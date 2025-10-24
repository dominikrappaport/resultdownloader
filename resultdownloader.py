"""
Scrape race results from RaceTimePro (English UI), pick specific columns,
clean up the Name column, and save as a semicolon-separated CSV.

Usage:
    python resultsdownloader.py \
      --url "https://events.racetime.pro/en/event/1022/competition/6422/results" \
      --output results.csv
"""

import argparse
import csv
import sys
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
import pandas as pd


# Columns we want in the final CSV, in this order:
REQUESTED_COLUMNS = [
    "Pos",
    "No",
    "Name",
    "Year of Birth",
    "Time",
    "Diff",
    "Cat",
    "Cat Pos",
    "Cat Diff",
    "⚤",
    "⚤ Pos",
    "⚤ Diff",
    "Club",
    "Pace",
#    "Nation",
    "City",
    "Status",
    "UCI-ID",
]


def fetch_html(session: requests.Session, url: str) -> str:
    """
    Fetch a URL and return HTML text.
    We send a browsery User-Agent because some sites behave differently for 'python-requests'.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/127.0.0.0 Safari/537.36"
        )
    }
    resp = session.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.text


def extract_results_table(html: str) -> pd.DataFrame | None:
    """
    Parse the HTML and return the most likely race results table as a pandas DataFrame.

    Heuristic:
    - read ALL <table> tags with pandas.read_html()
    - score each table based on how many "typical" race headers it contains
    - return the best-scoring one
    """
    try:
        tables = pd.read_html(html)
    except ValueError:
        # No tables found at all
        return None

    typical_headers = {
        "Pos",
        "No",
        "Name",
        "Year of Birth",
        "Time",
        "Status",
        "Club",
        "UCI-ID",
        "Pace",
    }

    best_df = None
    best_score = -1

    for df in tables:
        # normalise column labels
        df.columns = [str(c).strip() for c in df.columns]

        score = sum(
            1
            for token in typical_headers
            if any(token in col for col in df.columns)
        )

        if score > best_score:
            best_df = df
            best_score = score

    # Fallback: if no score > -1 (shouldn't happen unless page has weird HTML),
    # just take the largest table.
    if best_df is None and tables:
        best_df = max(tables, key=lambda d: len(d))
        best_df.columns = [str(c).strip() for c in best_df.columns]

    return best_df


def find_next_page_url(html: str, current_url: str) -> str | None:
    """
    Try to detect a *server-side* next page.

    Many racetime.pro pages actually include all rows in one HTML
    and then paginate client-side with JavaScript. In that case there's
    no real "next" link in the HTML and we just stop after the first page.

    We'll check:
    - <a rel="next" ...>
    - common "next page" link texts
    """
    soup = BeautifulSoup(html, "html.parser")

    # 1) rel="next"
    link = soup.find("a", rel="next")
    if link and link.get("href"):
        return urljoin(current_url, link["href"])

    # 2) text-based heuristics
    possible_texts = [
        "next",
        "next »",
        "next page",
        ">",
        "›",
        ">>",
        "more",
        "weiter",
        "nächste",
    ]

    for a in soup.find_all("a"):
        text = (a.get_text() or "").strip().lower()
        if text in possible_texts and a.get("href"):
            return urljoin(current_url, a["href"])

    # no server-side next page found
    return None


def scrape_all_pages(start_url: str) -> pd.DataFrame:
    """
    Visit start_url and any true "next" pages, combine all result rows,
    and drop duplicates.
    """
    session = requests.Session()

    all_frames = []
    visited = set()
    url = start_url

    while url and url not in visited:
        visited.add(url)

        html = fetch_html(session, url)
        df = extract_results_table(html)

        if df is not None and not df.empty:
            # ensure stripped column names on each page
            df.columns = [str(c).strip() for c in df.columns]
            all_frames.append(df)

        # follow pagination if available
        url = find_next_page_url(html, url)

    if not all_frames:
        # nothing found at all
        return pd.DataFrame()

    big = pd.concat(all_frames, ignore_index=True)

    # remove duplicates using some identifying columns if present
    dedup_cols = [c for c in big.columns if c.lower() in ("pos", "no", "name")]
    if dedup_cols:
        big = big.drop_duplicates(subset=dedup_cols)

    return big


def normalize_name_column(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean the 'Name' column:
    - The raw 'Name' can look like: "Alice Smith  Cycling Club ABC"
      (two or more spaces separating athlete name and team/club).
    - We only want the first part before the big gap.

    Steps:
    - cast to string
    - split on 2+ whitespace chars
    - take element 0
    - strip leading/trailing spaces
    """
    if "Name" in df.columns:
        df["Name"] = (
            df["Name"]
            .astype(str)
            .str.split(r"\s{2,}", n=1)  # split on two or more spaces
            .str[0]
            .str.strip()
        )
    return df


def select_and_order_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure all REQUESTED_COLUMNS exist, clean 'Name', and return only those columns
    in the specified order.
    """
    # Make sure all desired columns exist
    for col in REQUESTED_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    # Clean up the 'Name' column
    df = normalize_name_column(df)

    # Reorder columns
    df_out = df[REQUESTED_COLUMNS].copy()
    return df_out


def write_csv(df: pd.DataFrame, out_file: str) -> None:
    """
    Write final DataFrame to a semicolon-separated CSV (UTF-8).
    Semicolon is friendlier for Excel in many European locales.
    """
    df.to_csv(
        out_file,
        index=False,
        sep=",",
        quoting=csv.QUOTE_MINIMAL,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scrape race results and export selected columns."
    )
    parser.add_argument(
        "--url",
        required=True,
        help=(
            "Results page URL "
            "(e.g. https://events.racetime.pro/en/event/1022/competition/6422/results)"
        ),
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output CSV filename",
    )

    args = parser.parse_args()

    df_all = scrape_all_pages(args.url)

    if df_all.empty:
        print(
            "No data found: could not locate a suitable results table.",
            file=sys.stderr,
        )
        return 1

    df_final = select_and_order_columns(df_all)
    write_csv(df_final, args.output)

    print(f"Wrote {len(df_final)} rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())