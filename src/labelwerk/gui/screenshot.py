"""Bildschirmfoto über das XDG-Desktop-Portal (``org.freedesktop.portal.Screenshot``).

Die Auswahl (Bereich, Fenster, Bildschirm) zeigt der Desktop (``interactive``); das Portal
antwortet asynchron mit dem Signal ``Response`` am Request-Objekt, dessen Pfad sich aus dem
Busnamen und einem eigenen ``handle_token`` ergibt – darum wird es vor dem Aufruf abonniert.
Ohne D-Bus testbar: ``request_path``, ``parse_response``, ``error_text``. Aufrufe gehen als
einzelne Nachrichten raus (``QDBusInterface`` würde beim Anlegen blockierend introspektieren).
"""
from __future__ import annotations

import uuid
from pathlib import Path
from urllib.parse import unquote, urlparse

from PySide6.QtCore import SLOT, QObject, Signal, Slot
from PySide6.QtDBus import QDBus, QDBusConnection, QDBusMessage

SERVICE = "org.freedesktop.portal.Desktop"
OBJECT = "/org/freedesktop/portal/desktop"
INTERFACE = "org.freedesktop.portal.Screenshot"
REQUEST = "org.freedesktop.portal.Request"
AVAILABLE_TIMEOUT_MS = 5_000      # Portal da? (startet es erst, dauert das meist < 1 s)
CALL_TIMEOUT_MS = 10_000          # Antwort auf den Aufruf selbst (die Auswahl dauert beliebig)
FAILED = "Bildschirmfoto fehlgeschlagen"
_RESPONSE_SLOT = SLOT("response(uint,QVariantMap)")
_NO_PORTAL = ("ServiceUnknown", "NameHasNoOwner", "UnknownObject", "UnknownInterface",
              "UnknownMethod", "ServiceNotFound")
_NO_ANSWER = ("NoReply", "Timeout", "TimedOut")


def session_bus() -> QDBusConnection:
    """Sitzungsbus (in Tests ersetzt – kein Test erreicht das echte Portal)."""
    return QDBusConnection.sessionBus()


def request_path(unique_name: str, token: str) -> str:
    """Pfad des Request-Objekts, an dem das Portal antwortet (Busname „:1.42“ → „1_42“)."""
    sender = unique_name.lstrip(":").replace(".", "_")
    return f"{OBJECT}/request/{sender}/{token}"


def parse_response(code: int, results: dict) -> tuple[Path | None, str | None]:
    """Antwort des Portals → (Pfad der Bilddatei, Fehlermeldung); (None, None) = abgebrochen."""
    if code == 1:
        return None, None
    if code != 0:
        return None, f"{FAILED} – vom System abgelehnt oder abgebrochen"
    uri = urlparse(str(results.get("uri") or ""))
    if uri.scheme != "file" or not uri.path:
        return None, f"{FAILED} – keine Bilddatei erhalten"
    return Path(unquote(uri.path)), None


def error_text(error_name: str) -> str:
    """D-Bus-Fehlername (z. B. „org.freedesktop.DBus.Error.ServiceUnknown“) → deutsche Meldung
    (die Fehlertexte von D-Bus sind englisch)."""
    short = error_name.rsplit(".", 1)[-1]
    if short in _NO_PORTAL:
        return f"{FAILED} – kein Bildschirmfoto-Portal gefunden"
    if short in _NO_ANSWER:
        return f"{FAILED} – das Portal antwortet nicht"
    if short == "NotAllowed":
        return f"{FAILED} – vom System nicht erlaubt"
    return f"{FAILED} – Fehler des Portals"


class _Request(QObject):
    """Empfänger der Antwort einer Aufnahme. QtDBus stellt Signale über die Ereignisschlange
    zu: eine schon eingereihte Antwort einer verworfenen Aufnahme kommt auch nach dem Abmelden
    noch an – sie zählt nur, solange ihr Empfänger der aktuelle ist."""

    def __init__(self, portal: ScreenshotPortal):
        super().__init__(portal)
        self._portal = portal

    @Slot("uint", "QVariantMap")
    def response(self, code: int, results: dict) -> None:
        self._portal._response(self, code, results)


class ScreenshotPortal(QObject):
    """Ein Bildschirmfoto je ``take()``; Ergebnis genau einmal über ``finished``:
    (Pfad | None, Fehlermeldung | None), (None, None) = abgebrochen."""

    finished = Signal(object, object)

    def __init__(self, bus: QDBusConnection | None = None, parent: QObject | None = None):
        super().__init__(parent)
        self._bus = bus
        self._request: _Request | None = None   # Empfänger der offenen Aufnahme
        self._spent: list[_Request] = []        # frühere Empfänger, beim nächsten take() gelöscht
        self._path: str | None = None           # dafür abonnierter Request-Pfad

    def bus(self) -> QDBusConnection:
        return self._bus if self._bus is not None else session_bus()

    def _call(self, path: str, interface: str, method: str, *args,
              timeout: int = CALL_TIMEOUT_MS) -> QDBusMessage:
        message = QDBusMessage.createMethodCall(SERVICE, path, interface, method)
        message.setArguments(list(args))
        return self.bus().call(message, QDBus.CallMode.Block, timeout)

    def available(self) -> bool:
        """Sitzungsbus erreichbar und Portal mit Schnittstelle Screenshot vorhanden."""
        if not self.bus().isConnected():
            return False
        reply = self._call(OBJECT, "org.freedesktop.DBus.Properties", "Get", INTERFACE,
                           "version", timeout=AVAILABLE_TIMEOUT_MS)
        return reply.type() == QDBusMessage.MessageType.ReplyMessage

    def take(self) -> None:
        """Auswahl des Desktops öffnen; das Ergebnis kommt über ``finished`` – bei Fehlern vor
        der Auswahl (kein Bus, kein Portal) noch während dieses Aufrufs. Eine noch offene
        Aufnahme wird verworfen (ihre Auswahl geschlossen, ihre Antwort nicht mehr gemeldet)."""
        if self._path is not None:
            self.bus().send(QDBusMessage.createMethodCall(SERVICE, self._path, REQUEST, "Close"))
        self._drop()
        for request in self._spent:          # nicht früher: Löschen eines Empfängers, dessen
            request.deleteLater()             # Antwort gerade zugestellt wird, stürzt ab (SIGBUS)
        self._spent.clear()
        bus = self.bus()
        if not bus.isConnected():
            self.finished.emit(None, f"{FAILED} – keine Verbindung zum Sitzungsbus")
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
            self._finish(None, f"{FAILED} – unerwartete Antwort des Portals")
            return
        if handle != self._path:            # ältere Portale: eigener Pfad
            self._subscribe(handle)

    def _subscribe(self, path: str) -> bool:
        """Antwort am Pfad ``path`` abonnieren (ein älteres wird gelöst); scheitert das, ist die
        Aufnahme mit Fehler beendet – sonst käme nie eine Antwort."""
        self._unsubscribe()
        if not self.bus().connect(SERVICE, path, REQUEST, "Response", self._request,
                                  _RESPONSE_SLOT):
            self._finish(None, f"{FAILED} – Antwort des Portals nicht abonnierbar")
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
