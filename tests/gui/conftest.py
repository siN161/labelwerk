import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    import PySide6  # noqa: F401
except ImportError:  # reine CLI-Umgebung: GUI-Tests überspringen
    collect_ignore_glob = ["test_*.py"]
