"""Command line. Agents operate the show by filling JSON, then running these."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from fieldshow.design import apply_design
from fieldshow.drill.chart import chart
from fieldshow.drill.image import import_image
from fieldshow.drill.openmarch import write_om
from fieldshow.model import apply_intent, demo_show, load_show, save_show, validate_intent
from fieldshow.music.arrange import arrange
from fieldshow.music.io import export_midi, export_musicxml, import_musicxml


def _build(show: dict) -> dict:
    show = arrange(show)
    show = chart(show)
    return show


def cmd_demo(args: argparse.Namespace) -> int:
    save_show(demo_show(), args.output)
    print(args.output)
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    show = load_show(args.show)
    problems = validate_intent(show)
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    print("ok")
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    show = load_show(args.show) if args.show else demo_show()
    intent = json.loads(Path(args.intent).read_text())
    show = apply_intent(show, intent)
    if args.design:
        show = apply_design(show, json.loads(Path(args.design).read_text()))
    if not args.no_build:
        show = _build(show)
    save_show(show, args.output)
    print(args.output)
    return 0


def cmd_arrange(args: argparse.Namespace) -> int:
    show = arrange(load_show(args.show))
    save_show(show, args.output)
    print(args.output)
    return 0


def cmd_chart(args: argparse.Namespace) -> int:
    show = chart(load_show(args.show))
    save_show(show, args.output)
    print(args.output)
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    show = _build(load_show(args.show))
    save_show(show, args.output)
    print(args.output)
    return 0


def cmd_export_om(args: argparse.Namespace) -> int:
    write_om(load_show(args.show), args.output)
    print(args.output)
    return 0


def cmd_export_musicxml(args: argparse.Namespace) -> int:
    export_musicxml(load_show(args.show), args.output)
    print(args.output)
    return 0


def cmd_export_midi(args: argparse.Namespace) -> int:
    export_midi(load_show(args.show), args.output)
    print(args.output)
    return 0


def cmd_import_musicxml(args: argparse.Namespace) -> int:
    show = import_musicxml(args.musicxml)
    save_show(show, args.output)
    print(args.output)
    return 0


def cmd_import_image(args: argparse.Namespace) -> int:
    show = load_show(args.show)
    show = import_image(show, args.image, args.assets)
    save_show(show, args.output)
    print(args.output)
    return 0


def cmd_prompt_card(_args: argparse.Namespace) -> int:
    card = Path(__file__).resolve().parents[2] / "docs" / "PROMPT-CARD.md"
    # Installed copies keep the card next to the source tree. Fall back to the
    # packaged text only when the repo checkout is the cwd.
    if not card.is_file():
        card = Path.cwd() / "docs" / "PROMPT-CARD.md"
    sys.stdout.write(card.read_text())
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    from fieldshow.web.app import create_app

    show = load_show(args.show) if args.show else demo_show()
    app = create_app(show)
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fieldshow")
    sub = parser.add_subparsers(dest="command", required=True)

    demo = sub.add_parser("demo", help="write the sample fanfare intent")
    demo.add_argument("-o", "--output", default="examples/fanfare.json")
    demo.set_defaults(func=cmd_demo)

    check = sub.add_parser("check", help="validate an intent")
    check.add_argument("show")
    check.set_defaults(func=cmd_check)

    apply = sub.add_parser("apply", help="merge an agent intent and build")
    apply.add_argument("intent")
    apply.add_argument("--show", help="base show; default is the demo")
    apply.add_argument("--design", help="optional design JSON")
    apply.add_argument("--no-build", action="store_true")
    apply.add_argument("-o", "--output", required=True)
    apply.set_defaults(func=cmd_apply)

    for name, func, help_text in (
        ("arrange", cmd_arrange, "write transposed section parts"),
        ("chart", cmd_chart, "place marchers from shapes"),
        ("build", cmd_build, "arrange and chart"),
    ):
        cmd = sub.add_parser(name, help=help_text)
        cmd.add_argument("show")
        cmd.add_argument("-o", "--output", required=True)
        cmd.set_defaults(func=func)

    om = sub.add_parser("export-om", help="write an OpenMarch .om JSON file")
    om.add_argument("show")
    om.add_argument("-o", "--output", required=True)
    om.set_defaults(func=cmd_export_om)

    xml = sub.add_parser("export-musicxml", help="write a MusicXML score")
    xml.add_argument("show")
    xml.add_argument("-o", "--output", required=True)
    xml.set_defaults(func=cmd_export_musicxml)

    mid = sub.add_parser("export-midi", help="write a MIDI file")
    mid.add_argument("show")
    mid.add_argument("-o", "--output", required=True)
    mid.set_defaults(func=cmd_export_midi)

    imp = sub.add_parser("import-musicxml", help="lead sheet from the first part")
    imp.add_argument("musicxml")
    imp.add_argument("-o", "--output", required=True)
    imp.set_defaults(func=cmd_import_musicxml)

    img = sub.add_parser("import-image", help="attach a field picture")
    img.add_argument("show")
    img.add_argument("image")
    img.add_argument("--assets", default="examples/assets")
    img.add_argument("-o", "--output", required=True)
    img.set_defaults(func=cmd_import_image)

    card = sub.add_parser("prompt-card", help="print the agent input contract")
    card.set_defaults(func=cmd_prompt_card)

    serve = sub.add_parser("serve", help="integrated music, drill, and design view")
    serve.add_argument("--show")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8876)
    serve.set_defaults(func=cmd_serve)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, FileNotFoundError, NotImplementedError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
