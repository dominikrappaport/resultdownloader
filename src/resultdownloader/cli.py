"""
CLI tool for downloading race results from RaceTimePro.

Usage:
    resultdownloader \
      --url "https://events.racetime.pro/en/event/1022/competition/6422/results" \
      --output results.csv

    resultdownloader \
      --urllist urls.txt
"""

import argparse
import re
import sys
from pathlib import Path
from .downloader import RaceResultsDownloader


def extract_event_competition(url: str) -> str:
    """
    Extract EVENT from a RaceTimePro URL.

    Args:
        url: URL in format https://events.racetime.pro/en/event/EVENT/competition/COMPETITION/results

    Returns:
        Event ID

    Raises:
        ValueError: If URL doesn't match expected pattern
    """
    pattern = r"/event/([^/]+)/"
    match = re.search(pattern, url)

    if not match:
        raise ValueError(f"URL doesn't match expected pattern: {url}")

    return match.group(1)


def process_url_list(urllist_file: str) -> int:
    """
    Process a file containing URLs and download results for each.

    Args:
        urllist_file: Path to text file with one URL per line

    Returns:
        Exit code (0 for success, 1 for any errors)
    """
    urllist_path = Path(urllist_file)

    if not urllist_path.exists():
        print(f"Error: File not found: {urllist_file}", file=sys.stderr)
        return 1

    try:
        with open(urllist_path, "r", encoding="utf-8") as f:
            urls = [line.strip() for line in f if line.strip()]
    except Exception as e:
        print(f"Error reading file {urllist_file}: {e}", file=sys.stderr)
        return 1

    if not urls:
        print(f"Error: No URLs found in {urllist_file}", file=sys.stderr)
        return 1

    downloader = RaceResultsDownloader()
    errors = []

    for i, url in enumerate(urls, 1):
        try:
            event = extract_event_competition(url)
            output_file = f"race_{event}.csv"

            print(f"[{i}/{len(urls)}] Processing {url}...")
            row_count = downloader.download_to_csv(url, output_file)
            print(f"  ✓ Wrote {row_count} rows to {output_file}")

        except ValueError as e:
            error_msg = f"  ✗ Error processing {url}: {e}"
            print(error_msg, file=sys.stderr)
            errors.append(error_msg)
        except Exception as e:
            error_msg = f"  ✗ Unexpected error processing {url}: {e}"
            print(error_msg, file=sys.stderr)
            errors.append(error_msg)

    if errors:
        print(f"\nCompleted with {len(errors)} error(s)", file=sys.stderr)
        return 1

    print(f"\n✓ Successfully processed all {len(urls)} URL(s)")
    return 0


def main() -> int:
    """
    Main entry point for the CLI tool.

    Returns:
        Exit code (0 for success, 1 for errors)
    """
    parser = argparse.ArgumentParser(
        description="Scrape race results and export selected columns."
    )

    # Create mutually exclusive group for --url and --urllist
    url_group = parser.add_mutually_exclusive_group(required=True)
    url_group.add_argument(
        "--url",
        help=(
            "Results page URL "
            "(e.g. https://events.racetime.pro/en/event/1022/competition/6422/results)"
        ),
    )
    url_group.add_argument(
        "--urllist",
        help=(
            "Text file with one URL per line. Results will be saved as race_EVENT.csv"
        ),
    )

    parser.add_argument(
        "--output",
        help="Output CSV filename (only used with --url)",
    )

    args = parser.parse_args()

    # Handle --urllist mode
    if args.urllist:
        if args.output:
            print("Warning: --output is ignored when using --urllist", file=sys.stderr)
        return process_url_list(args.urllist)

    # Handle --url mode
    if not args.output:
        print("Error: --output is required when using --url", file=sys.stderr)
        parser.print_help()
        return 1

    try:
        downloader = RaceResultsDownloader()
        row_count = downloader.download_to_csv(args.url, args.output)
        print(f"Wrote {row_count} rows to {args.output}")
        return 0
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
