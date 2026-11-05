"""
Upgraded BuildCores Adapter (`https://www.buildcores.com/products/GPU`).
Integrates the user's 2-step Selenium + BeautifulSoup scraper (`data-testid='part-card'`,
`button[data-testid='pagination-next']`, `div[data-part-details-spec-row='true']`)
with Schema-First Normalization (`NormalizedVGASchema`).
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from adapters.base_adapter import BaseVGAAdapter
from core.http_html import parse_html_tree
from schemas.vga_schema import SourceSite, StockStatus


class BuildCoresAdapter(BaseVGAAdapter):
    """
    Adapter for `https://www.buildcores.com/products/GPU` & `buildcores-open-db`.
    """

    source = SourceSite.BUILDCORES
    base_url = "https://www.buildcores.com"
    category_url = "https://www.buildcores.com/products/GPU"
    save_prefix = "buildcores"
    request_delay_sec = 1.0

    # -------------------------------------------------------------------------
    # Step 1 (Selenium): Quét danh sách link sản phẩm từ trang danh mục BuildCores
    # -------------------------------------------------------------------------
    def get_all_product_links(
        self,
        driver: Any,
        start_url: Optional[str] = None,
        max_pages: Optional[int] = None,
    ) -> List[str]:
        from bs4 import BeautifulSoup
        from selenium.common.exceptions import NoSuchElementException, TimeoutException
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait

        target_url = start_url or self.category_url
        print(f"\n[BƯỚC 1] ĐANG QUÉT DANH SÁCH SẢN PHẨM BUILDCORES: {target_url}")
        driver.get(target_url)
        time.sleep(4)  # Chờ Next.js hydrate DOM hoàn tất

        product_links: List[str] = []
        seen_links: set[str] = set()
        page_count = 1

        while True:
            print(f" -> Đang quét trang {page_count}...")
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "div[data-testid='part-card']")
                    )
                )
            except TimeoutException:
                print(" -> Hết thời gian chờ tải sản phẩm.")
                break

            soup = BeautifulSoup(driver.page_source, "html.parser")
            cards = soup.find_all("div", attrs={"data-testid": "part-card"})

            new_links = 0
            for card in cards:
                part_id = card.get("data-part-buildcores-id")
                if part_id:
                    full_url = f"https://www.buildcores.com/products/GPU/{part_id.strip()}"
                    if full_url not in seen_links:
                        seen_links.add(full_url)
                        product_links.append(full_url)
                        new_links += 1

            print(
                f"    + Thu thập được {new_links} sản phẩm ở trang {page_count}. "
                f"(Tổng tích lũy: {len(product_links)})"
            )

            if max_pages is not None and page_count >= max_pages:
                print(f" -> Đã đạt giới hạn max_pages={max_pages}.")
                break

            # Kiểm tra nút chuyển trang (Next)
            try:
                next_btn = driver.find_element(
                    By.CSS_SELECTOR, "button[data-testid='pagination-next']"
                )
                if next_btn.get_attribute("disabled"):
                    print(" -> Nút 'Next' đã bị vô hiệu hóa. Đã đến trang cuối cùng!")
                    break

                driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});", next_btn
                )
                time.sleep(0.5)
                driver.execute_script("arguments[0].click();", next_btn)

                page_count += 1
                time.sleep(3)
            except NoSuchElementException:
                print(" -> Không tìm thấy nút Next. Dừng phân trang.")
                break
            except Exception as exc:
                print(f" -> Lỗi khi bấm Next: {exc}")
                break

        print(f"==> TỔNG CỘNG THU THẬP: {len(product_links)} link sản phẩm.\n")
        return product_links

    # -------------------------------------------------------------------------
    # Step 2 (Selenium): Trích xuất chi tiết sản phẩm BuildCores
    # -------------------------------------------------------------------------
    def scrape_product_detail(self, driver: Any, url: str) -> Dict[str, Any]:
        from selenium.common.exceptions import TimeoutException
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait

        driver.get(url)
        time.sleep(2.5)

        try:
            WebDriverWait(driver, 8).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "div[data-testid='part-details-specs']")
                )
            )
        except TimeoutException:
            pass

        return self.parse_detail_html(driver.page_source, url)

    def parse_detail_html(self, html_text: str, url: str) -> Dict[str, Any]:
        """
        Parse BuildCores product detail HTML (`h1`, `part-details-best-price-value`,
        and `div[data-part-details-spec-row='true']`).
        Works with either BeautifulSoup4 or built-in stdlib DOM parser.
        """
        product_data: Dict[str, Any] = {
            "Link sản phẩm": url,
            "Tên sản phẩm": "",
            "Giá hiện tại": "",
            "Giá gốc": "",
            "Tình trạng": "Còn hàng",
            "Thời gian cào": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "raw_specs": {},
        }

        root = parse_html_tree(html_text)
        h1 = root.find_first(tag="h1")
        if h1:
            product_data["Tên sản phẩm"] = h1.get_text()

        price_node = root.find_first(
            tag="p", attr_filters={"data-testid": "part-details-best-price-value"}
        )
        if price_node:
            product_data["Giá hiện tại"] = price_node.get_text()

        spec_rows = root.find_all(
            tag="div", attr_filters={"data-part-details-spec-row": "true"}
        )
        for row in spec_rows:
            label_div = None
            val_div = None
            for child in row.find_all(tag="div"):
                cls_str = child.attr("class")
                if "font-medium" in cls_str and label_div is None:
                    label_div = child
                elif "wrap-break-word" in cls_str and val_div is None:
                    val_div = child

            if label_div and val_div:
                key = label_div.get_text()
                val = val_div.get_text(separator=" ")
                if key and val and val != "Unknown":
                    product_data[key] = val
                    product_data["raw_specs"][key] = val

        return product_data

    # -------------------------------------------------------------------------
    # Payload Extraction & Schema-First Adaptation
    # -------------------------------------------------------------------------
    def extract_raw_items(self, raw_payload: Any) -> List[Dict[str, Any]]:
        if isinstance(raw_payload, list):
            return raw_payload
        if isinstance(raw_payload, dict):
            if (
                "opendb_id" in raw_payload
                or "chipset" in raw_payload
                or "Link sản phẩm" in raw_payload
                or "Tên sản phẩm" in raw_payload
            ):
                return [raw_payload]
            return (
                raw_payload.get("items")
                or raw_payload.get("gpus")
                or raw_payload.get("products")
                or []
            )
        if isinstance(raw_payload, str) and raw_payload.strip():
            text = raw_payload.strip()
            if text.startswith("{") or text.startswith("["):
                return self.extract_raw_items(json.loads(text))
            if "data-part-details-spec-row" in text or "<h1" in text:
                return [
                    self.parse_detail_html(
                        text, "https://www.buildcores.com/products/GPU/sample"
                    )
                ]
        return []

    def adapt_item(self, raw_item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Adapt either:
          (A) Scraped HTML detail dict from `scrape_product_detail` / `parse_detail_html`, OR
          (B) BuildCores OpenDB JSON record
        into `NormalizedVGASchema`.
        """
        # Case A: Scraped detail dict from `scrape_product_detail`
        if "Link sản phẩm" in raw_item or "Tên sản phẩm" in raw_item:
            url = str(raw_item.get("Link sản phẩm") or raw_item.get("url") or "").strip()
            raw_name = str(raw_item.get("Tên sản phẩm") or raw_item.get("raw_name") or "").strip()
            raw_specs = self.extract_legacy_specs_from_dict(raw_item)

            spec_parsed = self.normalizer.parse_spec_table_dict(
                raw_specs=raw_specs, raw_title=raw_name, url=url
            )
            price_usd = self.normalizer.normalize_price_usd(
                raw_item.get("Giá hiện tại") or raw_item.get("raw_price")
            )
            part_id = url.rstrip("/").split("/")[-1] if url else "UNKNOWN"
            sku = part_id if part_id.startswith("BC-") else f"BC-{part_id[:12].upper()}"

            return {
                "sku": sku,
                "raw_name": raw_name,
                "url": self.resolve_url(url) or self.category_url,
                "image_url": raw_item.get("image_url"),
                "price_vnd": None,
                "original_price_vnd": None,
                "price_usd": price_usd,
                "stock_status": (
                    StockStatus.IN_STOCK if price_usd is not None else StockStatus.UNKNOWN
                ),
                **spec_parsed,
            }

        # Case B: Structured OpenDB JSON record
        metadata = raw_item.get("metadata") or {}
        raw_name = str(
            metadata.get("name") or raw_item.get("raw_name") or raw_item.get("name") or ""
        ).strip()
        part_numbers: List[str] = metadata.get("part_numbers") or []
        primary_mpn: Optional[str] = None
        for pn in part_numbers:
            pn_clean = str(pn).strip()
            if len(pn_clean) >= 5 and pn_clean.upper() not in ("OC", "NON-OC", "GAMING"):
                primary_mpn = pn_clean.upper()
                break

        synth_specs: Dict[str, Any] = {
            "Chipset Manufacturer": raw_item.get("chipset_manufacturer"),
            "Chipset": raw_item.get("chipset"),
            "Manufacturer": metadata.get("manufacturer") or raw_item.get("manufacturer"),
            "Series": metadata.get("series") or metadata.get("variant"),
            "Part Numbers": primary_mpn or ", ".join(str(p) for p in part_numbers),
            "Memory": f"{raw_item.get('memory')} GB" if raw_item.get("memory") else None,
            "Memory Type": raw_item.get("memory_type"),
            "Core Boost Clock": (
                f"{raw_item.get('core_boost_clock')} MHz"
                if raw_item.get("core_boost_clock")
                else None
            ),
            "TDP": f"{raw_item.get('tdp')} W" if raw_item.get("tdp") else None,
            "Length": f"{raw_item.get('length')} mm" if raw_item.get("length") else None,
            "Total Slot Width": raw_item.get("total_slot_width"),
            "Cooling": raw_item.get("cooling"),
            "Power Connectors": self.normalizer.format_power_connectors(
                raw_item.get("power_connectors")
            ),
        }
        opendb_id = str(raw_item.get("opendb_id") or raw_item.get("sku") or "UNKNOWN")
        url = raw_item.get("url") or f"https://www.buildcores.com/products/GPU/{opendb_id}"

        spec_parsed = self.normalizer.parse_spec_table_dict(
            raw_specs=synth_specs, raw_title=raw_name, url=url
        )
        if primary_mpn:
            spec_parsed["mpn"] = primary_mpn

        price_usd = self._extract_usd_price(raw_item)
        sku = opendb_id if opendb_id.startswith("BC-") else f"BC-{opendb_id[:12].upper()}"

        return {
            "sku": sku,
            "raw_name": raw_name,
            "url": self.resolve_url(url) or self.category_url,
            "image_url": raw_item.get("image_url"),
            "price_vnd": None,
            "original_price_vnd": None,
            "price_usd": price_usd,
            "stock_status": (
                StockStatus.IN_STOCK if price_usd is not None else StockStatus.UNKNOWN
            ),
            **spec_parsed,
        }

    @staticmethod
    def _extract_usd_price(raw_item: Dict[str, Any]) -> Optional[float]:
        if isinstance(raw_item.get("price_usd"), (int, float)):
            return float(raw_item["price_usd"])
        gen_info = raw_item.get("general_product_information") or {}
        if isinstance(gen_info.get("msrp_usd"), (int, float)):
            return float(gen_info["msrp_usd"])
        identifiers = raw_item.get("identifiers") or {}
        listings = identifiers.get("retailer_listings") or []
        for listing in listings:
            if isinstance(listing, dict) and isinstance(listing.get("price"), (int, float)):
                return float(listing["price"])
        return None
