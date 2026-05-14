from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import json
import sys

from ms_meetings.browser import BrowserConfig
from ms_meetings.browser import load_env_browser_config
from ms_meetings.browser import open_page
from ms_meetings.teams_transcript import TranscriptExtractionError
from ms_meetings.teams_transcript import fetch_transcript
from ms_meetings.teams_transcript import save_artifacts
from ms_meetings.teams_transcript import slugify_title


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Extract a finalized Teams transcript using the main Chrome profile.")
    parser.add_argument("url", help="Microsoft Stream or Teams recap URL")
    parser.add_argument("--output-dir", default="output", help="Directory for generated artifacts")
    parser.add_argument("--profile-directory", default=None, help="Chrome profile directory name, default is taken from env or Default")
    parser.add_argument("--user-data-dir", default=None, help="Chrome user data root, default is the standard macOS Chrome path")
    parser.add_argument("--chrome-path", default=None, help="Chrome binary path")
    parser.add_argument("--headless", action="store_true", help="Run Chrome headless")
    parser.add_argument("--timeout-ms", type=int, default=None, help="Browser timeout in milliseconds")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    config = _build_browser_config(args)

    try:
        with open_page(config=config, url=args.url) as (_, _, page):
            result = fetch_transcript(page=page, source_url=args.url)
    except TranscriptExtractionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    slug = slugify_title(result.document.title)
    artifacts = save_artifacts(result.document, output_dir=Path(args.output_dir), slug=slug)
    print(
        json.dumps(
            {
                "title": artifacts.title,
                "transcript_path": artifacts.transcript_path,
                "metadata_path": artifacts.metadata_path,
                "warnings": result.document.warnings,
            },
            indent=2,
        )
    )


def _build_browser_config(args) -> BrowserConfig:
    config = load_env_browser_config()
    if args.chrome_path:
        config.chrome_path = Path(args.chrome_path)
    if args.user_data_dir:
        config.user_data_dir = Path(args.user_data_dir)
    if args.profile_directory:
        config.profile_directory = args.profile_directory
    if args.timeout_ms is not None:
        config.timeout_ms = args.timeout_ms
    if args.headless:
        config.headless = True
    return config


if __name__ == "__main__":
    main()