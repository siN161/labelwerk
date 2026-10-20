"""Mock XDG screenshot portal for tests on a private D-Bus (never the one of the session).

Runs with the system Python (PyGObject/Gio): ``python3 fake_portal.py KIND CODE URI``.
KIND: ``normal`` (answer after 50 ms), ``early`` (answer already before the return value),
``other`` (own request path like older portals), ``twice`` (two answers),
``never`` (never answers).
URI "-" = answer without ``uri``; "{n}" in the URI becomes the number of the call.
Prints "READY" as soon as the name is taken, and per call
"CALL interactive=… modal=… token=…" as well as "CLOSE <path>" when someone sends ``Request.Close`` to
a request path (after the call that delivered it); without the name it ends with code 1.
"""
import sys

from gi.repository import Gio, GLib

MODE, CODE, URI = sys.argv[1], int(sys.argv[2]), sys.argv[3]
XML = """<node><interface name="org.freedesktop.portal.Screenshot">
<method name="Screenshot"><arg type="s" direction="in"/><arg type="a{sv}" direction="in"/>
<arg type="o" direction="out"/></method><property name="version" type="u" access="read"/>
</interface></node>"""
REQUEST_XML = """<node><interface name="org.freedesktop.portal.Request">
<method name="Close"/></interface></node>"""
INFO = Gio.DBusNodeInfo.new_for_xml(XML).interfaces[0]
REQUEST_INFO = Gio.DBusNodeInfo.new_for_xml(REQUEST_XML).interfaces[0]
calls = 0


def close(conn, sender, path, iface, method, params, invocation):
    print(f"CLOSE {path}", flush=True)
    invocation.return_value(None)


def call(conn, sender, path, iface, method, params, invocation):
    global calls
    calls += 1
    options = params.unpack()[1]
    print(f"CALL interactive={options.get('interactive')} modal={options.get('modal')} "
          f"token={options['handle_token']}", flush=True)
    base = "/org/freedesktop/portal/desktop/request/" + sender[1:].replace(".", "_")
    request = f"{base}/{options['handle_token']}" if MODE != "other" else f"{base}/alt{calls}"
    results = {"uri": GLib.Variant("s", URI.format(n=calls))} if URI != "-" else {}

    def emit():
        conn.emit_signal(None, request, "org.freedesktop.portal.Request", "Response",
                         GLib.Variant("(ua{sv})", (CODE, results)))
        return False

    if MODE == "early":
        emit()
        conn.flush_sync(None)
    conn.register_object(request, REQUEST_INFO, close, None, None)
    invocation.return_value(GLib.Variant("(o)", (request,)))
    if MODE == "twice":
        GLib.timeout_add(30, emit)
        GLib.timeout_add(60, emit)
    elif MODE not in ("early", "never"):
        GLib.timeout_add(50, emit)


def get_property(conn, sender, path, iface, name):
    return GLib.Variant("u", 2)


loop = GLib.MainLoop()
bus = Gio.bus_get_sync(Gio.BusType.SESSION)
bus.register_object("/org/freedesktop/portal/desktop", INFO, call, get_property, None)
Gio.bus_own_name_on_connection(bus, "org.freedesktop.portal.Desktop", 0,
                               lambda conn, name: print("READY", flush=True),
                               lambda conn, name: loop.quit())    # name not (or no longer) taken
loop.run()
sys.exit(1)
