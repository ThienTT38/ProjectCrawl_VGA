"""
Drop-in upgraded BuildCores crawler script (`crawl_buildcores.py`).
Uses `BuildCoresAdapter` to execute the 2-step Selenium crawl and normalize records
immediately at the source into `NormalizedVGASchema`.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from adapters.buildcores_adapter import BuildCoresAdapter
from schemas.vga_schema import NormalizedVGASchema


def crawl(
    headless: bool = False,
    max_pages: Optional[int] = None,
    max_products: Optional[int] = None,
    save_interval: int = 10,
) -> List[NormalizedVGASchema]:
    adapter = BuildCoresAdapter()
    batch = adapter.crawl_with_selenium(
        headless=headless,
        max_pages=max_pages,
        max_products=max_products,
        save_interval=save_interval,
    )
    return batch.valid_records


if __name__ == "__main__":
    crawl()
