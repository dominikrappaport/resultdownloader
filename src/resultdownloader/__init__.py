"""
Result Downloader - A package for scraping race results from RaceTimePro.

This module provides functionality to download, parse, and process race results
from RaceTimePro websites.
"""

from .downloader import download_results, RaceResultsDownloader

__version__ = "1.0.1"
__all__ = ["download_results", "RaceResultsDownloader"]
__author__ = "Dominik Rappaport"
__email__ = "dominik@rappaport.at"
__license__ = "MIT"
