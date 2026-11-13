# Contributing to the VGA Price Prediction and Market Intelligence Platform

Thank you for your interest in contributing to the **ProjectCrawl_VGA** platform. This project maintains high standards of data engineering integrity, reproducible scientific evaluation, and code quality.

Please review the guidelines below prior to submitting pull requests or proposing architectural modifications.

---

## 1. Project Overview and Philosophy

This platform implements an automated end-to-end data pipeline for:
- Multi-source retail e-commerce scraping from Vietnamese computer hardware distributors and international hardware repositories.
- Schema-first normalization, feature extraction, and dual-key hardware specification enrichment.
- Hierarchical multi-tier price imputation with explicit provenance tracking.
- Leakage-free machine learning modeling for cross-sectional price prediction and market valuation.

All contributions must adhere to the following principles:
- **Reproducibility:** Code must execute deterministically from an empty clone without requiring hardcoded local machine paths.
- **Scientific Integrity:** Machine learning models must be trained and evaluated without data leakage. Transformations must be encapsulated within pipeline folds.
- **Ground-Truth Preservation:** Authentic observed retail data points must never be overwritten or conflated with synthetic or formula-generated estimations.
- **Relational Integrity:** Deterministic identifiers (e.g., SHA-256 URL hashes) must prevent duplicate primary key collisions.

---

## 2. Development Setup

### 2.1. Environment Configuration
Clone the repository and initialize an isolated virtual environment:

```bash
git clone https://github.com/ThienTT38/ProjectCrawl_VGA.git
cd ProjectCrawl_VGA

# Initialize virtual environment
python -m venv .venv

# Activate environment
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1
# On Linux / macOS:
source .venv/bin/activate

# Install locked dependencies
pip install -r requirements.txt
```

### 2.2. Package Hierarchy
The repository is modularized into discrete functional packages:
- `adapters/`: Source-specific parsers inheriting from `BaseAdapter`.
- `core/`: HTTP drivers, retry policies, and compatibility utilities.
- `crawlers/`: Runnable scraping tasks and site registries.
- `normalizers/`: Regular expression extraction for hardware specifications and brands.
- `schemas/`: Pydantic data contracts (`NormalizedVGASchema`).
- `pipeline/`: Sequential data cleaning, imputation, and time-series synthesis scripts.
- `ml/`: Model training, cross-validation, and inference prediction routines.
- `storage/`: Database exporters and relational schema management (SQLite, CSV, JSON).
- `tests/`: Automated unit tests and critique verification suites.

---

## 3. Contribution Workflow

### 3.1. Branching Strategy
- `main`: Production-ready, verified codebase. Direct commits to `main` are restricted to maintainers.
- Feature branches: Create dedicated branches from `main` using descriptive naming:
  - `feat/feature-name` for new scrapers, models, or pipeline stages.
  - `fix/bug-description` for defect resolutions.
  - `docs/documentation-update` for documentation and scientific report updates.

### 3.2. Commit Message Standards
Commits must follow the Conventional Commits specification:
- `feat:` Introduces a new feature or architectural capability.
- `fix:` Patches a bug or rectifies a data engineering defect.
- `docs:` Documentation additions or updates (README, reports, contributing guide).
- `test:` Introduces new unit tests or updates the verification suite.
- `refactor:` Code reorganization without functional changes.

---

## 4. Engineering and Scientific Guidelines

### 4.1. Adding New Retail Adapters
When implementing a new retail scraper:
1. Inherit from `adapters.base_adapter.BaseAdapter`.
2. Validate every record against `schemas.vga_schema.NormalizedVGASchema`.
3. Route invalid non-GPU accessory items (e.g., riser cables, brackets) to the Dead-Letter Queue via `record_dead_letter(...)`.
4. Ensure primary keys are computed deterministically via 16-character SHA-256 URL hashing.

### 4.2. Machine Learning and Evaluation Standards
1. **Zero Data Leakage:** Preprocessing transformations (imputation, scaling, one-hot encoding) must be encapsulated inside `sklearn.pipeline.Pipeline` or `sklearn.compose.ColumnTransformer`. Never fit transformations across the full dataset prior to splitting.
2. **Ground-Truth Benchmarking:** Always benchmark predictive models against the isolated authentic observed retail subset (`ACTUAL_STORE_RETAIL`) in addition to any full test partitions.
3. **Out-of-Distribution Validation:** Evaluate generalization across unseen GPU architectures using `GroupKFold` grouped by `gpu_model`.

### 4.3. Code Style and Quality
- Use Python 3.11+ type annotations (`typing.Optional`, `typing.List`, `typing.Dict`).
- Maintain UTF-8 encoding across all file operations.
- Avoid introducing casual emojis or presentation icons in production logs, README files, or academic documentation.

---

## 5. Verification and Testing

Prior to opening a pull request, all automated test suites must pass completely:

```bash
# Execute unit test suite (All 12 tests must pass)
python -m unittest discover -s tests -v

# Execute scientific critique verification audit (All 10 checks must pass)
python tests/verify_all_fixes.py

# Verify model training and inference
python ml/ml_price_prediction.py
```

---

## 6. Project Lead and Contact

- **Lead Maintainer:** Tran Thanh Thien ([@ThienTT38](https://github.com/ThienTT38))
- **Email:** `tranthanhthien792@gmail.com`
- **Issue Tracker:** [GitHub Issues](https://github.com/ThienTT38/ProjectCrawl_VGA/issues)
