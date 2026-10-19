"""Arbeitsordner der Pflege-Werkzeuge: Testblätter, umgewandelte Ergebnisse und alle Ausgaben liegen
dort – nie im Repository (echte Marken enthalten Namen und Adressen)."""
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def workdir(argument: str | None = None) -> Path:
    """Ordner aus ``argument`` bzw. ``$LABELWERK_PARCEL_DIR``; fehlt er oder liegt er im Repository,
    bricht das Werkzeug mit einer Meldung ab."""
    value = argument or os.environ.get("LABELWERK_PARCEL_DIR")
    if not value:
        sys.exit("Arbeitsordner fehlt: LABELWERK_PARCEL_DIR=ordner setzen (außerhalb des Repositorys).")
    path = Path(value).expanduser().resolve()
    if path == REPO or REPO in path.parents:
        sys.exit(f"{path} liegt im Repository – Ausgaben und Marken gehören nicht hinein.")
    path.mkdir(parents=True, exist_ok=True)
    return path
