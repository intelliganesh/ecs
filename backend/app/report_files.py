from contextlib import contextmanager
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from app.core.config import BACKEND_DIR
from app.retirement_results import MAX_SOURCE_BYTES, InvalidRun


@contextmanager
def publish_report(path: Path, csv: str):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = NamedTemporaryFile(dir=path.parent, delete=False)
    temporary_path = Path(temporary.name)
    try:
        with temporary:
            temporary.write(csv.encode("utf-8"))
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)
    try:
        yield
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def report_directory(directory: Path) -> Path:
    return BACKEND_DIR / directory


def load_report_source(input_dir: Path, job_id: int) -> bytes:
    path = report_directory(input_dir) / f"{job_id}.csv"
    try:
        with path.open("rb") as source:
            data = source.read(MAX_SOURCE_BYTES + 1)
    except FileNotFoundError as exc:
        raise InvalidRun(f"Source CSV missing. Place {path.name} in the configured report input folder.") from exc
    except OSError as exc:
        raise InvalidRun(f"Could not read {path.name} in the configured report input folder.") from exc
    if len(data) > MAX_SOURCE_BYTES:
        raise InvalidRun(f"The source CSV {path.name} must be 5 MB or smaller.")
    return data
