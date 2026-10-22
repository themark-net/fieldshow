"""Part PDFs written by `fieldshow build`, and the page that links them.

The engraving checks run the real LilyPond when it is installed and skip, with
the image command, when it is not. The failure checks use no engraver.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fieldshow.model import SECTION_ORDER, load_show
from fieldshow.music.engrave import find_lilypond, find_musicxml2ly
from fieldshow.web.app import create_app

ROOT = Path(__file__).resolve().parents[1]
DOCKER_PYTEST = (
    "docker build -t fieldshow:t0005 . && "
    'docker run --rm -v "$PWD:/work" -w /work -e HOME=/tmp fieldshow:t0005 '
    'sh -c \'pip install --no-cache-dir -e ".[dev]" && pytest\''
)


def _require_engraver() -> None:
    if find_lilypond() and find_musicxml2ly():
        return
    pytest.skip(
        "LilyPond not found (set FIELDSHOW_ENGRAVER and FIELDSHOW_MUSICXML2LY). "
        f"Run this test in the image: {DOCKER_PYTEST}"
    )


def _page_count(path: Path) -> int:
    pdfinfo = shutil.which("pdfinfo")
    if pdfinfo:
        proc = subprocess.run(
            [pdfinfo, str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0:
            for line in proc.stdout.splitlines():
                if line.startswith("Pages:"):
                    return int(line.split()[1])
    return len(re.findall(rb"/Type\s*/Page(?!s)", path.read_bytes()))


def _build(out: Path, env: dict) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "fieldshow",
            "build",
            str(ROOT / "examples" / "fanfare.json"),
            "-o",
            str(out),
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture(scope="module")
def engraved(tmp_path_factory: pytest.TempPathFactory) -> Path:
    _require_engraver()
    out = tmp_path_factory.mktemp("engraved") / "show.json"
    result = _build(out, os.environ.copy())
    assert result.returncode == 0, result.stderr
    return out


def test_build_writes_one_real_pdf_per_part(engraved: Path):
    show = json.loads(engraved.read_text())
    assert set(show["part_pdfs"]) == set(SECTION_ORDER)
    pdfs = sorted((engraved.parent / "parts").glob("*.pdf"))
    assert [path.stem for path in pdfs] == sorted(SECTION_ORDER)
    for section in SECTION_ORDER:
        assert show["part_pdfs"][section] == f"parts/{section}.pdf"
        path = engraved.parent / show["part_pdfs"][section]
        data = path.read_bytes()
        assert data.startswith(b"%PDF")
        assert len(data) > 1000
        assert _page_count(path) >= 1
    assert not show.get("engrave_error")


def test_page_links_each_part_pdf(engraved: Path):
    client = TestClient(create_app(load_show(engraved), show_path=engraved))
    page = client.get("/")
    assert page.status_code == 200
    for section in SECTION_ORDER:
        assert f'href="/api/part-pdf/{section}"' in page.text
        response = client.get(f"/api/part-pdf/{section}")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/pdf")
        assert response.content.startswith(b"%PDF")
        assert len(response.content) > 1000


def test_missing_engraver_builds_and_page_marks_parts_unavailable(tmp_path: Path):
    out = tmp_path / "show.json"
    env = os.environ.copy()
    missing = str(tmp_path / "missing-lilypond")
    env["FIELDSHOW_ENGRAVER"] = missing
    env["FIELDSHOW_LILYPOND"] = missing
    result = _build(out, env)
    assert result.returncode == 0, result.stderr
    assert "PDF parts unavailable: LilyPond not found (set FIELDSHOW_ENGRAVER)" in result.stderr
    show = json.loads(out.read_text())
    assert show["parts"]["trumpet"][0] == "C5"
    assert show["part_pdfs"] == {section: None for section in SECTION_ORDER}
    assert "LilyPond not found" in show["engrave_error"]
    assert list(tmp_path.rglob("*.pdf")) == []
    client = TestClient(create_app(show, show_path=out))
    page = client.get("/").text
    assert "unavailable" in page
    assert "LilyPond not found" in page
    assert 'href="/api/part-pdf/' not in page
    for section in SECTION_ORDER:
        assert client.get(f"/api/part-pdf/{section}").status_code == 404
    assert client.get("/api/part-pdf/not-a-part").status_code == 404


def test_engraver_nonzero_exit_marks_parts_unavailable(tmp_path: Path):
    converter = tmp_path / "musicxml2ly"
    converter.write_text(
        "#!/bin/sh\n"
        "out=\n"
        "while [ $# -gt 0 ]; do\n"
        '  if [ "$1" = "-o" ]; then out=$2; shift 2; continue; fi\n'
        "  shift\n"
        "done\n"
        "printf '%s\\n' '% not lilypond' > \"$out\"\n"
        "exit 0\n"
    )
    lilypond = tmp_path / "lilypond"
    lilypond.write_text("#!/bin/sh\necho 'fake lilypond failed' >&2\nexit 4\n")
    converter.chmod(0o755)
    lilypond.chmod(0o755)
    out = tmp_path / "show.json"
    env = os.environ.copy()
    env["FIELDSHOW_ENGRAVER"] = str(lilypond)
    env["FIELDSHOW_MUSICXML2LY"] = str(converter)
    result = _build(out, env)
    assert result.returncode == 0, result.stderr
    assert "lilypond exited 4" in result.stderr
    assert "fake lilypond failed" in result.stderr
    show = json.loads(out.read_text())
    assert show["parts"]["flute"][0] == "Bb4"
    assert all(value is None for value in show["part_pdfs"].values())
    assert "lilypond exited 4" in show["engrave_error"]
    assert list(tmp_path.rglob("*.pdf")) == []
