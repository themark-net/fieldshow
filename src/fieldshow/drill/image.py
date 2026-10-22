"""Attach a field picture to a show. No vision. The agent reads the picture."""

from __future__ import annotations

import shutil
from pathlib import Path

from fieldshow.model import FIELD_IMAGE_SUFFIXES


def import_image(show: dict, src: str | Path, base_dir: str | Path) -> dict:
    """Copy ``src`` to ``<base_dir>/images/field.<ext>`` and store ``images/field.<ext>``.

    ``field_image`` is always that relative marker, never the source path.
    """
    source = Path(src)
    if not source.is_file():
        raise FileNotFoundError(src)
    suffix = source.suffix.lower()
    if suffix not in FIELD_IMAGE_SUFFIXES:
        raise ValueError("field image must be png, jpg, webp, or gif")
    dest_dir = Path(base_dir) / "images"
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = f"field{suffix}"
    shutil.copyfile(source, dest_dir / name)
    show["field_image"] = f"images/{name}"
    return show
