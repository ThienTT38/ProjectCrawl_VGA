"""
Base Adapter implementing the Schema-First Scraping / Adapter Pattern.
Upgraded directly on top of the user's 2-step Selenium + BeautifulSoup workflow:
  - Step 1: `get_all_product_links(driver, start_url)` (Category pagination / Load-more)
  - Step 2: `scrape_product_detail(driver, url)` (Detail page + Spec table modal click)
  - Step 3: `adapt_item(raw_item)` -> `NormalizedVGASchema` (Normalize at Source!)
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from core.compat import ValidationError
from normalizers.vga_normalizer import NonVGAAccessoryError, VGANormalizer
from schemas.vga_schema import DeadLetterRecord, NormalizedVGASchema, SourceSite

logger = logging.getLogger("vga_crawler.adapter")

# Standard base keys used by the legacy `scrape_product_detail` dictionary
LEGACY_META_KEYS = {
    "Link sản phẩm",
    "Tên sản phẩm",
    "Giá hiện tại",
    "Giá gốc",
    "Tình trạng",
    "Thời gian cào",
    "sku",
    "mpn",
    "raw_name",
    "url",
    "image_url",
    "raw_price",
    "raw_old_price",
    "raw_stock",
    "raw_warranty",
    "summary_text",
    "spec_text",
    "raw_specs",
}


@dataclass
class AdapterBatchResult:
    """Result container returned by an Adapter execution."""

    source: SourceSite
    valid_records: List[NormalizedVGASchema] = field(default_factory=list)
    dead_letters: List[DeadLetterRecord] = field(default_factory=list)

    @property
    def total_processed(self) -> int:
        return len(self.valid_records) + len(self.dead_letters)

    @property
    def success_rate(self) -> float:
        if self.total_processed == 0:
            return 100.0
        return round((len(self.valid_records) / self.total_processed) * 100.0, 2)


class BaseVGAAdapter(ABC):
    """
    Abstract Adapter unifying:
      1. Legacy 2-step Selenium + BeautifulSoup scraping (`get_all_product_links` & `scrape_product_detail`)
      2. Offline/Fixture HTML & JSON extraction (`extract_raw_items` & `parse_detail_html`)
      3. Immediate Schema-First Normalization (`adapt_item` -> `NormalizedVGASchema`)
      4. Dead-Letter Queue (`DeadLetterRecord`) isolation for non-VGA accessories & invalid items
    """

    source: SourceSite
    base_url: str
    category_url: str
    save_prefix: str
    request_delay_sec: float = 1.2

    def __init__(self, timeout: float = 20.0) -> None:
        self.timeout = timeout
        self.normalizer = VGANormalizer()

    # -------------------------------------------------------------------------
    # Abstract / Hook Methods for Concrete Adapters (Philong, Mega, PhongVu, BuildCores)
    # -------------------------------------------------------------------------
    @abstractmethod
    def get_all_product_links(
        self,
        driver: Any,
        start_url: Optional[str] = None,
        max_pages: Optional[int] = None,
    ) -> List[str]:
        """Step 1 (Selenium): Collect all unique product detail URLs from category page."""

    @abstractmethod
    def scrape_product_detail(self, driver: Any, url: str) -> Dict[str, Any]:
        """Step 2 (Selenium): Open product detail URL, expand spec modal/table, and extract raw dict."""

    @abstractmethod
    def parse_detail_html(self, html_text: str, url: str) -> Dict[str, Any]:
        """Parse a product detail page HTML string into a raw product dict (with spec table rows)."""

    @abstractmethod
    def extract_raw_items(self, raw_payload: Any) -> List[Dict[str, Any]]:
        """Extract raw item dicts from HTML/JSON payload (category HTML, detail HTML, or dict list)."""

    @abstractmethod
    def adapt_item(self, raw_item: Dict[str, Any]) -> Dict[str, Any]:
        """Transform a raw item dict (from detail page or category card) into `NormalizedVGASchema` fields."""

    # -------------------------------------------------------------------------
    # Shared Helper Utilities
    # -------------------------------------------------------------------------
    def resolve_url(self, path_or_url: Optional[str]) -> Optional[str]:
        """Resolve relative URLs against the adapter's `base_url`."""
        if not path_or_url:
            return None
        cleaned = path_or_url.strip()
        if cleaned.startswith(("http://", "https://")):
            return cleaned
        return urljoin(self.base_url, cleaned)

    @staticmethod
    def extract_legacy_specs_from_dict(raw_item: Dict[str, Any]) -> Dict[str, str]:
        """
        Extract all dynamic specification table rows added via `product_data[key] = val`
        in the legacy `scrape_product_detail` format, merging with explicit `raw_specs`.
        """
        specs: Dict[str, str] = {}
        if isinstance(raw_item.get("raw_specs"), dict):
            for k, v in raw_item["raw_specs"].items():
                if k and v is not None:
                    specs[str(k)] = str(v)

        for k, v in raw_item.items():
            if k not in LEGACY_META_KEYS and isinstance(v, (str, int, float)):
                val_str = str(v).strip()
                if val_str and val_str != "Unknown":
                    specs[k] = val_str
        return specs

    # -------------------------------------------------------------------------
    # Schema-First Normalization & Validation Pipeline
    # -------------------------------------------------------------------------
    def normalize_single_item(
        self, raw_item: Dict[str, Any], batch: AdapterBatchResult
    ) -> Optional[NormalizedVGASchema]:
        """
        Normalize and validate a single raw item right at the source boundary.
        Appends either to `batch.valid_records` or `batch.dead_letters`.
        """
        raw_url = str(
            raw_item.get("Link sản phẩm") or raw_item.get("url") or ""
        ).strip()
        raw_id = str(
            raw_item.get("sku")
            or raw_item.get("id")
            or raw_item.get("opendb_id")
            or raw_url
            or "unknown"
        )
        raw_title = str(
            raw_item.get("Tên sản phẩm")
            or raw_item.get("raw_name")
            or raw_item.get("name")
            or raw_item.get("title")
            or ""
        ).strip()

        try:
            # 1. Domain Guard: Filter out VGA holders, riser cables, brackets immediately
            self.normalizer.assert_is_vga_product(raw_title)

            # 2. Source Adapter Mapping & Spec Table Normalization
            adapted_dict = self.adapt_item(raw_item)
            adapted_dict["source"] = self.source

            # 3. Strict Schema-First Validation
            validated = NormalizedVGASchema.model_validate(adapted_dict)
            batch.valid_records.append(validated)
            return validated

        except NonVGAAccessoryError as acc_err:
            logger.info(
                "[%s] Đã chặn phụ kiện không phải VGA (%s): %s",
                self.source.value,
                raw_id,
                acc_err,
            )
            batch.dead_letters.append(
                DeadLetterRecord(
                    source=self.source.value,
                    raw_identifier=raw_id,
                    raw_title=raw_title,
                    reason=f"NonVGAAccessory: {acc_err}",
                    raw_payload=raw_item,
                )
            )
        except ValidationError as val_err:
            logger.warning(
                "[%s] Lỗi kiểm định Schema cho SP (%s - %s): %s",
                self.source.value,
                raw_id,
                raw_title,
                val_err,
            )
            batch.dead_letters.append(
                DeadLetterRecord(
                    source=self.source.value,
                    raw_identifier=raw_id,
                    raw_title=raw_title,
                    reason=f"SchemaValidationError: {val_err}",
                    raw_payload=raw_item,
                )
            )
        except Exception as exc:
            logger.warning(
                "[%s] Lỗi chuyển đổi Adapter cho SP (%s - %s): %s",
                self.source.value,
                raw_id,
                raw_title,
                exc,
            )
            batch.dead_letters.append(
                DeadLetterRecord(
                    source=self.source.value,
                    raw_identifier=raw_id,
                    raw_title=raw_title,
                    reason=f"AdapterTransformError: {exc}",
                    raw_payload=raw_item,
                )
            )
        return None

    def process_payload(self, raw_payload: Any) -> AdapterBatchResult:
        """Process a batch payload (HTML, JSON, or list of raw dicts) through Schema-First validation."""
        batch = AdapterBatchResult(source=self.source)
        raw_items = self.extract_raw_items(raw_payload)
        for raw_item in raw_items:
            self.normalize_single_item(raw_item, batch)
        return batch

    # -------------------------------------------------------------------------
    # Unified 2-Step Selenium Crawler Template Method (Replaces duplicated `crawl()`)
    # -------------------------------------------------------------------------
    def crawl_with_selenium(
        self,
        headless: bool = False,
        max_pages: Optional[int] = None,
        max_products: Optional[int] = None,
        save_interval: int = 10,
        output_dir: str = "output",
    ) -> AdapterBatchResult:
        """
        Executes the full 2-step Selenium crawl lifecycle with real-time Schema-First normalization:
          1. Launch Chrome WebDriver via `utils.get_driver()`
          2. Run `get_all_product_links(driver, self.category_url)`
          3. Visit each product URL via `scrape_product_detail(driver, url)`
          4. Normalize & validate each product immediately at the source (`normalize_single_item`)
          5. Checkpoint to SQLite + JSON + CSV every `save_interval` items via `utils.save_data_to_files()`
        """
        from utils import get_driver, save_data_to_files

        batch = AdapterBatchResult(source=self.source)
        print(f"Đang khởi động trình duyệt Chrome cho [{self.source.value.upper()}]...")
        driver = get_driver(headless=headless)

        try:
            product_urls = self.get_all_product_links(
                driver, self.category_url, max_pages=max_pages
            )
            if not product_urls:
                print(
                    f"[{self.source.value.upper()}] Không tìm thấy link sản phẩm nào. Kết thúc quá trình!"
                )
                return batch

            if max_products is not None and max_products > 0:
                product_urls = product_urls[:max_products]

            print("\n" + "=" * 65)
            print(
                f"[{self.source.value.upper()} - BƯỚC 2] TRÍCH XUẤT CHI TIẾT & CHUẨN HÓA TẠI NGUỒN ({len(product_urls)} SP)"
            )
            print("=" * 65 + "\n")

            for idx, url in enumerate(product_urls, 1):
                print(f"[{idx}/{len(product_urls)}] Đang cào & chuẩn hóa: {url}")
                raw_detail = self.scrape_product_detail(driver, url)
                normalized_item = self.normalize_single_item(raw_detail, batch)

                if normalized_item is not None:
                    print(
                        f"    -> [OK] {normalized_item.normalized_name} | "
                        f"GPU: {normalized_item.gpu_model} | VRAM: {normalized_item.vram_gb}GB {normalized_item.vram_type.value} | "
                        f"Giá: {normalized_item.price_vnd or normalized_item.price_usd or 'Liên hệ'}"
                    )
                else:
                    last_dl = batch.dead_letters[-1] if batch.dead_letters else None
                    print(
                        f"    -> [CHẶN DLQ] Đã loại bỏ bản ghi không hợp lệ: {last_dl.reason if last_dl else ''}"
                    )

                if idx % save_interval == 0:
                    save_data_to_files(
                        batch.valid_records,
                        self.save_prefix,
                        dead_letters=batch.dead_letters,
                        output_dir=output_dir,
                    )

                time.sleep(self.request_delay_sec)

        except KeyboardInterrupt:
            print("\n[!] Người dùng chủ động dừng chương trình (Ctrl + C)!")
        except Exception as exc:
            print(f"\n[!] Có lỗi bất ngờ xảy ra: {exc}")
        finally:
            print("\nĐang đóng trình duyệt...")
            try:
                driver.quit()
            except Exception:
                pass

            if batch.valid_records or batch.dead_letters:
                print("\nĐang lưu dữ liệu chuẩn hóa lần cuối...")
                save_data_to_files(
                    batch.valid_records,
                    self.save_prefix,
                    dead_letters=batch.dead_letters,
                    output_dir=output_dir,
                )
                print(
                    f"HOÀN TẤT [{self.source.value.upper()}]! "
                    f"Hợp lệ: {len(batch.valid_records)} SP | Chặn rác (DLQ): {len(batch.dead_letters)} SP."
                )
            else:
                print("Chưa có dữ liệu nào được thu thập.")

        return batch

    async def crawl_live(self, max_pages: int = 1) -> AdapterBatchResult:
        """Async wrapper around `crawl_with_selenium` for orchestrator compatibility."""
        import asyncio

        return await asyncio.to_thread(
            self.crawl_with_selenium,
            headless=True,
            max_pages=max_pages,
        )
