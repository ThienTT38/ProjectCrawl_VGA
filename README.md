# VGA Price Intelligence and Time-Series Forecasting Platform
### An End-to-End System for Multi-Source Scraping, Data Engineering, Hardware Specification Harmonization, and Machine Learning Valuation

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![Scikit-Learn](https://img.shields.io/badge/scikit--learn-v1.4%2B-orange.svg)](https://scikit-learn.org/)
[![Pydantic](https://img.shields.io/badge/Pydantic-v2.7%2B-red.svg)](https://docs.pydantic.dev/)
[![SQLite](https://img.shields.io/badge/SQLite-v3.40%2B-lightgrey.svg)](https://sqlite.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)


---

## 1. Executive Summary and Objectives

The graphics processing unit (GPU/VGA) retail market in Vietnam is characterized by high price volatility, fragmented seller disclosures, multi-currency imports, and non-standardized hardware naming conventions. This project establishes an automated, production-grade data intelligence pipeline designed to:

1. **Ingest Multi-Source Retail and Hardware Data:** Extract comprehensive GPU listings from Vietnamese authorized distributors (Phong Vu, Mega Technology, Phi Long) and international hardware repositories (BuildCores Open Database, TechPowerUp).
2. **Standardize and Harmonize Schemas:** Resolve messy product titles, irregular VRAM/bus descriptions, and non-standardized brand naming using robust regex parsers, deterministic SHA-256 SKU identifiers, and strict Pydantic data contract validation.
3. **Execute Transparent Multi-Tier Imputation:** Address missing pricing attributes through a tiered hierarchical imputation engine (Tiers 1 to 5), maintaining a strict distinction between observed market prices and simulated estimations via provenance tracking.
4. **Model Retail Pricing Realism:** Normalize prices to Vietnamese psychological retail pricing standards (Charm Pricing ending in `...90,000 VND`) while preserving authentic distributor discounts and original strike-through prices.
5. **Construct Verified Time-Series Panels:** Maintain a clean 3-week longitudinal dataset and an isolated ground-truth observed price tracking dataset without synthetic inflation.
6. **Implement Leakage-Free Machine Learning Valuation:** Train multivariate linear, bagging, and boosting algorithms with rigorous train-test isolation and GroupKFold cross-validation, evaluating on ground-truth observed retail prices.

---

## 2. End-to-End Pipeline Architecture

The system follows a modular, feed-forward architecture across six specialized processing stages:

```mermaid
flowchart TD
    subgraph S1["1. DATA INGESTION (ADAPTER PATTERN)"]
        direction TB
        src_pv["Phong Vu (phongvu.vn)<br/>API / Next.js JSON Engine"]
        src_mega["Mega Technology (mega.com.vn)<br/>HTML / Slug Parser"]
        src_pl["Phi Long (philong.com.vn)<br/>Pagination Parser"]
        src_bc["BuildCores Open Database<br/>Spec & Hardware DB"]

        adapter["BaseAdapter Interface"]
        pydantic["Pydantic Validation (VGASchema)"]
        dlq["Dead-Letter Queue (Filter Risers, Brackets)"]

        src_pv --> adapter
        src_mega --> adapter
        src_pl --> adapter
        src_bc --> adapter
        adapter --> pydantic
        pydantic -- Valid --> raw_norm["vga_normalized.csv (4,299 SKUs)"]
        pydantic -- Invalid --> dlq
    end

    subgraph S2["2. CLEANING & CURRENCY UNIFICATION"]
        direction TB
        clean_brand["Brand Normalization (ASUS, MSI, GIGABYTE, etc.)"]
        clean_spec["Feature Extraction (VRAM GB/Type, Fan, Clock, TDP)"]
        conv_vnd["Currency Unification (VND at 25,450 VND/USD)"]
        raw_norm --> clean_brand --> clean_spec --> conv_vnd
    end

    subgraph S3["3. MULTI-TIER IMPUTATION & HARMONIZATION"]
        direction TB
        l1["Tier 1: Cross-retailer SKU Match"]
        l2["Tier 2: Median GPU + VRAM + Brand"]
        l3["Tier 3: Median Architecture + VRAM"]
        l4["Tier 4: Base Architecture Baseline"]
        l5["Tier 5: TechPowerUp MSRP & Depreciation"]
        conv_vnd --> l1 --> l2 --> l3 --> l4 --> l5
        l5 --> imputed_100["100.0% Price Coverage (4,299/4,299)"]
    end

    subgraph S4["4. RETAIL PRICE REALISM ENGINE"]
        direction TB
        guard["Ground-Truth Price Guard (Preserve 588 Retail Prices)"]
        charm["Charm Pricing Normalization (...90,000 VND)"]
        tier["Cooling Tier Adjustment (Flagship +15%, Compact -5%, OC +2%)"]
        disc["Observed vs Simulated Discount Provenance"]
        imputed_100 --> guard
        imputed_100 --> tier --> charm --> disc
    end

    subgraph S5["5. 3-WEEK TIME-SERIES ENGINEERING"]
        direction TB
        w1["Week 1 (Oct 07, 2026): Base Snapshot"]
        w2["Week 2 (Oct 21, 2026): Trajectory & Promotions"]
        w3["Week 3 (Oct 30, 2026): Realistic Panel Snapshot"]

        wide["Wide Panel Dataset (vga_3weeks_panel_dataset.csv)"]
        long_ts["Long Time-Series (vga_3weeks_timeseries_long.csv)"]
        db["SQLite Database (vga_3weeks_database.db)"]

        disc --> w3
        w1 --> wide & long_ts
        w2 --> wide & long_ts
        w3 --> wide & long_ts
        wide & long_ts --> db
    end

    subgraph S6["6. MACHINE LEARNING & VALUATION"]
        direction TB
        feats["Feature Engineering (Lags, Momentum, Volatility)"]
        models["Ensemble Model Training (Gradient Boosting / RF)<br/>Observed Ground-Truth R² = 94.63% | MAE = 3.10M VND"]
        pred["Next-Week Valuation Prediction"]
        deal["Valuation Audit (GOOD_DEAL / FAIR / OVERPRICED)"]
        wide --> feats --> models --> pred --> deal
    end
```

---

## 3. Repository Directory Structure

```text
ProjectCrawl_VGA/
├── adapters/                  # Concrete adapters for each retail source
│   ├── base_adapter.py        # Base adapter interface and dead-letter queue
│   ├── phongvu_adapter.py     # Teko Discovery API parser
│   ├── mega_adapter.py        # Hurasoft HTML parser
│   ├── philong_adapter.py     # Phi Long store parser
│   └── buildcores_adapter.py  # Hardware DB adapter
├── core/                      # HTTP clients, driver setup, and compatibility utilities
│   ├── compat.py              # Pydantic v1/v2 compatibility shim
│   ├── http_html.py           # Resilient HTTP request helper
│   └── utils.py               # Chrome WebDriver & checkpoint utilities
├── crawlers/                  # Concrete crawler runners and site registry
│   ├── crawl_buildcores.py    # BuildCores hardware crawl runner
│   ├── crawl_mega.py          # Mega Technology crawl runner
│   ├── crawl_philong.py       # Phi Long crawl runner
│   ├── crawl_phongvu.py       # Phong Vu crawl runner
│   └── sites.py               # Site registry and mapping
├── normalizers/               # Regex parsers for GPU model, brand, VRAM, and accessories
├── schemas/                   # Pydantic schema contracts (VGASchema)
├── storage/                   # Multi-format data exporters (SQLite, CSV, JSON)
├── pipeline/                  # Data engineering pipeline stages & enrichment
│   ├── enricher.py            # Hardware specification cross-enrichment
│   ├── orchestrator.py        # Multi-adapter crawl orchestrator
│   ├── clean_and_unify.py     # Stage 1: Initial cleaning, unification & deduplication
│   ├── impute_prices.py       # Stage 2: Multi-tier hierarchical imputation
│   ├── build_100pct_solutions.py # Stage 3: 100% price coverage via MSRP / 2nd-hand
│   ├── clean_realism_prices.py # Stage 4: Retail realism & Charm Pricing
│   ├── build_3weeks_dataset.py # Stage 5: Multi-week longitudinal panel builder
│   └── refresh_normalized_baseline.py # Normalized baseline synchronizer
├── ml/                        # Machine Learning valuation and modeling
│   └── ml_price_prediction.py # Leakage-free ML training & GroupKFold cross-validation
├── tests/                     # Automated test and verification suite
│   ├── test_vga_crawler.py    # Unit tests for SKU hashing, parsers, and schemas
│   └── verify_all_fixes.py    # Comprehensive audit validating all 10 critique items
│
├── data/                      # Standardized data engineering hierarchy
│   ├── 01_raw/                # Original weekly raw crawled snapshots
│   ├── 02_processed/          # Cleaned, validated weekly records
│   ├── 03_timeseries/         # Integrated 3-week time-series datasets
│   │   ├── vga_3weeks_panel_dataset.csv     # Wide panel dataset (4,299 rows x 40 columns)
│   │   ├── vga_3weeks_timeseries_long.csv   # Longitudinal dataset (12,897 observations)
│   │   ├── vga_observed_price_tracking.csv  # Pure observed longitudinal data (537 rows)
│   │   ├── vga_3weeks_dataset.json          # JSON representation for downstream services
│   │   └── vga_3weeks_database.db           # Indexed SQLite database
│   └── 04_legacy_archive/     # Historical archive of legacy intermediate artifacts
│
├── output/                    # Production deliverables and model artifacts
│   ├── deliverables/          # Final distribution datasets (CSV, JSON, SQLite)
│   ├── models/                # Trained serialization files (.joblib)
│   ├── logs/                  # Crawl diagnostics and dead-letter logs
│   └── archive_stages/        # Intermediate audit stages (L1-L4)
│
├── main.py                    # Unified CLI command orchestrator
├── requirements.txt           # Pinned production dependency manifest
└── README.md                  # Project documentation and reproduction guide
└── README.md                  # Comprehensive project documentation
```

---

## 4. Resolution of Reviewer Critiques and Verification Matrix

The platform has been audited against all 10 priority scientific and data engineering critiques (P1.1–P1.4, P2.5–P2.10) with 100% test pass rates:

| Critique Code | Description of Original Defect | Remediation Strategy | Verification Metric / Outcome |
| :--- | :--- | :--- | :--- |
| **P1.1** | Tracking dataset contained synthetic prices generated by formula | Separated pure observed tracking data from synthetic trajectory models | Created `vga_observed_price_tracking.csv` (537 genuine observed data points) |
| **P1.2** | ML models were evaluated on internally estimated prices | Segregated evaluation set; reported standalone metrics on ground-truth observed retail prices | Ground-Truth Retail: Random Forest $R^2 = 94.63\%$, MAE = 3.10M VND, MAPE = 13.07% |
| **P1.3** | Truncated SKU slugs caused collision and overwrite in SQLite | Replaced truncated slugs with 16-character full SHA-256 URL hashes | **0 duplicate SKUs** across all 4,299 products in CSV and SQLite catalog |
| **P1.4** | CUDA core parser parsed `2944.0` as `29440` cores | Added float parsing handler: `int(float(raw_str))` before regex fallback | Parsed float strings verified at exactly 2,944 cores; 3,859 cards enriched |
| **P2.5** | Preprocessing pipeline fitted on test partition (Data Leakage) | Split dataset before statistics; encapsulated preprocessing inside Scikit-Learn `Pipeline` | 0 data leakage; transformation fitted solely on training partition |
| **P2.6** | Stock status incorrectly inferred in BuildCores adapter | Assigned `UNKNOWN` status to BuildCores; verified explicit retailer stock cues | BuildCores stock status verified at 0 false positives |
| **P2.7** | Authentic original and discount percentages overwritten | Preserved raw scraped strike-through prices; only imputed when missing | 352 authentic retailer discounts preserved; no synthetic discounts forced |
| **P2.8** | Hardware matching by name was excessively loose | Enforced dual-key join on normalized chipset identifier and exact VRAM capacity | 100% consistent matching across TechPowerUp spec database |
| **P2.9** | Single-page timeout aborted entire crawl session | Wrapped page fetches in per-page try-except blocks with error logging | Resilient scraping with accurate completed crawl statistics |
| **P2.10** | Pipeline contained hardcoded user paths | Replaced absolute paths with relative paths; pinned virtual environment specs | 100% reproducible execution from an empty repository clone |

---

## 5. Machine Learning Methodology and Empirical Results

### Algorithms Implemented
1. **Regularized Linear Regression (Ridge / Lasso):** Serves as an interpretable parametric baseline to evaluate linear relationships between hardware attributes and market valuations.
2. **Random Forest Regressor:** Employs bootstrap aggregation (Bagging) across 100 randomized decision trees to capture high-order nonlinearities without overfitting.
3. **Gradient Boosting Regressor:** Sequentially constructs shallow decision trees, optimizing squared error loss through gradient descent to fit complex market valuation curves.

### Quantitative Benchmark Results

#### Evaluation on Ground-Truth Observed Retail Prices (588 Domestic Products)
Evaluated strictly on independent, un-imputed domestic retail prices to measure real-world pricing fidelity:

| Model Architecture | Coefficient of Determination ($R^2$) | Mean Absolute Error (MAE) | Mean Absolute Percentage Error (MAPE) |
| :--- | :---: | :---: | :---: |
| **Random Forest Regressor** | **94.63%** | **3,105,362 VND** | **13.07%** |
| **Gradient Boosting Regressor** | 93.85% | 3,342,109 VND | 14.22% |
| **Ridge Linear Regression** | 85.12% | 5,120,440 VND | 22.45% |

#### Evaluation on Full Stratified Test Partition (860 Products)
Evaluated with zero data leakage across all catalog tiers:

| Model Architecture | Coefficient of Determination ($R^2$) | Mean Absolute Error (MAE) | Root Mean Squared Error (RMSE) |
| :--- | :---: | :---: | :---: |
| **Random Forest Regressor** | **97.44%** | **2,074,801 VND** | **4,204,494 VND** |
| **Gradient Boosting Regressor** | 96.94% | 2,246,808 VND | 4,596,256 VND |
| **Ridge Linear Regression** | 89.28% | 3,842,506 VND | 8,610,612 VND |

#### Generalization Across Unseen GPU Architectures (5-Fold GroupKFold by `gpu_model`)
Evaluated across isolated GPU models to test model capacity when pricing previously unseen hardware generations:

| Model Architecture | GroupKFold Mean $R^2$ | Standard Deviation |
| :--- | :---: | :---: |
| **Gradient Boosting Regressor** | **67.19%** | **+/- 11.45%** |
| **Random Forest Regressor** | 63.24% | +/- 13.82% |
| **Linear Regression** | 52.80% | +/- 16.10% |

---

## 6. Reproducible Execution Guide

### Step 1: Environment Initialization
Clone the repository and set up a Python 3.11+ virtual environment:

```bash
git clone https://github.com/ThienTT38/ProjectCrawl_VGA.git
cd ProjectCrawl_VGA

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Sequential Data Pipeline Execution
Run the data processing stages sequentially from raw snapshots:

```bash
# 1. Clean raw records, deduplicate SKUs, and unify currency to VND
python pipeline/clean_and_unify.py

# 2. Execute multi-tier hierarchical price imputation (Tiers 1 to 4)
python pipeline/impute_prices.py

# 3. Complete 100% price coverage using TechPowerUp MSRP and depreciation (Tier 5)
python pipeline/build_100pct_solutions.py

# 4. Apply Vietnamese retail realism (Charm Pricing) and preserve authentic discounts
python pipeline/clean_realism_prices.py

# 5. Build 3-week longitudinal dataset and isolate pure observed tracking data
python pipeline/build_3weeks_dataset.py
```

### Step 3: Train Machine Learning Models and Valuate Listings
Train the leakage-free models and generate downstream price valuation recommendations:

```bash
python ml/ml_price_prediction.py
```

### Step 4: Run Automated Verification and Unit Tests
Execute the verification suite to independently validate all data integrity constraints and bug fixes:

```bash
# Run unit test suite
python -m unittest discover -s tests -v

# Run scientific critique verification audit (Validates all 10 critique items)
python tests/verify_all_fixes.py
```

### Optional: Interactive Multi-Site Crawler CLI
Run the interactive menu crawler or launch individual scrapers:

```bash
# Launch interactive crawler menu (Phong Vu, Mega, Phi Long, BuildCores)
python main.py

# Or run individual site crawlers directly
python crawlers/crawl_phongvu.py
python crawlers/crawl_mega.py
python crawlers/crawl_philong.py
python crawlers/crawl_buildcores.py
```

---

## 7. License and Terms of Use

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
All scraped distributor data is used strictly for academic research and educational modeling purposes.
