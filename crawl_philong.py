"""
Drop-in upgraded Phi Long Technology crawler script (`crawl_philong.py`).
Uses `PhilongAdapter` to execute the 2-step Selenium crawl (`https://philong.com.vn/card-do-hoa.html`)
and normalize records immediately at the source into `NormalizedVGASchema`.
"""

from __future__ import annotations

from typing import List, Optional

from adapters.philong_adapter import PhilongAdapter
from schemas.vga_schema import NormalizedVGASchema


def crawl(
    headless: bool = False,
    max_pages: Optional[int] = None,
    max_products: Optional[int] = None,
    save_interval: int = 10,
) -> List[NormalizedVGASchema]:
    adapter = PhilongAdapter()
    batch = adapter.crawl_with_selenium(
        headless=headless,
        max_pages=max_pages,
        max_products=max_products,
        save_interval=save_interval,
    )
    return batch.valid_records


if __name__ == "__main__":
    crawl()
