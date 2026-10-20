"""Collect translatable texts and maintain the language files.

    python tools/i18n.py extract   # rewrite src/labelwerk/po/labelwerk.pot from the code
    python tools/i18n.py update    # carry new texts into every .po, mark dropped ones obsolete (#~)
    python tools/i18n.py check     # like the test: .pot up to date, every language complete

Calls of ``_``, ``N_``, ``NP_``, ``ngettext`` and ``pgettext`` with a literal text are found (AST,
without executing the code); "# Translators: …" comments directly above are carried along as a hint
(``#.``), texts with ``{name}`` get ``#, python-brace-format`` (Weblate/Poedit then check the
placeholders). ``update`` keeps what translators entered: comments, uncertain (fuzzy) and obsolete
entries. The output is sorted, without date and without line numbers (location = file) – it only
changes when texts change.
"""
from __future__ import annotations

import ast
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "labelwerk"
PO_DIR = SRC / "po"
POT = PO_DIR / "labelwerk.pot"
HEADER = {"de": "nplurals=2; plural=(n != 1);"}


@dataclass
class Message:
    msgid: str
    plural: str | None = None
    context: str = ""
    places: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)       # hints for translators (#.)

    @property
    def brace_format(self) -> bool:
        return bool(re.search(r"\{[^{}]*\}", self.msgid.replace("{{", "").replace("}}", "")))

    @property
    def key(self) -> tuple[str, str]:
        return self.context, self.msgid


def _text(node) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def extract(src: Path = SRC) -> dict[tuple[str, str], Message]:
    """All translatable texts under ``src``: (context, text) → Message with locations."""
    found: dict[tuple[str, str], Message] = {}
    for path in sorted(src.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        lines = source.split("\n")           # the way the parser counts (not splitlines: U+2028 …)
        tree = ast.parse(source, str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = node.func.id if isinstance(node.func, ast.Name) else \
                node.func.attr if isinstance(node.func, ast.Attribute) else None
            args = [_text(a) for a in node.args]
            message = None
            if name in ("_", "N_") and len(args) == 1 and args[0] is not None:
                message = Message(args[0])
            elif name in ("pgettext", "NP_") and len(args) == 2 and None not in args:
                message = Message(args[1], context=args[0])
            elif name == "ngettext" and len(args) >= 2 and None not in args[:2]:
                message = Message(args[0], plural=args[1])
            if message is None:
                continue
            place = str(path.relative_to(src.parent.parent))   # without line: stable when refactoring
            number = node.lineno - 2                              # comment directly above
            notes = []
            while number >= 0 and lines[number].strip().startswith("#"):
                notes.insert(0, lines[number].strip().lstrip("#").strip())
                number -= 1
            if any(n.startswith("Translators:") for n in notes):
                note = " ".join(notes[next(i for i, n in enumerate(notes)
                                           if n.startswith("Translators:")):])
                message.notes.append(note)
            known = found.setdefault(message.key, message)
            for note in message.notes:
                if note not in known.notes:
                    known.notes.append(note)
            if place not in known.places:
                known.places.append(place)
            if message.plural and not known.plural:
                known.plural = message.plural
    return found


def _escape(char: str) -> str:
    return {"\\": "\\\\", '"': '\\"', "\t": "\\t", "\r": "\\r"}.get(
        char, f"\\{ord(char):03o}" if ord(char) < 32 and char != "\n" else char)


def _quote(text: str) -> str:
    escaped = "".join(map(_escape, text))
    if "\n" not in escaped:
        return f'"{escaped}"'
    parts = escaped.split("\n")
    lines = [p + "\\n" for p in parts[:-1]] + ([parts[-1]] if parts[-1] else [])
    return '""\n' + "\n".join(f'"{line}"' for line in lines)


def _entry(m: Message, translation: list[str] | None = None, places: bool = True,
           comments: list[str] = (), flags: list[str] = ()) -> str:
    out = [f"# {c}".rstrip() for c in comments]
    if places:
        out += [f"#. {n}" for n in m.notes] + [f"#: {p}" for p in m.places]
    flags = [*flags, *(["python-brace-format"] if m.brace_format else [])]
    if flags:
        out.append("#, " + ", ".join(dict.fromkeys(flags)))
    if m.context:
        out.append(f"msgctxt {_quote(m.context)}")
    out.append(f"msgid {_quote(m.msgid)}")
    if m.plural is not None:
        out.append(f"msgid_plural {_quote(m.plural)}")
        forms = translation or ["", ""]
        out += [f"msgstr[{i}] {_quote(f)}" for i, f in enumerate(forms)]
    else:
        out.append(f"msgstr {_quote((translation or [''])[0])}")
    return "\n".join(out) + "\n"


def pot_text(messages: dict) -> str:
    head = ('msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n'
            '"Plural-Forms: nplurals=2; plural=(n != 1);\\n"\n')
    return head + "".join("\n" + _entry(m) for _, m in sorted(messages.items()))


def po_text(language: str, messages: dict, translations: dict, obsolete: dict,
            raw: dict | None = None, header: str | None = None) -> str:
    """Language file: header (an existing one stays), all texts of the code with translation, comments and
    translators' flags (``raw``), then obsolete ones (``#~``)."""
    head = header or ('msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n'
                      f'"Language: {language}\\n"\n'
                      f'"Plural-Forms: {HEADER.get(language, "nplurals=2; plural=(n != 1);")}\\n"\n')
    raw = raw or {}
    body = "".join("\n" + _entry(m, translations.get(k), comments=raw.get(k, {}).get("comments", []),
                                 flags=[f for f in raw.get(k, {}).get("flags", [])
                                        if f != "python-brace-format"])
                   for k, m in sorted(messages.items()))
    old = "".join("\n" + "\n".join("#~ " + line for line in _entry(m, t, places=False).splitlines())
                  + "\n" for (m, t) in obsolete.values())
    return head + body + old


def read_raw(text: str) -> tuple[str, dict]:
    """Raw entries of a language file, including uncertain and obsolete ones: header (text) and
    (context, text) → {comments, flags, forms, plural, obsolete}."""
    sys.path.insert(0, str(ROOT / "src"))
    from labelwerk.i18n import unquote
    header, entries, block = "", {}, []

    def finish(lines):
        nonlocal header
        if not lines:
            return
        obsolete = all(line.startswith("#~") for line in lines if line.strip())
        lines = [line[2:].strip() if line.startswith("#~") else line for line in lines]
        comments, flags, fields, key = [], [], {}, None
        for line in lines:
            if line.startswith("#,"):
                flags += [f.strip() for f in line[2:].split(",") if f.strip()]
            elif line.startswith("# ") or line == "#":
                comments.append(line[2:])
            elif line.startswith("#"):
                continue                                    # extract rewrites #: and #.
            elif line.startswith('"'):
                fields[key] += unquote(line, "")
            else:
                key, __, value = line.partition(" ")
                fields[key] = unquote(value, "")
        if fields.get("msgid") == "" and "msgctxt" not in fields:
            header = "\n".join(l for l in lines if not l.startswith("#")) + "\n"
            return
        forms = [fields[k] for k in sorted(fields) if k.startswith("msgstr")]
        entries[(fields.get("msgctxt", ""), fields["msgid"])] = {
            "comments": comments, "flags": flags, "forms": forms,
            "plural": fields.get("msgid_plural"), "obsolete": obsolete}

    for line in text.splitlines():
        if not line.strip():
            finish(block)
            block = []
        else:
            block.append(line)
    finish(block)
    return header, entries


def _load(language: str):
    sys.path.insert(0, str(ROOT / "src"))
    from labelwerk.i18n import parse_po
    path = PO_DIR / f"{language}.po"
    return parse_po(path.read_text(encoding="utf-8"), language) if path.exists() else None


def languages() -> list[str]:
    return sorted(p.stem for p in PO_DIR.glob("*.po"))


def placeholders(text: str) -> list[str]:
    """Named placeholders ``{name}``/``{name!r}``/``{name:.1f}`` and %-specifiers of a text."""
    return sorted(re.findall(r"\{[^{}]*\}", text.replace("{{", "").replace("}}", ""))
                  + re.findall(r"%(?:\([a-z_]+\))?[srd]", text))


GERMAN = re.compile(r"[äöüÄÖÜß]|\b(der|das|und|nicht|kein|keine|ist|mit|für|oder|auf|bei|wird|"
                    r"Etikett|Drucker|Datei|Fehler|Bild|Seite|Zeile|Spalte|Rand|Rahmen|Schrift|"
                    r"Größe|Zwischenablage|Bildschirmfoto|Serie|Vorlage|Einstellung)\b")
# German texts that are deliberately not translations (stored/compared): file → texts
GERMAN_OK = {"src/labelwerk/gui/image_import.py": {"Abgelegtes Bild", "Zwischenablage",
                                                   "Bildschirmfoto"}}


def german_leftovers(src: Path = SRC) -> list[str]:
    """German-looking texts outside ``_()`` & co. (without docstrings) – user texts that the
    switch to English missed; exceptions in ``GERMAN_OK``."""
    calls, found = {"_", "N_", "pgettext", "ngettext"}, []
    for path in sorted(src.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        skip = set()
        for node in ast.walk(tree):
            body = getattr(node, "body", None)
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)) \
                    and body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                skip.add(id(body[0].value))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in calls:
                skip.update(id(a) for a in ast.walk(node))
        where = str(path.relative_to(src.parent.parent))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip \
                    and len(node.value) > 2 and GERMAN.search(node.value) \
                    and node.value not in GERMAN_OK.get(where, ()):
                found.append(f"{where}:{node.lineno}: {node.value[:80]!r}")
    return found


def problems(messages: dict | None = None) -> list[str]:
    """What the test checks: .pot up to date, every language complete, placeholders equal."""
    messages = extract() if messages is None else messages
    found = []
    if not POT.exists() or POT.read_text(encoding="utf-8") != pot_text(messages):
        found.append("labelwerk.pot out of date – python tools/i18n.py extract")
    for language in languages():
        catalog = _load(language)
        header = re.search(r"nplurals\s*=\s*(\d+)", (PO_DIR / f"{language}.po").read_text(
            encoding="utf-8-sig"))
        if header is None:
            found.append(f"{language}: header without \"Plural-Forms: nplurals=…\"")
            continue
        nplurals = int(header[1])
        for key, m in sorted(messages.items()):
            forms = catalog.messages.get(key)
            if not forms:
                found.append(f"{language}: missing {m.msgid!r}" + (f" ({m.context})" if m.context else ""))
                continue
            if m.plural is not None and len(forms) != nplurals:
                found.append(f"{language}: {len(forms)} instead of {nplurals} plural forms in {m.msgid!r}")
            for index, form in enumerate(forms):
                original = m.msgid if index == 0 or m.plural is None else m.plural
                if set(placeholders(form)) != set(placeholders(original)):
                    found.append(f"{language}: placeholders differ in {m.msgid!r}: {form!r}")
    return found


def update() -> None:
    """New template; every language file: new texts added (empty), existing translations along with
    comments and flags (fuzzy) stay, dropped ones become obsolete (``#~``)."""
    messages = extract()
    POT.write_text(pot_text(messages), encoding="utf-8")
    for language in languages():
        path = PO_DIR / f"{language}.po"
        header, raw = read_raw(path.read_text(encoding="utf-8-sig"))
        translations = {k: e["forms"] for k, e in raw.items() if k in messages and any(e["forms"])}
        obsolete = {k: (Message(k[1], plural=e["plural"], context=k[0]), e["forms"])
                    for k, e in raw.items() if k not in messages and any(e["forms"])}
        path.write_text(po_text(language, messages, translations, obsolete, raw, header or None),
                        encoding="utf-8")


def main(argv: list[str]) -> int:
    command = argv[0] if argv else "check"
    if command == "extract":
        POT.write_text(pot_text(extract()), encoding="utf-8")
        print(f"written: {POT}")
        return 0
    if command == "update":
        update()
        print("updated: " + ", ".join([POT.name, *(f"{lang}.po" for lang in languages())]))
        return 0
    found = problems()
    print("\n".join(found) if found else "complete")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
