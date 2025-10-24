# Resultdownloader

## Author

Dominik Rappaport, dominik@rappaport.at

## Synopsis

I wanted to download the results of a competition listed on the website RaceTimePro. They do not offer a download to 
CSV option, though. This script does the job.

## Disclaimer

I frankly admit that most parts of this script were written by ChatGPT. I only had to make minor adjustments.

## Installation

Install the uv package manager. Then run:

```bash
git clone https://github.com/dominikrappaport/resultdownloader.git
cd resultdownloader
uv sync
```

## Usage

The script accepts two arguments. The URL of the competition and the name of the CSV file to write to.

```bash
uv run resultdownloader.py --url "URL" --output FILE
```

Example:

```bash
uv run resultdownloader.py --url "https://events.racetime.pro/en/event/1022/competition/6422/results" --output race_results.csv
```