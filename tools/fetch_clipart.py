"""Generate the symbol library: src/labelwerk/clipart_data/clipart.zip and LICENSES.md.

Downloads reproducibly:
- Tabler Icons (MIT) as an npm tarball with a fixed version and SHA-256 – without trademarks: without the
  categories "Brand" and "Laundry" (care symbols) and without the names/prefixes from
  ``tabler_skip`` in de.json,
- packaging marks (ISO 7000/ISO 780) and safety signs (ISO 7010) from Wikimedia Commons –
  only files with the licence "Public domain" or "CC0" according to the Commons API, without restriction
  notes (trademark, state emblem ...) and without CC0 releases of files whose author is
  ISO (an uploader cannot grant those); exactly one file per ISO 7010 code,
- own drawings from tools/clipart/eigene (CC0).
Whatever does not fit is skipped and listed – except for the explicitly listed
ISO 7000 marks: those abort the run. The state of the Commons files (SHA-1, licence) is in
tools/clipart/commons.lock.json; if it differs, the script aborts (``--update`` rewrites it
– then check the changes). German names, categories, search terms:
tools/clipart/de.json, English ones: tools/clipart/en.json (required for every symbol – the English
Commons descriptions are too inconsistent). Every entry has ``names``/``subgroups`` per language
({"de", "en"}). Every SVG is trial-rasterised with Qt (empty/invalid → skipped).

    .venv/bin/python tools/fetch_clipart.py [--cache FOLDER] [--update]

Needs network access (Commons throttles: pauses of 3 s per file); not part of the tests. The result
is checked in.
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
TABLER_SKIP_CATEGORIES = {"Brand", "Laundry"}   # Laundry: textile care symbols (GINETEX marks);
                                                # the washing machine is in "Devices" and stays
API = "https://commons.wikimedia.org/w/api.php"
ISO7010_CATEGORY = "Category:ISO 7010 safety signs (vector drawings)"
ISO7010_FILE = re.compile(r"^File:ISO 7010 ([EFMPW]\d{3})(?:\.svg$|[ ;].*\.svg$)")
ISO7010_VARIANT = re.compile(r"\b(new|arrow|color)\b|-r\d", re.IGNORECASE)
FREE = {"Public domain": "Public domain", "CC0": "CC0"}
OWN_LICENSE = "CC0"
USER_AGENT = ("labelwerk-fetch-clipart/1.0 (https://github.com/siN161/labelwerk; "
              "one-off retrieval of the symbol library) python-urllib")   # Wikimedia policy
RETRY = {429, 500, 502, 503, 504}
_WS = re.compile(r">\s+<")
_AUTHOR_NOISE = re.compile(r"(Diese Vektorgrafik wurde "
                           r"von .* erstellt\s*\.?|Die vorherige Version wurde erzeugt mit .*|"
                           r"(?:\bi\s+)?Der Quelltext dieser SVG\s*-Datei ist valide\.?|"
                           r"Unknown author|Autor/-in unbekannt)",
                           re.IGNORECASE)


class FetchError(Exception):
    pass


def fetch(url: str, cache: Path | None = None, check=None) -> bytes:
    """Load a URL – with a cache folder (written atomically), retry only on throttling,
    server error or timeout, polite pause. ``check(data)`` raises on a
    content error (then nothing is cached)."""
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
                raise SystemExit(f"Download failed: {url}: {e}") from e
            retry = e.headers.get("Retry-After")
            time.sleep(int(retry) if retry and retry.isdigit() else 60)
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt == 5:
                raise SystemExit(f"Download failed: {url}: {e}") from e
            time.sleep(30)
    time.sleep(3.0 if "upload.wikimedia.org" in url else 0.5)   # otherwise Commons throttles (429)
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
            raise SystemExit(f"Commons API reports an error: {json.loads(data)['error']}")
    return json.loads(fetch(f"{API}?{urllib.parse.urlencode(params)}", cache, check))


def plain(html: str) -> str:
    """HTML → text (tags as whitespace so that words do not stick together)."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or "")).strip()


def author(html: str) -> str:
    text = re.sub(r"\s+", " ", _AUTHOR_NOISE.sub(" ", plain(html))).strip(" .,;")
    return text if text and text.lower() not in {"author", "unknown"} else "unbekannt"


def compact(svg: str) -> str:
    """Shrink the SVG: drop whitespace between tags, Tabler classes and the invisible helper
    rectangle, currentColor → black."""
    svg = re.sub(r'<path stroke="none" d="M0 0h24v24H0z" fill="none"\s*/>', "", svg)
    svg = re.sub(r'\s+class="[^"]*"', "", svg)
    svg = svg.replace("currentColor", "#000000")
    return _WS.sub("><", svg.strip()) + "\n"


# --- Tabler ------------------------------------------------------------------------------
def blocked(name: str, skip: list[str]) -> bool:
    """Trademark? An entry ending in "-" is a prefix, otherwise a name including variants ("lego-off")."""
    return any(name.startswith(s) if s.endswith("-") else name == s or name.startswith(s + "-")
               for s in skip)


def tabler(de: dict, cache: Path | None) -> tuple[list[dict], dict[str, bytes], str]:
    data = fetch(TABLER_URL, cache)
    if hashlib.sha256(data).hexdigest() != TABLER_SHA256:
        raise SystemExit("Tabler archive: checksum does not match – version changed?")
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        def read(name: str) -> bytes:
            return tar.extractfile(f"package/{name}").read()
        icons = json.loads(read("icons.json"))
        licence = read("LICENSE").decode()
        skip = de["tabler_skip"]
        for entry in skip:                       # typos in the block list get noticed
            if not any(blocked(name, [entry]) for name in icons):
                raise SystemExit(f"tabler_skip: {entry!r} matches no icon")
        wanted = {name: icon for name, icon in icons.items()
                  if icon.get("category") not in TABLER_SKIP_CATEGORIES
                  and not blocked(name, skip)}
        synonyms: dict[str, list[str]] = {}
        for word, names in de["synonyms"].items():
            for name in names:
                if name not in wanted:
                    raise SystemExit(f"Synonym {word!r}: Tabler icon {name!r} does not exist")
                synonyms.setdefault(name, []).append(word)
        entries, files = [], {}
        for name, icon in sorted(wanted.items()):
            category = icon.get("category") or ""
            for style in ("outline", "filled"):
                if style not in icon.get("styles", {}):
                    continue
                path = f"tabler/{style}/{name}.svg"
                files[path] = compact(read(f"icons/{style}/{name}.svg").decode()).encode()
                plain_name = name.replace("-", " ")
                subgroup = de["categories"].get(category, category)
                entries.append({
                    "id": f"tabler/{style}/{name}", "group": "allgemein",
                    "subgroup": subgroup,
                    "name": plain_name + (" (gefüllt)" if style == "filled" else ""),
                    "names": {"de": plain_name + (" (gefüllt)" if style == "filled" else ""),
                              "en": plain_name + (" (filled)" if style == "filled" else "")},
                    "subgroups": {"de": subgroup, "en": category or "Other"},
                    "keywords": sorted({*map(str, icon.get("tags", [])), *synonyms.get(name, [])}),
                    "file": path, "source": f"Tabler Icons {TABLER_VERSION}",
                    "url": "https://tabler.io/icons", "author": "Paweł Kuna", "license": "MIT"})
    return entries, files, licence


# --- Wikimedia Commons ---------------------------------------------------------------------
def iso_name(description: str) -> str:
    """Title from the Commons description: "Warnzeichen W012: Warnung vor elektrischer
    Spannung" → "Warnung vor elektrischer Spannung"; without code, explanation after ";" and
    appended source references."""
    text = description.split(":", 1)[1] if ":" in description else description
    text = re.sub(r"^(Safe condition sign|ISO 7010)?\s*[EFMPW]\d{3}\s*", "", text.strip())
    text = re.split(r";|Technische Regeln|Quelle\s*:|In Deutschland| nach DIN", text)[0]
    return text.strip(" .,:-")


def category_files(cache: Path | None) -> list[str]:
    """All files of the ISO 7010 category (page by page)."""
    titles, more = [], {}
    while True:
        answer = api(cache, action="query", list="categorymembers", cmtitle=ISO7010_CATEGORY,
                     cmtype="file", cmlimit="500", **more)
        titles += [m["title"] for m in answer["query"]["categorymembers"]]
        if "continue" not in answer:
            return titles
        more = {"cmcontinue": answer["continue"]["cmcontinue"]}


def file_info(titles: list[str], cache: Path | None, language: str = "de") -> dict[str, dict]:
    info: dict[str, dict] = {}
    for start in range(0, len(titles), 40):
        pages = api(cache, action="query", titles="|".join(titles[start:start + 40]),
                    prop="imageinfo", iiprop="url|sha1|extmetadata", iiextmetadatalanguage=language,
                    iiextmetadatafilter="ImageDescription|LicenseShortName|License|Artist|"
                                        "Restrictions")["query"]["pages"]
        for page in pages:
            if page.get("imageinfo"):
                info[page["title"]] = page["imageinfo"][0]
    return info


def problem(title: str, meta: dict | None) -> str | None:
    """Why this file is out of the question – or None."""
    if meta is None:
        return "not found"
    ext = meta["extmetadata"]
    licence = ext.get("LicenseShortName", {}).get("value", "")
    if licence not in FREE:
        return f"licence {licence!r}"
    if ext.get("Restrictions", {}).get("value", "").strip():
        return f"restriction {plain(ext['Restrictions']['value'])!r}"
    if licence == "CC0" and re.search(r"\bISO\b", author(ext.get("Artist", {}).get("value", ""))):
        return "CC0 release for an ISO work (doubtful)"
    return None


def commons(de: dict, en: dict, cache: Path | None, lock: dict, update: bool
            ) -> tuple[list[dict], dict[str, bytes], list[str], dict]:
    listed = [(f"File:ISO 7000 - Ref-No {ref}.svg", f"iso7000/{ref}") for ref in de["iso7000"]]
    candidates: dict[str, list[str]] = {}
    skipped = []
    for title in sorted(category_files(cache)):
        match = ISO7010_FILE.match(title)
        if match is None or ISO7010_VARIANT.search(title[14:]):
            skipped.append(f"{title}: not a sign or a variant")
            continue
        candidates.setdefault(match[1], []).append(title)
    for code, titles in candidates.items():          # the file name without suffix first
        titles.sort(key=lambda t, c=code: t != f"File:ISO 7010 {c}.svg")
    info = file_info([t for t, _ in listed] + [t for ts in candidates.values() for t in ts], cache)
    chosen = []
    for title, ident in listed:
        if why := problem(title, info.get(title)):
            raise SystemExit(f"{title}: {why} – is explicitly listed in de.json")
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
            raise SystemExit(f"{title}: state differs from commons.lock.json "
                             f"({lock.get(title)} → {new_lock[title]}) – accept with --update")
        svg = fetch(meta["url"].split("?")[0], cache)
        if hashlib.sha1(svg).hexdigest() != meta["sha1"]:
            raise SystemExit(f"{title}: checksum does not match")
        code = ident.split("/")[1]
        if group == "versand":
            name, subgroup, standard = de["iso7000"][code], "Packzeichen (ISO 780)", "ISO 780"
            name_en, subgroup_en = en["iso7000"][code], en["subgroups"][subgroup]
        else:
            subgroup, standard = de["iso7010_kinds"][code[0]], "ISO 7010"
            subgroup_en = en["iso7010_kinds"][code[0]]
            description = plain(ext.get("ImageDescription", {}).get("value", ""))
            name = f"{de['iso7010'].get(code) or iso_name(description) or title[5:-4]} ({code})"
            if code not in en["iso7010"]:
                raise SystemExit(f"{title}: English name missing in en.json (iso7010/{code})")
            name_en = f"{en['iso7010'][code]} ({code})"
        path = f"commons/{ident}.svg"
        files[path] = svg
        entries.append({
            "id": ident, "group": group, "subgroup": subgroup, "name": name,
            "names": {"de": name, "en": name_en},
            "subgroups": {"de": subgroup, "en": subgroup_en},
            "keywords": [code, standard, subgroup, subgroup_en], "file": path, "source": title[5:],
            "url": f"https://commons.wikimedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}",
            "author": author(ext.get("Artist", {}).get("value", "")), "license": licence})
    if not update and set(lock) != set(new_lock):
        raise SystemExit(f"Selection differs from commons.lock.json: "
                         f"{sorted(set(lock) ^ set(new_lock))} – accept with --update")
    return entries, files, skipped, new_lock


# --- own drawings ----------------------------------------------------------------------
def own(de: dict, en: dict) -> tuple[list[dict], dict[str, bytes]]:
    entries, files = [], {}
    names = de["eigene"]
    found = {p.stem for p in (DATA / "eigene").glob("*.svg")}
    if found != set(names):
        raise SystemExit(f"tools/clipart/eigene and de.json do not match: "
                         f"{sorted(found ^ set(names))}")
    if set(en["eigene"]) != set(names):
        raise SystemExit(f"en.json and de.json (eigene) do not match: "
                         f"{sorted(set(en['eigene']) ^ set(names))}")
    for stem, meta in sorted(names.items()):
        path = f"labelwerk/{stem}.svg"
        files[path] = (DATA / "eigene" / f"{stem}.svg").read_bytes()
        subgroup = "Elektro" if meta["group"] == "elektro" else "Packzeichen (ISO 780)"
        entries.append({
            "id": f"labelwerk/{stem}", "group": meta["group"], "subgroup": subgroup,
            "name": meta["name"], "names": {"de": meta["name"], "en": en["eigene"][stem]},
            "subgroups": {"de": subgroup, "en": en["subgroups"][subgroup]},
            "keywords": meta["keywords"], "file": path,
            "source": "labelwerk (eigene Zeichnung)", "url": "", "author": "labelwerk",
            "license": OWN_LICENSE})
    return entries, files


def check_render(files: dict[str, bytes]) -> list[str]:
    """Rasterise every SVG with Qt: invalid or completely white → list of failures."""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QByteArray, QRectF, Qt
    from PySide6.QtGui import QGuiApplication, QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer
    app = QGuiApplication.instance() or QGuiApplication([])  # noqa: F841 – must stay alive
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
    lines = ["# Licences of the symbols", "",
             "Generated automatically by `tools/fetch_clipart.py` – do not edit by hand.", "",
             "Names: German from `tools/clipart/de.json` or the Commons description, English from "
             "`tools/clipart/en.json` – own translations or short titles of the standards, no text taken "
             "from Commons or Wikipedia.", "",
             f"## Tabler Icons {TABLER_VERSION} (MIT)", "", "https://tabler.io/icons", "",
             "```", tabler_licence.strip(), "```", "",
             "## Wikimedia Commons (public domain or CC0)", "",
             "| Symbol | File | Author | Licence |", "|---|---|---|---|"]
    for e in entries:
        if e["id"].startswith(("iso7000/", "iso7010/")):
            lines.append(f"| {e['names']['en']} | [{e['source']}]({e['url']}) | {e['author']} | "
                         f"{e['license']} |")
    lines += ["", "## Own drawings (CC0 – free to use, also on printed labels)", ""]
    lines += [f"- {e['names']['en']}" for e in entries if e["id"].startswith("labelwerk/")]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--cache", type=Path, help="folder for downloaded files (repeatable)")
    parser.add_argument("--update", action="store_true",
                        help="accept a changed state of the Commons files (commons.lock.json)")
    args = parser.parse_args()
    de = json.loads((DATA / "de.json").read_text(encoding="utf-8"))
    en = json.loads((DATA / "en.json").read_text(encoding="utf-8"))
    lock = json.loads(LOCK.read_text(encoding="utf-8")) if LOCK.exists() else {}
    own_entries, own_files = own(de, en)
    commons_entries, commons_files, skipped, new_lock = commons(de, en, args.cache, lock,
                                                                 args.update)
    tabler_entries, tabler_files, tabler_licence = tabler(de, args.cache)
    entries = own_entries + commons_entries + tabler_entries
    files = {**own_files, **commons_files, **tabler_files}
    bad = check_render(files)
    if bad:
        print("Cannot be rendered (skipped):", *bad, sep="\n  ")
        entries = [e for e in entries if e["file"] not in bad]
        files = {k: v for k, v in files.items() if k not in bad}
    ids = [e["id"] for e in entries]
    if len(ids) != len(set(ids)):
        raise SystemExit("Duplicate ids in the catalog")
    OUT.mkdir(parents=True, exist_ok=True)
    catalog = {"version": 1, "symbols": entries}
    with zipfile.ZipFile(OUT / "clipart.zip", "w", zipfile.ZIP_DEFLATED) as zf:
        for name in ["catalog.json", *sorted(files)]:
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))   # reproducible
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
    print(f"{len(entries)} symbols {counts}, clipart.zip {size / 1e6:.1f} MB")
    if skipped:
        print("Skipped:", *skipped, sep="\n  ")


if __name__ == "__main__":
    sys.exit(main())
