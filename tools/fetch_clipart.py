"""Symbol-Bibliothek erzeugen: src/labelwerk/clipart_data/clipart.zip und LICENSES.md.

Lädt reproduzierbar:
- Tabler Icons (MIT) als npm-Tarball mit fester Version und SHA-256 – ohne Marken: ohne die
  Kategorie „Brand“ und ohne die Namen/Präfixe aus ``tabler_skip`` in de.json,
- Packzeichen (ISO 7000/ISO 780) und Sicherheitszeichen (ISO 7010) von Wikimedia Commons –
  nur Dateien mit Lizenz „Public domain“ oder „CC0“ laut Commons-API, ohne Einschränkungs-
  hinweise (Marke, Hoheitszeichen …) und ohne CC0-Freigaben von Dateien, deren Urheber die ISO
  ist (die kann ein Hochlader nicht erteilen); je ISO-7010-Code genau eine Datei,
- eigene Zeichnungen aus tools/clipart/eigene (CC0).
Was nicht passt, wird übersprungen und aufgelistet – außer bei den ausdrücklich gelisteten
ISO-7000-Zeichen: dann Abbruch. Der Stand der Commons-Dateien (SHA-1, Lizenz) steht in
tools/clipart/commons.lock.json; weicht er ab, bricht das Skript ab (``--update`` schreibt ihn
neu – danach die Änderungen prüfen). Deutsche Namen, Kategorien, Suchbegriffe:
tools/clipart/de.json. Jede SVG wird mit Qt probehalber gerastert (leer/ungültig → übersprungen).

    .venv/bin/python tools/fetch_clipart.py [--cache ORDNER] [--update]

Braucht Netz (Commons drosselt: Pausen von 3 s je Datei); nicht Teil der Tests. Das Ergebnis
wird eingecheckt.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(__file__).resolve().parent / "clipart"
LOCK = DATA / "commons.lock.json"
OUT = ROOT / "src" / "labelwerk" / "clipart_data"
TABLER_VERSION = "3.49.0"
TABLER_URL = f"https://registry.npmjs.org/@tabler/icons/-/icons-{TABLER_VERSION}.tgz"
TABLER_SHA256 = "aa3042907eb0bdb079fd70733e2d75f785683d4726279128a0ca2343099f7074"
TABLER_SKIP_CATEGORIES = {"Brand"}
API = "https://commons.wikimedia.org/w/api.php"
ISO7010_CATEGORY = "Category:ISO 7010 safety signs (vector drawings)"
ISO7010_FILE = re.compile(r"^File:ISO 7010 ([EFMPW]\d{3})(?:\.svg$|[ ;].*\.svg$)")
ISO7010_VARIANT = re.compile(r"\b(new|arrow|color)\b|-r\d", re.IGNORECASE)
FREE = {"Public domain": "Public domain", "CC0": "CC0"}
OWN_LICENSE = "CC0"
USER_AGENT = ("labelwerk-fetch-clipart/1.0 (https://github.com/siN161/labelwerk; "
              "einmaliger Abruf der Symbol-Bibliothek) python-urllib")   # Wikimedia-Richtlinie
RETRY = {429, 500, 502, 503, 504}
_WS = re.compile(r">\s+<")
_AUTHOR_NOISE = re.compile(r"(Der Quelltext dieser SVG-Datei ist valide\.?|Diese Vektorgrafik wurde "
                           r"von .* erstellt\s*\.?|Unknown author|Autor/-in unbekannt)",
                           re.IGNORECASE)


class FetchError(Exception):
    pass


def fetch(url: str, cache: Path | None = None, check=None) -> bytes:
    """URL laden – mit Cache-Ordner (atomar geschrieben), Wiederholung nur bei Drosselung,
    Serverfehler oder Zeitüberschreitung, höflicher Pause. ``check(data)`` wirft bei
    inhaltlichem Fehler (dann wird nichts gecacht)."""
    if cache is not None:
        hit = cache / hashlib.sha256(url.encode()).hexdigest()
        if hit.exists():
            return hit.read_bytes()
    for attempt in range(6):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=60) as response:
                data = response.read()
            break
        except urllib.error.HTTPError as e:
            if e.code not in RETRY or attempt == 5:
                raise SystemExit(f"Laden fehlgeschlagen: {url}: {e}") from e
            retry = e.headers.get("Retry-After")
            time.sleep(int(retry) if retry and retry.isdigit() else 60)
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt == 5:
                raise SystemExit(f"Laden fehlgeschlagen: {url}: {e}") from e
            time.sleep(30)
    time.sleep(3.0 if "upload.wikimedia.org" in url else 0.5)   # Commons drosselt sonst (429)
    if check is not None:
        check(data)
    if cache is not None:
        cache.mkdir(parents=True, exist_ok=True)
        part = hit.with_suffix(".part")
        part.write_bytes(data)
        part.replace(hit)
    return data


def api(cache: Path | None, **params) -> dict:
    params.update(format="json", formatversion="2")

    def check(data: bytes) -> None:
        if "error" in json.loads(data):
            raise SystemExit(f"Commons-API meldet Fehler: {json.loads(data)['error']}")
    return json.loads(fetch(f"{API}?{urllib.parse.urlencode(params)}", cache, check))


def plain(html: str) -> str:
    """HTML → Text (Tags als Leerraum, damit Wörter nicht zusammenkleben)."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or "")).strip()


def author(html: str) -> str:
    text = re.sub(r"\s+", " ", _AUTHOR_NOISE.sub(" ", plain(html))).strip(" .,;")
    return text if text and text.lower() not in {"author", "unknown"} else "unbekannt"


def compact(svg: str) -> str:
    """SVG verkleinern: Leerraum zwischen Tags, Tabler-Klassen und unsichtbares Hilfsrechteck
    raus, currentColor → Schwarz."""
    svg = re.sub(r'<path stroke="none" d="M0 0h24v24H0z" fill="none"\s*/>', "", svg)
    svg = re.sub(r'\s+class="[^"]*"', "", svg)
    svg = svg.replace("currentColor", "#000000")
    return _WS.sub("><", svg.strip()) + "\n"


# --- Tabler ------------------------------------------------------------------------------
def blocked(name: str, skip: list[str]) -> bool:
    """Marke? Eintrag mit „-“ am Ende ist ein Präfix, sonst Name samt Varianten („lego-off“)."""
    return any(name.startswith(s) if s.endswith("-") else name == s or name.startswith(s + "-")
               for s in skip)


def tabler(de: dict, cache: Path | None) -> tuple[list[dict], dict[str, bytes], str]:
    data = fetch(TABLER_URL, cache)
    if hashlib.sha256(data).hexdigest() != TABLER_SHA256:
        raise SystemExit("Tabler-Archiv: Prüfsumme stimmt nicht – Version geändert?")
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        def read(name: str) -> bytes:
            return tar.extractfile(f"package/{name}").read()
        icons = json.loads(read("icons.json"))
        licence = read("LICENSE").decode()
        skip = de["tabler_skip"]
        for entry in skip:                       # Tippfehler in der Sperrliste fallen auf
            if not any(blocked(name, [entry]) for name in icons):
                raise SystemExit(f"tabler_skip: {entry!r} passt auf kein Icon")
        wanted = {name: icon for name, icon in icons.items()
                  if icon.get("category") not in TABLER_SKIP_CATEGORIES
                  and not blocked(name, skip)}
        synonyms: dict[str, list[str]] = {}
        for word, names in de["synonyms"].items():
            for name in names:
                if name not in wanted:
                    raise SystemExit(f"Synonym {word!r}: Tabler-Icon {name!r} gibt es nicht")
                synonyms.setdefault(name, []).append(word)
        entries, files = [], {}
        for name, icon in sorted(wanted.items()):
            category = icon.get("category") or ""
            for style in ("outline", "filled"):
                if style not in icon.get("styles", {}):
                    continue
                path = f"tabler/{style}/{name}.svg"
                files[path] = compact(read(f"icons/{style}/{name}.svg").decode()).encode()
                entries.append({
                    "id": f"tabler/{style}/{name}", "group": "allgemein",
                    "subgroup": de["categories"].get(category, category),
                    "name": name.replace("-", " ") + (" (gefüllt)" if style == "filled" else ""),
                    "keywords": sorted({*map(str, icon.get("tags", [])), *synonyms.get(name, [])}),
                    "file": path, "source": f"Tabler Icons {TABLER_VERSION}",
                    "url": "https://tabler.io/icons", "author": "Paweł Kuna", "license": "MIT"})
    return entries, files, licence


# --- Wikimedia Commons ---------------------------------------------------------------------
def iso_name(description: str) -> str:
    """Titel aus der Commons-Beschreibung: „Warnzeichen W012: Warnung vor elektrischer
    Spannung“ → „Warnung vor elektrischer Spannung“; ohne Kennung, Erklärung nach „;“ und
    angehängte Quellenangaben."""
    text = description.split(":", 1)[1] if ":" in description else description
    text = re.sub(r"^(Safe condition sign|ISO 7010)?\s*[EFMPW]\d{3}\s*", "", text.strip())
    text = re.split(r";|Technische Regeln|Quelle\s*:|In Deutschland| nach DIN", text)[0]
    return text.strip(" .,:-")


def category_files(cache: Path | None) -> list[str]:
    """Alle Dateien der ISO-7010-Kategorie (seitenweise)."""
    titles, more = [], {}
    while True:
        answer = api(cache, action="query", list="categorymembers", cmtitle=ISO7010_CATEGORY,
                     cmtype="file", cmlimit="500", **more)
        titles += [m["title"] for m in answer["query"]["categorymembers"]]
        if "continue" not in answer:
            return titles
        more = {"cmcontinue": answer["continue"]["cmcontinue"]}


def file_info(titles: list[str], cache: Path | None) -> dict[str, dict]:
    info: dict[str, dict] = {}
    for start in range(0, len(titles), 40):
        pages = api(cache, action="query", titles="|".join(titles[start:start + 40]),
                    prop="imageinfo", iiprop="url|sha1|extmetadata", iiextmetadatalanguage="de",
                    iiextmetadatafilter="ImageDescription|LicenseShortName|License|Artist|"
                                        "Restrictions")["query"]["pages"]
        for page in pages:
            if page.get("imageinfo"):
                info[page["title"]] = page["imageinfo"][0]
    return info


def problem(title: str, meta: dict | None) -> str | None:
    """Warum diese Datei nicht in Frage kommt – oder None."""
    if meta is None:
        return "nicht gefunden"
    ext = meta["extmetadata"]
    licence = ext.get("LicenseShortName", {}).get("value", "")
    if licence not in FREE:
        return f"Lizenz {licence!r}"
    if ext.get("Restrictions", {}).get("value", "").strip():
        return f"Einschränkung {plain(ext['Restrictions']['value'])!r}"
    if licence == "CC0" and re.search(r"\bISO\b", author(ext.get("Artist", {}).get("value", ""))):
        return "CC0-Freigabe für ein ISO-Werk (zweifelhaft)"
    return None


def commons(de: dict, cache: Path | None, lock: dict, update: bool
            ) -> tuple[list[dict], dict[str, bytes], list[str], dict]:
    listed = [(f"File:ISO 7000 - Ref-No {ref}.svg", f"iso7000/{ref}") for ref in de["iso7000"]]
    candidates: dict[str, list[str]] = {}
    skipped = []
    for title in sorted(category_files(cache)):
        match = ISO7010_FILE.match(title)
        if match is None or ISO7010_VARIANT.search(title[14:]):
            skipped.append(f"{title}: kein Zeichen bzw. Variante")
            continue
        candidates.setdefault(match[1], []).append(title)
    for code, titles in candidates.items():          # der Dateiname ohne Zusatz zuerst
        titles.sort(key=lambda t, c=code: t != f"File:ISO 7010 {c}.svg")
    info = file_info([t for t, _ in listed] + [t for ts in candidates.values() for t in ts], cache)
    chosen = []
    for title, ident in listed:
        if why := problem(title, info.get(title)):
            raise SystemExit(f"{title}: {why} – ist in de.json ausdrücklich gelistet")
        chosen.append((title, ident, "versand"))
    for code, titles in sorted(candidates.items()):
        reasons = []
        for title in titles:
            if why := problem(title, info.get(title)):
                reasons.append(f"{title}: {why}")
            else:
                chosen.append((title, f"iso7010/{code}", "sicherheit"))
                break
        else:
            skipped += reasons
    entries, files, new_lock = [], {}, {}
    for title, ident, group in chosen:
        meta = info[title]
        ext = meta["extmetadata"]
        licence = FREE[ext["LicenseShortName"]["value"]]
        new_lock[title] = {"sha1": meta["sha1"], "license": licence}
        if not update and lock.get(title) != new_lock[title]:
            raise SystemExit(f"{title}: Stand weicht von commons.lock.json ab "
                             f"({lock.get(title)} → {new_lock[title]}) – mit --update übernehmen")
        svg = fetch(meta["url"].split("?")[0], cache)
        if hashlib.sha1(svg).hexdigest() != meta["sha1"]:
            raise SystemExit(f"{title}: Prüfsumme stimmt nicht")
        code = ident.split("/")[1]
        if group == "versand":
            name, subgroup, standard = de["iso7000"][code], "Packzeichen (ISO 780)", "ISO 780"
        else:
            subgroup, standard = de["iso7010_kinds"][code[0]], "ISO 7010"
            description = plain(ext.get("ImageDescription", {}).get("value", ""))
            name = f"{de['iso7010'].get(code) or iso_name(description) or title[5:-4]} ({code})"
        path = f"commons/{ident}.svg"
        files[path] = svg
        entries.append({
            "id": ident, "group": group, "subgroup": subgroup, "name": name,
            "keywords": [code, standard, subgroup], "file": path, "source": title[5:],
            "url": f"https://commons.wikimedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}",
            "author": author(ext.get("Artist", {}).get("value", "")), "license": licence})
    if not update and set(lock) != set(new_lock):
        raise SystemExit(f"Auswahl weicht von commons.lock.json ab: "
                         f"{sorted(set(lock) ^ set(new_lock))} – mit --update übernehmen")
    return entries, files, skipped, new_lock


# --- eigene Zeichnungen ----------------------------------------------------------------------
def own(de: dict) -> tuple[list[dict], dict[str, bytes]]:
    entries, files = [], {}
    names = de["eigene"]
    found = {p.stem for p in (DATA / "eigene").glob("*.svg")}
    if found != set(names):
        raise SystemExit(f"tools/clipart/eigene und de.json passen nicht zusammen: "
                         f"{sorted(found ^ set(names))}")
    for stem, meta in sorted(names.items()):
        path = f"labelwerk/{stem}.svg"
        files[path] = (DATA / "eigene" / f"{stem}.svg").read_bytes()
        entries.append({
            "id": f"labelwerk/{stem}", "group": meta["group"],
            "subgroup": "Elektro" if meta["group"] == "elektro" else "Packzeichen (ISO 780)",
            "name": meta["name"], "keywords": meta["keywords"], "file": path,
            "source": "labelwerk (eigene Zeichnung)", "url": "", "author": "labelwerk",
            "license": OWN_LICENSE})
    return entries, files


def check_render(files: dict[str, bytes]) -> list[str]:
    """Jede SVG mit Qt rastern: ungültig oder ganz weiß → Liste der Fehler."""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QByteArray, QRectF, Qt
    from PySide6.QtGui import QGuiApplication, QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer
    app = QGuiApplication.instance() or QGuiApplication([])  # noqa: F841 – muss leben
    dark = bytes(range(128))
    bad = []
    for path, svg in files.items():
        renderer = QSvgRenderer(QByteArray(svg))
        image = QImage(64, 64, QImage.Format.Format_Grayscale8)
        image.fill(Qt.GlobalColor.white)
        if renderer.isValid():
            painter = QPainter(image)
            renderer.render(painter, QRectF(0, 0, 64, 64))
            painter.end()
        pixels = bytes(image.constBits())
        if not renderer.isValid() or len(pixels.translate(None, dark)) == len(pixels):
            bad.append(path)
    return bad


def licences_md(entries: list[dict], tabler_licence: str) -> str:
    lines = ["# Lizenzen der Symbole", "",
             "Automatisch erzeugt von `tools/fetch_clipart.py` – nicht von Hand ändern.", "",
             f"## Tabler Icons {TABLER_VERSION} (MIT)", "", "https://tabler.io/icons", "",
             "```", tabler_licence.strip(), "```", "",
             "## Wikimedia Commons (gemeinfrei bzw. CC0)", "",
             "| Symbol | Datei | Urheber | Lizenz |", "|---|---|---|---|"]
    for e in entries:
        if e["id"].startswith(("iso7000/", "iso7010/")):
            lines.append(f"| {e['name']} | [{e['source']}]({e['url']}) | {e['author']} | "
                         f"{e['license']} |")
    lines += ["", "## Eigene Zeichnungen (CC0 – frei verwendbar, auch auf gedruckten Etiketten)", ""]
    lines += [f"- {e['name']}" for e in entries if e["id"].startswith("labelwerk/")]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--cache", type=Path, help="Ordner für geladene Dateien (wiederholbar)")
    parser.add_argument("--update", action="store_true",
                        help="geänderten Stand der Commons-Dateien übernehmen (commons.lock.json)")
    args = parser.parse_args()
    de = json.loads((DATA / "de.json").read_text(encoding="utf-8"))
    lock = json.loads(LOCK.read_text(encoding="utf-8")) if LOCK.exists() else {}
    own_entries, own_files = own(de)
    commons_entries, commons_files, skipped, new_lock = commons(de, args.cache, lock, args.update)
    tabler_entries, tabler_files, tabler_licence = tabler(de, args.cache)
    entries = own_entries + commons_entries + tabler_entries
    files = {**own_files, **commons_files, **tabler_files}
    bad = check_render(files)
    if bad:
        print("Nicht darstellbar (übersprungen):", *bad, sep="\n  ")
        entries = [e for e in entries if e["file"] not in bad]
        files = {k: v for k, v in files.items() if k not in bad}
    ids = [e["id"] for e in entries]
    if len(ids) != len(set(ids)):
        raise SystemExit("Doppelte ids im Katalog")
    OUT.mkdir(parents=True, exist_ok=True)
    catalog = {"version": 1, "symbols": entries}
    with zipfile.ZipFile(OUT / "clipart.zip", "w", zipfile.ZIP_DEFLATED) as zf:
        for name in ["catalog.json", *sorted(files)]:
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))   # reproduzierbar
            info.compress_type = zipfile.ZIP_DEFLATED
            data = (json.dumps(catalog, ensure_ascii=False, separators=(",", ":")).encode()
                    if name == "catalog.json" else files[name])
            zf.writestr(info, data, compresslevel=9)
    (OUT / "LICENSES.md").write_text(licences_md(entries, tabler_licence), encoding="utf-8")
    if args.update:
        LOCK.write_text(json.dumps(new_lock, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                        encoding="utf-8")
    counts = {}
    for e in entries:
        counts[e["group"]] = counts.get(e["group"], 0) + 1
    size = (OUT / "clipart.zip").stat().st_size
    print(f"{len(entries)} Symbole {counts}, clipart.zip {size / 1e6:.1f} MB")
    if skipped:
        print("Übersprungen:", *skipped, sep="\n  ")


if __name__ == "__main__":
    sys.exit(main())
