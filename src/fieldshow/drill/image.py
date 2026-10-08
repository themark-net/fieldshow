"""Attach a field picture to a show. No vision. The agent reads the picture."""

from __future__ import annotations

import shutil
from pathlib import Path


def import_image(show: dict, src: str | Path, assets_dir: str | Path) -> dict:
    source = Path(src)
    if not source.is_file():
        raise FileNotFoundError(src)
    if source.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        raise ValueError("field image must be png, jpg, webp, or gif")
    dest_dir = Path(assets_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"field{source.suffix.lower()}"
    shutil.copyfile(source, dest)
    show["field_image"] = dest.as_posix()
    return show
