"""Part PDFs written by `fieldshow build`, and the page that links them.

The engraving checks run the real LilyPond when it is installed and skip, with
the image command, when it is not. Failure, route, and timeout checks use no
real engraver.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fieldshow.model import SECTION_ORDER, load_show
from fieldshow.music.arrange import arrange
from fieldshow.music.engrave import find_lilypond, find_musicxml2ly
from fieldshow.music.io import PART_NAMES, export_musicxml
from fieldshow.web.app import create_app

ROOT = Path(__file__).resolve().parents[1]
DOCKER_PYTEST = (
    "docker build -t fieldshow:t0005 . && "
    'docker run --rm -v "$PWD:/work" -w /work -e HOME=/tmp --user "$(id -u):$(id -g)" fieldshow:t0005 '
    'sh -c \'python -m venv /tmp/v --system-site-packages && . /tmp/v/bin/activate && '
    'pip install -q --no-cache-dir -e ".[dev]" && pytest\''
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


def _pdf_text(path: Path) -> str:
    pdftotext = shutil.which("pdftotext")
    if not pdftotext:
        pytest.fail("pdftotext is not installed (poppler-utils)")
    proc = subprocess.run(
        [pdftotext, "-layout", str(path), "-"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


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


def _paper_items(html: str) -> list[str]:
    chunk = html.split('id="paper"', 1)[1]
    chunk = chunk.split("</ul>", 1)[0]
    return re.findall(r"<li\b.*?</li>", chunk, flags=re.DOTALL)


def _converter_script() -> str:
    return (
        "#!/bin/sh\n"
        "out=\n"
        "while [ $# -gt 0 ]; do\n"
        '  if [ "$1" = "-o" ]; then out=$2; shift 2; continue; fi\n'
        "  shift\n"
        "done\n"
        "printf '%s\\n' '% not lilypond' > \"$out\"\n"
        "exit 0\n"
    )


def _write_exec(path: Path, text: str) -> None:
    path.write_text(text)
    path.chmod(0o755)


def _fake_tools(directory: Path, lilypond: str) -> dict[str, str]:
    directory.mkdir(parents=True, exist_ok=True)
    converter = directory / "musicxml2ly"
    engraver = directory / "lilypond"
    _write_exec(converter, _converter_script())
    _write_exec(engraver, lilypond)
    env = os.environ.copy()
    env["FIELDSHOW_ENGRAVER"] = str(engraver)
    env["FIELDSHOW_LILYPOND"] = str(engraver)
    env["FIELDSHOW_MUSICXML2LY"] = str(converter)
    return env


def _gone(pid: int) -> bool:
    """True when the pid is reaped or is only a zombie."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except PermissionError:
        return False
    status = Path(f"/proc/{pid}/status")
    if not status.exists():
        return True
    try:
        text = status.read_text()
    except OSError:
        return True
    for line in text.splitlines():
        if line.startswith("State:"):
            return line.split()[1].startswith("Z")
    return False


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
    bodies = []
    texts = {}
    for section in SECTION_ORDER:
        assert show["part_pdfs"][section] == f"parts/{section}.pdf"
        path = engraved.parent / show["part_pdfs"][section]
        data = path.read_bytes()
        assert data.startswith(b"%PDF")
        assert len(data) > 1000
        assert _page_count(path) >= 1
        bodies.append(data)
        text = _pdf_text(path)
        texts[section] = text
        own = PART_NAMES[section]
        assert own in text
        for other, name in PART_NAMES.items():
            if other == section or name in own or own in name:
                continue
            assert name not in text
    assert len(set(bodies)) == len(SECTION_ORDER)
    assert texts["flute"] != texts["tuba"]
    assert texts["trumpet"] != texts["snare"]
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
        disk = (engraved.parent / "parts" / f"{section}.pdf").read_bytes()
        assert response.content == disk
        assert disk.startswith(b"%PDF")
        assert len(disk) > 1000


def test_export_parts_start_at_offset_zero(tmp_path: Path):
    """Gate Fanfare parts share a timeline. Score.append pads hidden measures."""
    show = arrange(load_show(ROOT / "examples" / "fanfare.json"))
    dest = tmp_path / "fanfare.musicxml"
    export_musicxml(show, dest)
    xml = dest.read_text()
    assert 'print-object="no"' not in xml
    part_chunks = re.findall(r"<part\b.*?</part>", xml, flags=re.DOTALL)
    assert len(part_chunks) == len(SECTION_ORDER)
    for chunk in part_chunks:
        assert len(re.findall(r"<measure\b", chunk)) == 2

    from music21 import converter

    score = converter.parse(str(dest))
    assert len(list(score.parts)) == len(SECTION_ORDER)
    for part in score.parts:
        measures = list(part.getElementsByClass("Measure"))
        notes = list(part.flatten().notes)
        first = notes[0].getOffsetBySite(part.flatten()) if notes else None
        assert len(measures) == 2
        assert first in (0, 0.0)
        assert notes


def test_missing_engraver_builds_and_page_marks_parts_unavailable(tmp_path: Path):
    parts = tmp_path / "parts"
    parts.mkdir()
    for section in SECTION_ORDER:
        (parts / f"{section}.pdf").write_bytes(b"%PDF-1.4\n%stale\n")
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
    assert page.count("LilyPond not found") == 1
    assert "unavailable: PDF parts unavailable" not in page
    assert 'href="/api/part-pdf/' not in page
    for section in SECTION_ORDER:
        assert client.get(f"/api/part-pdf/{section}").status_code == 404
    assert client.get("/api/part-pdf/not-a-part").status_code == 404


def _exit_4_lilypond() -> str:
    return (
        "#!/bin/sh\n"
        "out=\n"
        "while [ $# -gt 0 ]; do\n"
        '  if [ "$1" = "-o" ]; then out=$2; shift 2; continue; fi\n'
        "  shift\n"
        "done\n"
        "printf '%s\\n' '%PDF-1.4 fake' > \"${out}.pdf\"\n"
        "echo 'fake lilypond failed /tmp/fieldshow-engrave-leak' >&2\n"
        "exit 4\n"
    )


def _build_exit_4(tmp_path: Path) -> tuple[Path, subprocess.CompletedProcess[str], dict]:
    for section in SECTION_ORDER:
        dest = tmp_path / "parts" / f"{section}.pdf"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"%PDF-1.4\n%stale-before-failure\n")
    out = tmp_path / "show.json"
    env = _fake_tools(tmp_path / "bin", _exit_4_lilypond())
    result = _build(out, env)
    show = json.loads(out.read_text())
    return out, result, show


def test_lilypond_exit_status_discards_the_pdf_it_wrote(tmp_path: Path):
    out, result, show = _build_exit_4(tmp_path)
    assert result.returncode == 0, result.stderr
    assert "lilypond exited 4" in result.stderr
    assert "fake lilypond failed" in result.stderr
    assert "/tmp/fieldshow-engrave-leak" in result.stderr
    assert show["parts"]["flute"][0] == "Bb4"
    assert all(value is None for value in show["part_pdfs"].values())
    assert "lilypond exited 4" in show["engrave_error"]
    assert "/tmp/fieldshow-engrave-leak" in show["engrave_error"]
    assert list(out.parent.rglob("*.pdf")) == []
    for section in SECTION_ORDER:
        assert show["part_errors"][section] == "lilypond exited 4"


def test_failed_engrave_page_shows_only_the_short_reason(tmp_path: Path):
    out, result, show = _build_exit_4(tmp_path)
    assert result.returncode == 0, result.stderr
    client = TestClient(create_app(show, show_path=out))
    page = client.get("/").text
    assert "/tmp/" not in page
    assert "fieldshow-engrave-" not in page
    items = _paper_items(page)
    assert len(items) == len(SECTION_ORDER)
    for item in items:
        assert len(item) < 200
        assert "lilypond exited 4" in item
        assert "/tmp/" not in item
        assert "fieldshow-engrave-" not in item
    for section in SECTION_ORDER:
        assert client.get(f"/api/part-pdf/{section}").status_code == 404


def test_part_pdf_route_rejects_null_tamper_and_escape(tmp_path: Path):
    show = load_show(ROOT / "examples" / "fanfare.json")
    show["part_pdfs"] = {section: None for section in SECTION_ORDER}
    show["engrave_error"] = None
    parts = tmp_path / "parts"
    parts.mkdir()
    good = b"%PDF-1.4\n%baritone-good\n"
    (parts / "baritone.pdf").write_bytes(good)
    show["part_pdfs"]["baritone"] = "parts/baritone.pdf"
    (parts / "trumpet.pdf").write_bytes(b"%PDF-1.4\n%trumpet-on-disk\n")
    show["part_pdfs"]["trumpet"] = None
    (parts / "snare.pdf").write_bytes(b"%PDF-1.4\n%snare-real\n")
    show["part_pdfs"]["snare"] = "show.json"
    (parts / "flute.pdf").write_bytes(b"%PDF-1.4\n%flute-real\n")
    show["part_pdfs"]["flute"] = "../x"
    (parts / "tuba.pdf").write_bytes(b"%PDF-1.4\n%tuba-real\n")
    show["part_pdfs"]["tuba"] = "/etc/passwd"
    (parts / "clarinet.pdf").write_bytes(b"%PDF-1.4\n%clarinet-real\n")
    (tmp_path / "notes.txt").write_text("NOT-A-PDF-NOTES\n")
    show["part_pdfs"]["clarinet"] = "notes.txt"
    (parts / "trombone.pdf").write_bytes(b"%PDF-1.4\n%trombone-real\n")
    show["part_pdfs"]["trombone"] = "parts/trombone.pdf\x00"
    (parts / "not-a-part.pdf").write_bytes(b"%PDF-1.4\n%PLANTED-SECTION\n")
    show["part_pdfs"]["not-a-part"] = "parts/not-a-part.pdf"
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"%PDF-1.4\n%OUTSIDE-MARKER\n")
    (parts / "alto_sax.pdf").symlink_to(outside)
    show["part_pdfs"]["alto_sax"] = "parts/alto_sax.pdf"

    path = tmp_path / "show.json"
    path.write_text(json.dumps(show))
    client = TestClient(
        create_app(load_show(path), show_path=path),
        raise_server_exceptions=False,
    )
    ok = client.get("/api/part-pdf/baritone")
    assert ok.status_code == 200
    assert ok.content == good
    assert ok.headers["content-type"].startswith("application/pdf")

    show_bytes = path.read_bytes()
    blocked = ("trumpet", "snare", "flute", "tuba", "clarinet", "trombone", "alto_sax")
    for section in blocked:
        response = client.get(f"/api/part-pdf/{section}")
        assert response.status_code == 404, section
        assert response.content != show_bytes
        assert b"NOT-A-PDF-NOTES" not in response.content
        assert b"OUTSIDE-MARKER" not in response.content
        assert b"root:" not in response.content
        assert not response.content.startswith(b"%PDF")

    planted = client.get("/api/part-pdf/not-a-part")
    assert planted.status_code == 404
    assert b"PLANTED-SECTION" not in planted.content

    for url in ("/api/part-pdf/../show.json", "/api/part-pdf/%2e%2e%2fshow.json"):
        response = client.get(url)
        assert response.status_code == 404, url
        assert response.status_code != 500
        assert response.content != show_bytes
        assert b"OUTSIDE-MARKER" not in response.content


def test_music_intent_hides_pdfs_and_design_intent_keeps_them(tmp_path: Path):
    show = load_show(ROOT / "examples" / "fanfare.json")
    show["part_pdfs"] = {section: f"parts/{section}.pdf" for section in SECTION_ORDER}
    show["engrave_error"] = None
    show["part_errors"] = {}
    parts = tmp_path / "parts"
    parts.mkdir()
    payload = b"%PDF-1.4\n%linked-part\n"
    for section in SECTION_ORDER:
        (parts / f"{section}.pdf").write_bytes(payload + section.encode())
    path = tmp_path / "show.json"
    path.write_text(json.dumps(show))
    client = TestClient(create_app(load_show(path), show_path=path))
    assert client.get("/api/part-pdf/trumpet").status_code == 200
    design = client.post(
        "/api/intent",
        json={
            "design": {
                "uniform": "White jacket",
                "flag": "plain gold",
                "palette": ["#e8a838", "#14120e"],
            }
        },
    )
    assert design.status_code == 200
    kept = client.get("/")
    assert 'href="/api/part-pdf/trumpet"' in kept.text
    assert client.get("/api/part-pdf/trumpet").content.startswith(b"%PDF")
    changed = client.post("/api/intent", json={"tempo": 96})
    assert changed.status_code == 200
    page = client.get("/").text
    assert "unavailable" in page
    assert 'href="/api/part-pdf/' not in page
    assert client.get("/api/part-pdf/trumpet").status_code == 404
    assert client.get("/api/part-pdf/tuba").status_code == 404


def test_engrave_timeout_kills_grandchild(tmp_path: Path):
    pidfile = tmp_path / "children.pids"
    lilypond = (
        "#!/bin/sh\n"
        "sleep 300 &\n"
        f"echo $! >> {shlex.quote(str(pidfile))}\n"
        "sleep 300\n"
    )
    out = tmp_path / "show.json"
    env = _fake_tools(tmp_path / "bin", lilypond)
    env["FIELDSHOW_ENGRAVE_TIMEOUT"] = "2"
    proc = subprocess.Popen(
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
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        try:
            _stdout, stderr = proc.communicate(timeout=120)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.communicate()
            pytest.fail("build hung; the engraver timeout did not stop the part")
        assert proc.returncode == 0, stderr
        show = json.loads(out.read_text())
        assert all(value is None for value in show["part_pdfs"].values())
        assert show["part_errors"]["trumpet"] == "timed out"
        assert "timed out" in show["engrave_error"]
        page = TestClient(create_app(show, show_path=out)).get("/").text
        assert "/tmp/" not in page
        assert "fieldshow-engrave-" not in page
        items = _paper_items(page)
        assert len(items) == len(SECTION_ORDER)
        for item in items:
            assert len(item) < 200
            assert "timed out" in item
        assert pidfile.is_file()
        pids = [int(line) for line in pidfile.read_text().split()]
        assert len(pids) == len(SECTION_ORDER)
        deadline = time.time() + 2
        while time.time() < deadline and not all(_gone(pid) for pid in pids):
            time.sleep(0.05)
        for pid in pids:
            assert _gone(pid)
    finally:
        if pidfile.is_file():
            for line in pidfile.read_text().split():
                try:
                    os.kill(int(line), signal.SIGKILL)
                except (ProcessLookupError, ValueError):
                    pass
        if proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.communicate()


def test_engraver_path_with_a_space_still_writes_pdfs(tmp_path: Path):
    tools = tmp_path / "fake bin"
    lilypond = (
        "#!/bin/sh\n"
        "out=\n"
        "while [ $# -gt 0 ]; do\n"
        '  if [ "$1" = "-o" ]; then out=$2; shift 2; continue; fi\n'
        "  shift\n"
        "done\n"
        "printf '%s\\n' '%PDF-1.4 fake-with-space' > \"${out}.pdf\"\n"
        "exit 0\n"
    )
    out = tmp_path / "show.json"
    env = _fake_tools(tools, lilypond)
    result = _build(out, env)
    assert result.returncode == 0, result.stderr
    show = json.loads(out.read_text())
    assert not show.get("engrave_error")
    for section in SECTION_ORDER:
        assert show["part_pdfs"][section] == f"parts/{section}.pdf"
        data = (tmp_path / "parts" / f"{section}.pdf").read_bytes()
        assert data.startswith(b"%PDF")


def _route_client(show_dir: Path, markers: dict[str, str | None]) -> TestClient:
    show = load_show(ROOT / "examples" / "fanfare.json")
    show["part_pdfs"] = {section: None for section in SECTION_ORDER}
    show["part_pdfs"].update(markers)
    show["engrave_error"] = None
    path = show_dir / "show.json"
    path.write_text(json.dumps(show))
    return TestClient(create_app(load_show(path), show_path=path), raise_server_exceptions=False)


def test_part_pdf_route_404s_when_the_file_is_missing_or_looping(tmp_path: Path):
    """Marker set but no file (the 'mounted only the JSON' deploy), and a symlink loop."""
    parts = tmp_path / "parts"
    parts.mkdir()
    good = b"%PDF-1.4\n%baritone-good\n"
    (parts / "baritone.pdf").write_bytes(good)
    (parts / "tuba.pdf").symlink_to("tuba.pdf")
    client = _route_client(
        tmp_path,
        {
            "baritone": "parts/baritone.pdf",
            "trumpet": "parts/trumpet.pdf",
            "tuba": "parts/tuba.pdf",
        },
    )
    assert client.get("/api/part-pdf/baritone").content == good
    assert client.get("/api/part-pdf/trumpet").status_code == 404
    assert client.get("/api/part-pdf/tuba").status_code == 404


def test_part_pdf_route_404s_when_parts_dir_is_unreadable(tmp_path: Path):
    if os.geteuid() == 0:
        pytest.skip("root ignores directory permissions")
    parts = tmp_path / "parts"
    parts.mkdir()
    (parts / "trumpet.pdf").write_bytes(b"%PDF-1.4\n%trumpet\n")
    client = _route_client(tmp_path, {"trumpet": "parts/trumpet.pdf"})
    parts.chmod(0)
    try:
        response = client.get("/api/part-pdf/trumpet")
    finally:
        parts.chmod(0o755)
    assert response.status_code == 404


def test_part_pdf_route_404s_when_parts_dir_points_outside_the_show(tmp_path: Path):
    show_dir = tmp_path / "show"
    show_dir.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "trumpet.pdf").write_bytes(b"%PDF-1.4 ELSEWHERE-OUTSIDE-SHOWDIR\n")
    (show_dir / "parts").symlink_to(elsewhere, target_is_directory=True)
    client = _route_client(show_dir, {"trumpet": "parts/trumpet.pdf"})
    response = client.get("/api/part-pdf/trumpet")
    assert response.status_code == 404
    assert b"ELSEWHERE" not in response.content


@pytest.mark.parametrize("value", ["abc", "0", "-1", "inf", "nan"])
def test_bad_engrave_timeout_fails_the_build_and_keeps_old_pdfs(tmp_path: Path, value: str):
    parts = tmp_path / "parts"
    parts.mkdir()
    old = {section: f"%PDF-1.4\n%old-{section}\n".encode() for section in SECTION_ORDER}
    for section, data in old.items():
        (parts / f"{section}.pdf").write_bytes(data)
    out = tmp_path / "show.json"
    out.write_text('{"previous": true}')
    env = _fake_tools(tmp_path / "bin", _exit_4_lilypond())
    env["FIELDSHOW_ENGRAVE_TIMEOUT"] = value
    result = _build(out, env)
    assert result.returncode == 2
    assert f"FIELDSHOW_ENGRAVE_TIMEOUT must be a positive number of seconds, got {value!r}" in result.stderr
    assert "Traceback" not in result.stderr
    assert out.read_text() == '{"previous": true}'
    for section, data in old.items():
        assert (parts / f"{section}.pdf").read_bytes() == data


def test_each_part_export_carries_its_own_pitches(tmp_path: Path):
    """The one-staff MusicXML the engraver reads has that section's notes."""
    from music21 import converter, note

    show = arrange(load_show(ROOT / "examples" / "fanfare.json"))

    def midi(tokens):
        return [note.Note(token).pitch.midi for token in tokens if token is not None]

    assert midi(show["parts"]["flute"]) != midi(show["parts"]["tuba"])
    for section in SECTION_ORDER:
        dest = tmp_path / f"{section}.musicxml"
        export_musicxml(show, dest, section=section)
        parts = list(converter.parse(str(dest)).parts)
        assert len(parts) == 1
        assert parts[0].partName == PART_NAMES[section]
        got = [n.pitch.midi for n in parts[0].flatten().notes]
        assert got == midi(show["parts"][section]), section


def test_musicxml2ly_exit_status_fails_the_part(tmp_path: Path):
    env = _fake_tools(
        tmp_path / "bin",
        "#!/bin/sh\n"
        "out=\n"
        "while [ $# -gt 0 ]; do\n"
        '  if [ "$1" = "-o" ]; then out=$2; shift 2; continue; fi\n'
        "  shift\n"
        "done\n"
        "printf '%s\\n' '%PDF-1.4 fake-good' > \"${out}.pdf\"\n"
        "exit 0\n",
    )
    converter = Path(env["FIELDSHOW_MUSICXML2LY"])
    _write_exec(converter, _converter_script().replace("exit 0\n", "exit 3\n"))
    out = tmp_path / "show.json"
    result = _build(out, env)
    assert result.returncode == 0, result.stderr
    assert "musicxml2ly exited 3" in result.stderr
    show = json.loads(out.read_text())
    assert show["part_pdfs"] == {section: None for section in SECTION_ORDER}
    assert show["part_errors"]["trumpet"] == "musicxml2ly exited 3"
    assert list((tmp_path / "parts").glob("*.pdf")) == []
