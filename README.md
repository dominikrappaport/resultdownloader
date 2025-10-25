# Resultdownloader

## Author

Dominik Rappaport, dominik@rappaport.at

## Synopsis

This tool facilitates the download of competition results from the RaceTimePro website. As the platform does not 
provide a native CSV export option, this script addresses that limitation.

## Disclaimer

It should be noted that substantial portions of this script were generated using ChatGPT, with only minor manual 
adjustments required.

## Installation

The resultdownloader is distributed as a Python package. Several installation methods are available.

### Using pip

Executing `pip` installs the package in your current Python environment. Global installation was once possible, but
modern Linux distributions no longer permit this approach.

```bash
pip install resultdownloader
```

### Using pipx or uv

Both `pipx` and `uv` enable global tool installation. The package can be installed as follows:

```bash
pipx install resultdownloader
```

or

```bash
uv tools install resultdownloader
```

## Usage

### Single URL Mode

Download results from a single competition by providing a URL and output filename:

```bash
resultdownloader --url "URL" --output FILE
```

Example:

```bash
resultdownloader --url "https://events.racetime.pro/en/event/1022/competition/6422/results" --output race_results.csv
```

### URL list mode

Download results from multiple competitions by providing a text file containing one URL per line:

```bash
resultdownloader --urllist FILE
```

Example:

```bash
resultdownloader --urllist racelist.txt
```

In this mode, output files are automatically named as `race_EVENT.csv` 
based on the event IDs extracted from each URL.