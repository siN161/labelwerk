"""Printers via CUPS (the Linux print system) – without Qt and without an extra library: only the
commands ``lpstat``, ``lpoptions`` and ``lp``.

Label sizes and resolution come from the driver (PPD: ``*PaperDimension``,
``*DefaultResolution``), otherwise from the size names (``lpoptions -l``: “62x29mm”, “w288h432”
in points), otherwise from a per-manufacturer list (Dymo, Zebra). Cut options are the
driver options with “Cut” in the name. Office printers (paper sizes A4, Letter …) are recognised from
the queue list so that the printer menu can hide them. Every call has a time limit, messages come in
English (``LC_MESSAGES=C``, names stay UTF-8); errors become the translated ``CupsError``. A background
thread polls the queue list – the UI never waits for CUPS.
"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, field, replace
from pathlib import Path

from PIL import Image

from .i18n import _
from .labels import DPI, DPI_RANGE, SIZE_MM, sized_id

PREFIX = "cups:"
PPD_DIR = Path("/etc/cups/ppd")            # tests set an empty directory
TIMEOUT_S = 5
PRINT_TIMEOUT_S = 120                      # lp uploads a whole series
QUEUE_MAX_AGE_S = 30                       # reuse the queue list for this long
INFO_MAX_AGE_S = 300                       # driver information of a queue likewise
FAILED_MAX_AGE_S = 30                      # … without an answer from CUPS only briefly (no waiting each time)
BACKGROUND = True                          # read the list in the background (tests: immediately)
# Name of a queue (CUPS: printable, no spaces, /, \, #, quotation marks)
_QUEUE_NAME = re.compile(r"[^\s/\\#'\"-][^\s/\\#'\"]{0,126}")
# Cut option: “Cut…” as a word or in CamelCase (“DymoCutOptions”), “Schneiden”/“Schnitt…” –
# not “Execute”, not “Schnittstelle”
_CUT = re.compile(r"(?:\b[Cc]ut|(?<=[a-z])Cut|\b[Ss]chn(?:itt|eid))(?!stelle)")
# Paper size of an office printer (``PageSize``): A3–A5, B5, Letter, Legal, Executive, Tabloid/Ledger,
# also as IPP name (“iso_a4_210x297mm”, “na_letter_8.5x11in”) and with a suffix (“A4.Borderless”,
# “A4Small”) – not A6 (shipping label) and not “A40”
_OFFICE = re.compile(r"(?:iso_|na_|jis_)?(?:a[345]|b5|letter|legal|executive|tabloid|ledger)(?!\d)",
                     re.I)
PT_MM = 25.4 / 72
# Fallback: common labels per manufacturer (width, height in mm)
MEDIA_LISTS = {
    "dymo": ((89, 28), (89, 36), (54, 25), (54, 101), (57, 32), (59, 102), (25, 25), (19, 51),
             (32, 57), (36, 89)),
    "zebra": ((51, 25), (57, 32), (76, 51), (102, 51), (102, 76), (102, 102), (102, 152),
              (38, 25), (60, 40)),
}
COMMON = ((57, 32), (54, 25), (89, 36), (102, 51), (102, 152), (51, 25))   # unknown manufacturer


class CupsError(Exception):
    """CUPS command failed (message for the user)."""


@dataclass(frozen=True)
class Queue:
    """A queue: name and device URI (e.g. usb://DYMO/LabelWriter%20450);
    ``office``: office printer (paper sizes like A4/Letter), None = unknown (CUPS gave no answer)."""
    name: str
    device: str = ""
    office: bool | None = None


@dataclass(frozen=True)
class CutOption:
    """Driver cut option: key, title and values (like ``lpoptions -l``);
    ``labels``: display of the values (otherwise the values themselves)."""
    key: str
    title: str
    choices: tuple[str, ...]
    default: str
    labels: tuple[str, ...] = ()


@dataclass(frozen=True)
class QueueInfo:
    """What the driver says about labels: sizes (key for ``lp``, width, height in mm),
    resolution, cut options; ``source`` where the sizes come from (ppd, options, list)."""
    media: tuple[tuple[str, float, float], ...]
    dpi: int
    cut_options: tuple[CutOption, ...] = ()
    source: str = "ppd"

    def label_ids(self) -> list[str]:
        ids = []
        for __, w, h in self.media:
            label_id = sized_id(w, h, self.dpi)
            if label_id not in ids:
                ids.append(label_id)
        return ids

    def media_key(self, w_mm: float, h_mm: float) -> str:
        """Driver size key for a label, otherwise a custom size."""
        for key, w, h in self.media:
            if abs(w - w_mm) <= 0.15 and abs(h - h_mm) <= 0.15:
                return key
        return f"Custom.{w_mm:g}x{h_mm:g}mm"


def valid_name(name) -> bool:
    """Valid queue name (also protects against paths and options in calls)."""
    return isinstance(name, str) and _QUEUE_NAME.fullmatch(name) is not None


def _environment() -> dict[str, str]:
    """Environment for CUPS commands: messages in English (readable the same way), charset stays."""
    env = {k: v for k, v in os.environ.items() if k not in ("LC_ALL", "LANGUAGE")}
    if "UTF-8" not in (env.get("LC_CTYPE") or env.get("LANG") or "").upper().replace("UTF8", "UTF-8"):
        env["LC_CTYPE"] = "C.UTF-8"
    env["LC_MESSAGES"] = "C"
    return env


def _run(*args: str, timeout: float = TIMEOUT_S) -> str:
    """CUPS command with time limit; output as text."""
    try:
        done = subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                              check=False, env=_environment())
    except FileNotFoundError:
        raise CupsError(_("CUPS commands missing (install the package cups-client)")) from None
    except subprocess.TimeoutExpired:
        raise CupsError(_("CUPS does not answer ({command})").format(command=args[0])) from None
    if done.returncode != 0:
        reason = (done.stderr or done.stdout).strip().splitlines()
        raise CupsError(_("CUPS: {reason}").format(reason=reason[-1]) if reason
                        else _("CUPS: {command} failed").format(command=args[0]))
    return done.stdout


_lock = threading.Lock()
_queues_cache: tuple[float | None, list[Queue]] = (None, [])
_queues_thread: threading.Thread | None = None
_info_cache: dict[str, tuple[float, QueueInfo]] = {}
# time, office printer, whether it answered, last question answered
_office_cache: dict[str, tuple[float, bool | None, bool, bool]] = {}


def read_queues(classify: bool = True) -> list[Queue]:
    """Configured queues (``lpstat -e``, devices from ``lpstat -v``; ``classify``:
    classify office printers, ``office``) – waits for CUPS; without CUPS none, without a device list
    without devices."""
    try:
        names = [n.strip() for n in _run("lpstat", "-e").splitlines() if valid_name(n.strip())]
    except CupsError:
        return []
    devices = {}
    try:
        for line in _run("lpstat", "-v").splitlines():
            m = re.search(r"(\S+):\s+(\S+:/\S*)\s*$", line)      # "device for X:", "Gerät für X:"
            if m:
                devices[m[1]] = m[2]
    except CupsError:
        pass
    office = _classify(names) if classify else {}
    return [Queue(n, devices.get(n, ""), office.get(n)) for n in names]


def is_office(default: str) -> bool | None:
    """Office printer by the driver's default paper size: A4, Letter … (even if a label printer
    has A4 in its list, e.g. the Zebra driver of CUPS, its default is a label); unknown (None)
    without a default."""
    return bool(_OFFICE.match(default)) if default else None


def _default_size(name: str) -> str:
    """Default paper size of a queue: from the PPD (``*DefaultPageSize``), otherwise
    ``lpoptions`` (value with “*”); ``CupsError`` without an answer."""
    try:
        if not valid_name(name):
            raise OSError("invalid queue name")      # internal, never shown
        m = re.search(r"^\*DefaultPageSize:\s*(\S+)", (PPD_DIR / f"{name}.ppd").read_text(
            errors="replace"), re.M)
        if m:
            return m[1]
    except OSError:                                  # not readable (permissions) or no PPD
        pass
    options = _options(name)
    return options["PageSize"][2] if _choices(options, "PageSize") else ""


def _classify(names: list[str]) -> dict[str, bool | None]:
    """``is_office`` per queue; remembered (``INFO_MAX_AGE_S``, without an answer
    ``FAILED_MAX_AGE_S``). Unremembered ones are asked by one thread each, all together at most
    ``TIMEOUT_S`` long – whoever has not answered by then is unknown (None); its answer counts on
    the next read."""
    now, result, ask = time.monotonic(), {}, []
    with _lock:
        for name in names:
            stamp, office, __, fresh = _office_cache.get(name, (None, None, False, False))
            if stamp is not None and now - stamp < (INFO_MAX_AGE_S if fresh
                                                    else FAILED_MAX_AGE_S):
                result[name] = office
            else:
                ask.append(name)
    threads = [threading.Thread(target=_classify_one, args=(name,), daemon=True) for name in ask]
    for thread in threads:
        thread.start()
    deadline = now + TIMEOUT_S
    for thread in threads:
        thread.join(max(0.0, deadline - time.monotonic()))
    with _lock:
        for name in ask:
            stamp, office, __, __ = _office_cache.get(name, (None, None, False, False))
            if stamp is None or stamp < now:          # not in time
                office = _unanswered(name, now)
            result[name] = office
    return result


def _classify_one(name: str) -> None:
    try:
        office = is_office(_default_size(name))
    except CupsError:
        with _lock:
            _unanswered(name, time.monotonic())
        return
    with _lock:
        _office_cache[name] = (time.monotonic(), office, True, True)


def _unanswered(name: str, now: float) -> bool | None:
    """No answer (time limit, error) – under ``_lock``: a previously known value stays (an
    office printer does not briefly appear in the menu), it is asked again after
    ``FAILED_MAX_AGE_S`` as with no answer; without an earlier answer unknown (None)."""
    __, office, answered, __ = _office_cache.get(name, (None, None, False, False))
    _office_cache[name] = (now, office if answered else None, answered, False)
    return office if answered else None


def queues(max_age: float = QUEUE_MAX_AGE_S, wait: bool = False,
           classify: bool = True) -> list[Queue]:
    """Queues as last read (at most ``max_age`` seconds old); if the list is
    older, a background thread re-reads it – ``queues()`` does not wait (the GUI asks every
    2 s; the first call returns none yet). ``wait``: re-read and wait (CLI);
    ``classify``: classify office printers (the background thread always does)."""
    global _queues_cache, _queues_thread
    if wait or not BACKGROUND:
        found = read_queues(classify)
        with _lock:
            _queues_cache = (time.monotonic(), found)
        return list(found)
    with _lock:
        stamp, cached = _queues_cache
        stale = stamp is None or time.monotonic() - stamp >= max_age
        if stale and (_queues_thread is None or not _queues_thread.is_alive()):
            _queues_thread = threading.Thread(target=_refresh_queues, daemon=True)
            _queues_thread.start()
        return list(cached)


def _refresh_queues() -> None:
    global _queues_cache
    found = read_queues()
    with _lock:
        _queues_cache = (time.monotonic(), found)


def forget() -> None:
    """Discard remembered queues and driver information (e.g. new queue)."""
    global _queues_cache
    with _lock:
        _queues_cache = (None, [])
        _info_cache.clear()
        _office_cache.clear()


def queue_info(name: str) -> QueueInfo:
    """Labels, resolution and cut options of a queue; remembered (``INFO_MAX_AGE_S``),
    if CUPS did not answer, the per-manufacturer list applies for ``FAILED_MAX_AGE_S``, then
    it is asked again. Waits for CUPS – only when choosing the printer."""
    with _lock:
        stamp, info = _info_cache.get(name, (None, None))
    if info is not None and time.monotonic() - stamp < (
            INFO_MAX_AGE_S if info.source != "failed" else FAILED_MAX_AGE_S):
        return info if info.source != "failed" else replace(info, source="list")
    try:
        options = _options(name) if valid_name(name) else {}
        answered = valid_name(name)
    except CupsError:
        options, answered = {}, False
    info = _queue_info(name, options)
    with _lock:                             # without an answer: remember briefly, then ask again
        _info_cache[name] = (time.monotonic(), info if answered else replace(info, source="failed"))
    return info


def _queue_info(name: str, options: dict) -> QueueInfo:
    dpi, media, source = DPI, (), "list"
    try:
        if not valid_name(name):
            raise OSError("invalid queue name")      # internal, never shown
        dpi, media = _parse_ppd((PPD_DIR / f"{name}.ppd").read_text(errors="replace"))
        source = "ppd"
    except OSError:                        # not readable (permissions) or no PPD
        dpi = _option_dpi(options) or DPI
        media = tuple(m for m in (_media_from_key(k) for k in _choices(options, "PageSize")) if m)
        source = "options" if media else "list"
    if not media:
        maker = next((m for m in MEDIA_LISTS if m in name.lower()), None)
        media = tuple((f"Custom.{w}x{h}mm", float(w), float(h))
                      for w, h in MEDIA_LISTS.get(maker, COMMON))
        source = "list"
    cuts = tuple(_cut_options(options))
    return QueueInfo(media, dpi, cuts, source)


def _options(name: str) -> dict[str, tuple[str, list[str], str]]:
    """``lpoptions -p NAME -l``: key → (title, values, default); CUPS does not answer →
    ``CupsError``."""
    text = _run("lpoptions", "-p", name, "-l")
    out = {}
    for line in text.splitlines():
        head, sep, values = line.partition(":")
        if not sep:
            continue
        key, __, title = head.partition("/")
        choices = values.split()
        default = next((c[1:] for c in choices if c.startswith("*")), choices[0] if choices else "")
        out[key.strip()] = (title.strip() or key.strip(), [c.lstrip("*") for c in choices], default)
    return out


def _choices(options: dict, key: str) -> list[str]:
    return options.get(key, ("", [], ""))[1]


def _option_dpi(options: dict) -> int | None:
    entry = options.get("Resolution")
    if entry is None:
        return None
    return _dpi(entry[2])


def _dpi(text: str) -> int | None:
    m = re.match(r"\s*(\d+)(?:x\d+)?\s*dpi", text)
    if not m:
        return None
    value = int(m[1])
    return value if DPI_RANGE[0] <= value <= DPI_RANGE[1] else None


def _parse_ppd(text: str) -> tuple[int, tuple[tuple[str, float, float], ...]]:
    """Resolution (``*DefaultResolution``) and sizes (``*PaperDimension Name/Text: "w h"`` in points)
    of a PPD; only fixed labels within the limits."""
    dpi = DPI
    m = re.search(r'^\*DefaultResolution:\s*(\S+)', text, re.M)
    if m:
        dpi = _dpi(m[1]) or DPI
    media = []
    for key, w, h in re.findall(r'^\*PaperDimension\s+([^/:\s]+)[^:]*:\s*"\s*([\d.]+)\s+([\d.]+)\s*"',
                                text, re.M):
        w_mm, h_mm = round(float(w) * PT_MM, 1), round(float(h) * PT_MM, 1)
        if SIZE_MM[0] <= w_mm <= SIZE_MM[1] and SIZE_MM[0] <= h_mm <= SIZE_MM[1]:
            media.append((key, w_mm, h_mm))
    return dpi, tuple(media)


def _media_from_key(key: str) -> tuple[str, float, float] | None:
    """Size from a name: “62x29mm”, “w288h432” (points), “4x6in”; otherwise None."""
    if (m := re.fullmatch(r"(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)mm", key)):
        w, h = float(m[1]), float(m[2])
    elif (m := re.fullmatch(r"w(\d+(?:\.\d+)?)h(\d+(?:\.\d+)?)", key)):
        w, h = float(m[1]) * PT_MM, float(m[2]) * PT_MM
    elif (m := re.fullmatch(r"(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)in", key)):
        w, h = float(m[1]) * 25.4, float(m[2]) * 25.4
    else:
        return None
    w, h = round(w, 1), round(h, 1)
    if not (SIZE_MM[0] <= w <= SIZE_MM[1] and SIZE_MM[0] <= h <= SIZE_MM[1]):
        return None
    return key, w, h


def _cut_options(options: dict) -> list[CutOption]:
    """Driver options for cutting (name or title contains “cut”/“schnitt”)."""
    return [CutOption(key, title, tuple(choices), default)
            for key, (title, choices, default) in options.items()
            if key != "PageSize" and _CUT.search(f"{key} {title}") and choices]


@dataclass
class Job:
    """Submitted job (``lp``): ID like “Dymo-12”, pages (labels)."""
    id: str
    pages: int = field(default=1)


def print_images(name: str, images: list[Image.Image], w_mm: float, h_mm: float, dpi: int,
                 options: dict[str, str] | None = None) -> Job:
    """Labels as one job to the queue ``name``: a PDF with one page per label
    at ``dpi`` (page = label, 1:1 – no fitting or rotating), driver size or
    custom, plus ``options`` (e.g. cut). Returns the job ID."""
    if not valid_name(name):
        raise CupsError(_("Invalid queue name: {name!r}").format(name=name))
    info = queue_info(name)
    key = info.media_key(w_mm, h_mm)
    with tempfile.TemporaryDirectory(prefix="labelwerk-") as folder:
        path = Path(folder) / "etiketten.pdf"
        first, *rest = [image.convert("1") for image in images]
        first.save(path, "PDF", resolution=dpi, save_all=True, append_images=rest)
        args = ["lp", "-d", name, "-o", f"media={key}", "-o", "print-scaling=none",
                "-o", "orientation-requested=3", "-o", "fit-to-page=false"]
        if not key.startswith("Custom."):                # driver size: also as PageSize
            args += ["-o", f"PageSize={key}"]
        for option, value in (options or {}).items():
            args += ["-o", f"{option}={value}"]
        answer = _run(*args, "--", str(path), timeout=PRINT_TIMEOUT_S)
    m = re.search(r"\b(\S+-\d+)\b", answer)                   # "request id is X-12", "Anfrage-ID ist X-12"
    return Job(m[1] if m else name, len(images))
