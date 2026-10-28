# ProjectCrawl_VGA

End-to-end pipeline for scraping, cleaning, and analyzing GPU/VGA prices across five retailers: Phong Vũ, Phi Long, Mega, SP-One, and BuildCores.

## Project Structure

- `Main_Crawler/main.py` — Interactive CLI to scrape individual retailers or all sites sequentially.
- `Main_Crawler/sites/` — Site-specific scrapers (`phongvu.py`, `philong.py`, `mega.py`, `sp_one.py`, `buildcores.py`).
- `Main_Crawler/utils.py` — Headless Chrome WebDriver setup and CSV/Excel export helpers.
- `vga_clean.py` — Cleans raw `vga_*.csv` files, normalizes prices (VND/USD), extracts GPU models and brands, flags anomalies, and outputs `vga_clean.csv`.
- `vga_analysis.py` — Generates statistical summaries and Matplotlib/Seaborn charts from `vga_clean.csv`.
- `vga_clean.csv` — Cleaned dataset ready for analysis.

## Setup

Requires Python 3.10+ and Google Chrome.

```bash
pip install -r requirements.txt
pip install matplotlib seaborn numpy
```

## Usage

### 1. Crawl GPU Data

```bash
python Main_Crawler/main.py
```

Select a site (`1`–`5`) or `6` to scrape all sites. Raw `.csv` and `.xlsx` files save to `dataset/`.

### 2. Clean Dataset

Place raw `vga_*.csv` files in the project root (or copy from `dataset/`), then run:

```bash
python vga_clean.py
```

This produces `vga_clean.csv`.

### 3. Run Analysis & Visualizations

```bash
python vga_analysis.py
```

Prints summary statistics to the terminal and opens interactive chart windows.
