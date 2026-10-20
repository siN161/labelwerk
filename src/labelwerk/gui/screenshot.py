"""Screenshot via the XDG desktop portal (``org.freedesktop.portal.Screenshot``).

The desktop shows the selection (area, window, screen) (``interactive``); the portal
answers asynchronously with the signal ``Response`` on the request object, whose path results from
the bus name and its own ``handle_token`` – so it is subscribed to before the call.
Testable without D-Bus: ``request_path``, ``parse_response``, ``error_text``. Calls go out as
single messages (``QDBusInterface`` would introspect blockingly when created).
"""
from __future__ import annotations

import uuid
from pathlib import Path
from urllib.parse import unquote, urlparse

from PySide6.QtCore import SLOT, QObject, Signal, Slot
from PySide6.QtDBus import QDBus, QDBusConnection, QDBusMessage

from ..i18n import N_, _

SERVICE = "org.freedesktop.portal.Desktop"
OBJECT = "/org/freedesktop/portal/desktop"
INTERFACE = "org.freedesktop.portal.Screenshot"
REQUEST = "org.freedesktop.portal.Request"
AVAILABLE_TIMEOUT_MS = 5_000      # portal there? (if it has to start first, that usually takes < 1 s)
CALL_TIMEOUT_MS = 10_000          # answer to the call itself (the selection may take any time)
FAILED = N_("Screenshot failed")
_RESPONSE_SLOT = SLOT("response(uint,QVariantMap)")
_NO_PORTAL = ("ServiceUnknown", "NameHasNoOwner", "UnknownObject", "UnknownInterface",
              "UnknownMethod", "ServiceNotFound")
_NO_ANSWER = ("NoReply", "Timeout", "TimedOut")


def session_bus() -> QDBusConnection:
    """Session bus (replaced in tests – no test reaches the real portal)."""
    return QDBusConnection.sessionBus()


def request_path(unique_name: str, token: str) -> str:
    """Path of the request object the portal answers on (bus name “:1.42” → “1_42”)."""
    sender = unique_name.lstrip(":").replace(".", "_")
    return f"{OBJECT}/request/{sender}/{token}"


def parse_response(code: int, results: dict) -> tuple[Path | None, str | None]:
    """Portal response → (path of the image file, error message); (None, None) = cancelled."""
    if code == 1:
        return None, None
    if code != 0:
        return None, _("Screenshot failed – rejected or cancelled by the system")
    uri = urlparse(str(results.get("uri") or ""))
    if uri.scheme != "file" or not uri.path:
        return None, _("Screenshot failed – no image file received")
    return Path(unquote(uri.path)), None


def error_text(error_name: str) -> str:
    """D-Bus error name (e.g. “org.freedesktop.DBus.Error.ServiceUnknown”) → message for the user
    (D-Bus's own error texts are English)."""
    short = error_name.rsplit(".", 1)[-1]
    if short in _NO_PORTAL:
        return _("Screenshot failed – no screenshot portal found")
    if short in _NO_ANSWER:
        return _("Screenshot failed – the portal does not answer")
    if short == "NotAllowed":
        return _("Screenshot failed – not allowed by the system")
    return _("Screenshot failed – error of the portal")


class _Request(QObject):
    """Receiver of the answer to one capture. QtDBus delivers signals via the event queue:
    an already queued answer of a discarded capture still arrives after unsubscribing –
    it counts only as long as its receiver is the current one."""

    def __init__(self, portal: ScreenshotPortal):
        super().__init__(portal)
        self._portal = portal

    @Slot("uint", "QVariantMap")
    def response(self, code: int, results: dict) -> None:
        self._portal._response(self, code, results)


class ScreenshotPortal(QObject):
    """One screenshot per ``take()``; result exactly once via ``finished``:
    (path | None, error message | None), (None, None) = cancelled."""

    finished = Signal(object, object)

    def __init__(self, bus: QDBusConnection | None = None, parent: QObject | None = None):
        super().__init__(parent)
        self._bus = bus
        self._request: _Request | None = None   # receiver of the open capture
        self._spent: list[_Request] = []        # earlier receivers, deleted on the next take()
        self._path: str | None = None           # request path subscribed for it

    def bus(self) -> QDBusConnection:
        return self._bus if self._bus is not None else session_bus()

    def _call(self, path: str, interface: str, method: str, *args,
              timeout: int = CALL_TIMEOUT_MS) -> QDBusMessage:
        message = QDBusMessage.createMethodCall(SERVICE, path, interface, method)
        message.setArguments(list(args))
        return self.bus().call(message, QDBus.CallMode.Block, timeout)

    def available(self) -> bool:
        """Session bus reachable and portal with the Screenshot interface present."""
        if not self.bus().isConnected():
            return False
        reply = self._call(OBJECT, "org.freedesktop.DBus.Properties", "Get", INTERFACE,
                           "version", timeout=AVAILABLE_TIMEOUT_MS)
        return reply.type() == QDBusMessage.MessageType.ReplyMessage

    def take(self) -> None:
        """Open the desktop's selection; the result arrives via ``finished`` – on errors before
        the selection (no bus, no portal) still during this call. A capture that is still open
        is discarded (its selection closed, its answer no longer reported)."""
        if self._path is not None:
            self._close(self._path)
        self._drop()
        for request in self._spent:          # not earlier: deleting a receiver whose
            request.deleteLater()             # answer is just being delivered crashes (SIGBUS)
        self._spent.clear()
        bus = self.bus()
        if not bus.isConnected():
            self.finished.emit(None, _("Screenshot failed – no connection to the session bus"))
            return
        token = f"labelwerk_{uuid.uuid4().hex}"
        self._request = _Request(self)
        if not self._subscribe(request_path(bus.baseService(), token)):
            return
        reply = self._call(OBJECT, INTERFACE, "Screenshot", "",
                           {"handle_token": token, "interactive": True, "modal": True})
        if reply.type() != QDBusMessage.MessageType.ReplyMessage:
            self._finish(None, error_text(reply.errorName()))
            return
        try:
            handle = reply.arguments()[0].path()
        except (IndexError, AttributeError):
            self._finish(None, _("Screenshot failed – unexpected answer from the portal"))
            return
        if handle != self._path and not self._subscribe(handle):   # older portals: own path
            self._close(handle)                  # without subscription no answer comes: close the selection

    def _close(self, path: str) -> None:
        """Close the open selection at request path ``path`` (``Request.Close``, without answer)."""
        self.bus().send(QDBusMessage.createMethodCall(SERVICE, path, REQUEST, "Close"))

    def _subscribe(self, path: str) -> bool:
        """Subscribe to the answer at path ``path`` (an older one is released); if that fails, the
        capture ends with an error – otherwise no answer would ever come."""
        self._unsubscribe()
        if not self.bus().connect(SERVICE, path, REQUEST, "Response", self._request,
                                  _RESPONSE_SLOT):
            self._finish(None, _("Screenshot failed – cannot subscribe to the answer of the portal"))
            return False
        self._path = path
        return True

    def _unsubscribe(self) -> None:
        if self._path is not None:
            self.bus().disconnect(SERVICE, self._path, REQUEST, "Response", self._request,
                                  _RESPONSE_SLOT)
            self._path = None

    def _drop(self) -> None:
        self._unsubscribe()
        if self._request is not None:
            self._spent.append(self._request)
            self._request = None

    def _response(self, request: _Request, code: int, results: dict) -> None:
        if request is self._request:
            self._finish(*parse_response(code, results))

    def _finish(self, path: Path | None, error: str | None) -> None:
        self._drop()
        self.finished.emit(path, error)
