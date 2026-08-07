#!/usr/bin/env python3
"""Build the unified dashboard and launch it with one command."""

from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path

from build_test_dashboard import main as build_dashboard
from paths import resolve_workspace_root
from voice_studio_server import run_server


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate and open VoiceGenerator dashboard")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=resolve_workspace_root(),
        help="Workspace root containing scripts/ and outputs/",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Only build dashboard, do not open browser.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Local bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8765, help="Local bind port (default: 8765)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.project_root.resolve()
    outputs_root = root / "outputs"
    output_html = outputs_root / "index.html"

    build_dashboard_args = ["--project-root", str(root)]
    # build_dashboard() reads sys.argv, so invoke the small builder as a
    # subprocess-free function by temporarily providing its arguments.
    previous_argv = sys.argv
    try:
        sys.argv = [str(root / "scripts" / "build_test_dashboard.py"), *build_dashboard_args]
        if build_dashboard() != 0:
            return 1
    finally:
        sys.argv = previous_argv

    if not output_html.exists():
        print(f"build failed: missing {output_html}")
        return 1

    if args.no_open:
        print(f"dashboard ready: {output_html}")
        return 0

    url = f"http://{args.host}:{args.port}/index.html"
    opened = webbrowser.open(url, new=2)
    if opened:
        print(f"opened: {url}")
    else:
        print(f"studio ready: {url}")
    run_server(args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
