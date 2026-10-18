"""Nachgebautes XDG-Screenshot-Portal für Tests auf einem privaten D-Bus (nie dem der Sitzung).

Läuft mit dem System-Python (PyGObject/Gio): ``python3 fake_portal.py ART CODE URI``.
ART: ``normal`` (Antwort nach 50 ms), ``early`` (Antwort schon vor dem Rückgabewert),
``other`` (eigener Request-Pfad wie ältere Portale), ``twice`` (zwei Antworten).
URI „-“ = Antwort ohne ``uri``; „{n}“ in der URI wird zur Nummer des Aufrufs.
Gibt „READY“ aus, sobald der Name belegt ist, und je Aufruf
„CALL interactive=… modal=… token=…“; ohne Namen endet es mit Code 1.
"""
import sys

from gi.repository import Gio, GLib

MODE, CODE, URI = sys.argv[1], int(sys.argv[2]), sys.argv[3]
XML = """<node><interface name="org.freedesktop.portal.Screenshot">
<method name="Screenshot"><arg type="s" direction="in"/><arg type="a{sv}" direction="in"/>
<arg type="o" direction="out"/></method><property name="version" type="u" access="read"/>
</interface></node>"""
INFO = Gio.DBusNodeInfo.new_for_xml(XML).interfaces[0]
calls = 0


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
    invocation.return_value(GLib.Variant("(o)", (request,)))
    if MODE == "twice":
        GLib.timeout_add(30, emit)
        GLib.timeout_add(60, emit)
    elif MODE != "early":
        GLib.timeout_add(50, emit)


def get_property(conn, sender, path, iface, name):
    return GLib.Variant("u", 2)


loop = GLib.MainLoop()
bus = Gio.bus_get_sync(Gio.BusType.SESSION)
bus.register_object("/org/freedesktop/portal/desktop", INFO, call, get_property, None)
Gio.bus_own_name_on_connection(bus, "org.freedesktop.portal.Desktop", 0,
                               lambda conn, name: print("READY", flush=True),
                               lambda conn, name: loop.quit())    # Name nicht (mehr) belegt
loop.run()
sys.exit(1)
