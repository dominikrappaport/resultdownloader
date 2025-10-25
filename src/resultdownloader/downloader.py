"""
Core functionality for downloading and processing race results from RaceTimePro.
"""

import csv
from typing import Optional
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
import pandas as pd
import io


# Default columns for race results
DEFAULT_COLUMNS = [
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
    "City",
    "Status",
    "UCI-ID",
]


class RaceResultsDownloader:
    """
    A class to download and process race results from RaceTimePro websites.

    Attributes:
        requested_columns: List of column names to include in the output
        session: requests.Session object for HTTP requests
    """

    def __init__(self, requested_columns: Optional[list[str]] = None):
        """
        Initialize the downloader.

        Args:
            requested_columns: List of columns to include in output.
                             If None, uses DEFAULT_COLUMNS.
        """
        self.requested_columns = requested_columns or DEFAULT_COLUMNS.copy()
        self.session = requests.Session()

    def fetch_html(self, url: str) -> str:
        """
        Fetch a URL and return HTML text.

        Args:
            url: The URL to fetch

        Returns:
            HTML content as string

        Raises:
            requests.HTTPError: If the request fails
        """
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/127.0.0.0 Safari/537.36"
            )
        }
        resp = self.session.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.text

    def extract_results_table(self, html: str) -> Optional[pd.DataFrame]:
        """
        Parse the HTML and return the most likely race results table as a pandas DataFrame.

        Heuristic:
        - read ALL <table> tags with pandas.read_html()
        - score each table based on how many "typical" race headers it contains
        - return the best-scoring one

        Args:
            html: HTML content to parse

        Returns:
            DataFrame with results or None if no suitable table found
        """
        try:
            tables = pd.read_html(io.StringIO(html))
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

    def find_next_page_url(self, html: str, current_url: str) -> Optional[str]:
        """
        Try to detect a *server-side* next page.

        Many racetime.pro pages actually include all rows in one HTML
        and then paginate client-side with JavaScript. In that case there's
        no real "next" link in the HTML and we just stop after the first page.

        Args:
            html: HTML content to parse
            current_url: Current page URL for resolving relative links

        Returns:
            URL of next page or None if not found
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

    def scrape_all_pages(self, start_url: str) -> pd.DataFrame:
        """
        Visit start_url and any true "next" pages, combine all result rows,
        and drop duplicates.

        Args:
            start_url: Initial URL to start scraping from

        Returns:
            DataFrame with all results combined
        """
        all_frames = []
        visited = set()
        url = start_url

        while url and url not in visited:
            visited.add(url)

            html = self.fetch_html(url)
            df = self.extract_results_table(html)

            if df is not None and not df.empty:
                # ensure stripped column names on each page
                df.columns = [str(c).strip() for c in df.columns]
                all_frames.append(df)

            # follow pagination if available
            url = self.find_next_page_url(html, url)

        if not all_frames:
            # nothing found at all
            return pd.DataFrame()

        big = pd.concat(all_frames, ignore_index=True)

        # remove duplicates using some identifying columns if present
        dedup_cols = [c for c in big.columns if c.lower() in ("pos", "no", "name")]
        if dedup_cols:
            big = big.drop_duplicates(subset=dedup_cols)

        return big

    def normalize_name_column(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean the 'Name' column:
        - The raw 'Name' can look like: "Alice Smith  Cycling Club ABC"
          (two or more spaces separating athlete name and team/club).
        - We only want the first part before the big gap.

        Args:
            df: DataFrame to process

        Returns:
            DataFrame with cleaned Name column
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

    def select_and_order_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Ensure all requested columns exist, clean 'Name', and return only those columns
        in the specified order.

        Args:
            df: DataFrame to process

        Returns:
            DataFrame with only requested columns in specified order
        """
        # Make sure all desired columns exist
        for col in self.requested_columns:
            if col not in df.columns:
                df[col] = ""

        # Clean up the 'Name' column
        df = self.normalize_name_column(df)

        # Reorder columns
        df_out = df[self.requested_columns].copy()
        return df_out

    def download(self, url: str) -> pd.DataFrame:
        """
        Download and process race results from the given URL.

        Args:
            url: Results page URL

        Returns:
            DataFrame with processed results

        Raises:
            ValueError: If no results table found
        """
        df_all = self.scrape_all_pages(url)

        if df_all.empty:
            raise ValueError(
                "No data found: could not locate a suitable results table."
            )

        df_final = self.select_and_order_columns(df_all)
        return df_final

    def download_to_csv(
        self, url: str, output_file: str, separator: str = ",", encoding: str = "utf-8"
    ) -> int:
        """
        Download race results and save to CSV file.

        Args:
            url: Results page URL
            output_file: Output CSV filename
            separator: CSV separator character (default: ",")
            encoding: File encoding (default: "utf-8")

        Returns:
            Number of rows written

        Raises:
            ValueError: If no results table found
        """
        df_final = self.download(url)

        df_final.to_csv(
            output_file,
            index=False,
            sep=separator,
            quoting=csv.QUOTE_MINIMAL,
            encoding=encoding,
        )

        return len(df_final)


def download_results(
    url: str,
    output_file: Optional[str] = None,
    requested_columns: Optional[list[str]] = None,
    separator: str = ",",
) -> pd.DataFrame:
    """
    Convenience function to download race results.

    Args:
        url: Results page URL
        output_file: Optional output CSV filename. If provided, results are saved to file.
        requested_columns: List of columns to include in output. If None, uses defaults.
        separator: CSV separator character (default: ",")

    Returns:
        DataFrame with race results

    Raises:
        ValueError: If no results table found

    Example:
        >>> df = download_results("https://events.racetime.pro/.../results")
        >>> df = download_results(
        ...     "https://events.racetime.pro/.../results",
        ...     output_file="results.csv"
        ... )
    """
    downloader = RaceResultsDownloader(requested_columns=requested_columns)
    df = downloader.download(url)

    if output_file:
        df.to_csv(
            output_file,
            index=False,
            sep=separator,
            quoting=csv.QUOTE_MINIMAL,
        )

    return df
