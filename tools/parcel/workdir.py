"""Working folder of the maintenance tools: test sheets, converted results and all outputs live
there – never in the repository (real parcel labels contain names and addresses)."""
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def workdir(argument: str | None = None) -> Path:
    """Folder from ``argument`` or ``$LABELWERK_PARCEL_DIR``; if it is missing or lies in the repository,
    the tool aborts with a message."""
    value = argument or os.environ.get("LABELWERK_PARCEL_DIR")
    if not value:
        sys.exit("Working folder missing: set LABELWERK_PARCEL_DIR=folder (outside the repository).")
    path = Path(value).expanduser().resolve()
    if path == REPO or REPO in path.parents:
        sys.exit(f"{path} is inside the repository – outputs and parcel labels do not belong there.")
    path.mkdir(parents=True, exist_ok=True)
    return path
