"""
Upgraded `utils.py` compatible with the legacy crawler scripts (`get_driver`, `save_data_to_files`),
now integrated with Schema-First validation, SQLite persistence, and normalized JSON/CSV export.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, List, Optional, Sequence, Union

from schemas.vga_schema import DeadLetterRecord, NormalizedVGASchema
from storage.exporter import StorageManager


def get_driver(headless: bool = False, page_load_timeout: int = 35) -> Any:
    """
    Initialize and return a configured Selenium Chrome WebDriver.
    Includes anti-detection flags, disabled notifications, and optimized page load strategy.
    """
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    options = Options()
    if headless:
        options.add_argument("--headless=new")

    options.add_argument("--start-maximized")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    )

    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(page_load_timeout)
    return driver


def save_data_to_files(
    records: Sequence[Union[NormalizedVGASchema, dict[str, Any]]],
    prefix: str,
    dead_letters: Optional[Sequence[DeadLetterRecord]] = None,
    output_dir: str | Path = "output",
) -> dict[str, Path]:
    """
    Upgraded checkpoint saver called every `SAVE_INTERVAL` items and on final exit.
    Accepts `NormalizedVGASchema` instances (or dicts validated into `NormalizedVGASchema`)
    and writes to:
      - `output/vga_catalog.db` (SQLite upsert)
      - `output/{prefix}_normalized.json`
      - `output/{prefix}_normalized.csv`
      - `output/{prefix}_dead_letters.json` (if dead_letters provided)
    """
    storage = StorageManager(output_dir=output_dir)

    normalized_list: List[NormalizedVGASchema] = []
    for item in records:
        if isinstance(item, NormalizedVGASchema):
            normalized_list.append(item)
        elif isinstance(item, dict):
            normalized_list.append(NormalizedVGASchema.model_validate(item))

    dl_list = list(dead_letters) if dead_letters else []

    storage.save_to_sqlite(normalized_list, dl_list)
    json_path = storage.export_json(normalized_list, f"{prefix}_normalized.json")
    csv_path = storage.export_csv(normalized_list, f"{prefix}_normalized.csv")

    saved = {
        "sqlite_db": storage.db_path,
        "json": json_path,
        "csv": csv_path,
    }
    if dl_list:
        dl_path = storage.export_dead_letters_json(dl_list, f"{prefix}_dead_letters.json")
        saved["dead_letters"] = dl_path

    print(
        f"    [SAVED] Đã lưu chuẩn hóa {len(normalized_list)} SP vào SQLite, "
        f"{json_path.name} và {csv_path.name} (Chặn {len(dl_list)} bản ghi lỗi/phụ kiện)."
    )
    return saved
