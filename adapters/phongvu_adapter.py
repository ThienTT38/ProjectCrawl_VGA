"""
Upgraded Phong Vũ Adapter (`https://phongvu.vn/c/vga-card-man-hinh`).
Integrates the user's 2-step Selenium + BeautifulSoup scraper (Load-more button
`'Xem thêm sản phẩm'`, spec expansion `'Xem thêm'`, `css-8a82ns`, `css-1lr8xjg`,
`css-ciimlz` / `css-9zbh2u`) as well as Teko Discovery JSON into `NormalizedVGASchema`.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from adapters.base_adapter import BaseVGAAdapter
from core.http_html import parse_html_tree
from schemas.vga_schema import SourceSite


class PhongVuAdapter(BaseVGAAdapter):
    """
    Adapter for `https://phongvu.vn/c/vga-card-man-hinh`.
    """

    source = SourceSite.PHONGVU
    base_url = "https://phongvu.vn"
    category_url = "https://phongvu.vn/c/vga-card-man-hinh"
    save_prefix = "phongvu_full"
    request_delay_sec = 1.5

    # -------------------------------------------------------------------------
    # Step 1 (Selenium): Quét danh mục Phong Vũ & bấm 'Xem thêm sản phẩm'
    # -------------------------------------------------------------------------
    def get_all_product_links(
        self,
        driver: Any,
        start_url: Optional[str] = None,
        max_pages: Optional[int] = None,
    ) -> List[str]:
        from bs4 import BeautifulSoup
        from selenium.common.exceptions import TimeoutException
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait

        target_url = start_url or self.category_url
        print(f"\n[BƯỚC 1] Đang truy cập trang danh mục Phong Vũ: {target_url}")
        driver.get(target_url)
        time.sleep(5)

        click_count = 0
        max_clicks = max_pages if (max_pages is not None and max_pages > 0) else 60

        while click_count < max_clicks:
            try:
                driver.execute_script(
                    "window.scrollTo(0, document.body.scrollHeight - 500);"
                )
                time.sleep(1.5)

                xpath_btn = "//div[contains(text(), 'Xem thêm sản phẩm')] | //*[contains(text(), 'Xem thêm sản phẩm')]"
                btn = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, xpath_btn))
                )

                driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});", btn
                )
                time.sleep(1)
                driver.execute_script("arguments[0].click();", btn)

                click_count += 1
                print(f" -> Đã bấm 'Xem thêm sản phẩm' lần thứ {click_count}")
                time.sleep(2.5)
            except TimeoutException:
                print(
                    " -> Đã tải hết danh sách sản phẩm (không còn nút Xem thêm)."
                )
                break
            except Exception as exc:
                print(f" -> Dừng click do: {exc}")
                break

        soup = BeautifulSoup(driver.page_source, "html.parser")
        product_links: List[str] = []
        seen_links: set[str] = set()

        for a in soup.find_all("a", href=True):
            href = a["href"]
            href_lower = href.lower()
            if (
                ("vga" in href_lower or "card-man-hinh" in href_lower)
                and "help.phongvu.vn" not in href_lower
                and "/cong-nghe/" not in href_lower
                and "/c/" not in href_lower
            ):
                full_url = (
                    href
                    if href.startswith("http")
                    else "https://phongvu.vn" + href
                )
                if "phongvu.vn" in full_url and full_url not in seen_links:
                    seen_links.add(full_url)
                    product_links.append(full_url)

        print(f"==> Tổng số link sản phẩm thu thập được: {len(product_links)}\n")
        return product_links

    # -------------------------------------------------------------------------
    # Step 2 (Selenium): Cào chi tiết sản phẩm & bấm 'Xem thêm' cấu hình (`css-ciimlz`)
    # -------------------------------------------------------------------------
    def scrape_product_detail(self, driver: Any, url: str) -> Dict[str, Any]:
        from selenium.common.exceptions import TimeoutException
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait

        driver.get(url)
        time.sleep(3)

        try:
            xpath_spec_btn = "//div[contains(@class, 'button-text') and contains(text(), 'Xem thêm')]"
            show_specs_btn = WebDriverWait(driver, 8).until(
                EC.element_to_be_clickable((By.XPATH, xpath_spec_btn))
            )
            print("    -> Đã tìm thấy nút 'Xem thêm' cấu hình. Tiến hành click...")
            driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", show_specs_btn
            )
            time.sleep(1)
            driver.execute_script("arguments[0].click();", show_specs_btn)
            time.sleep(2)
        except TimeoutException:
            print(
                "    -> [Thông báo] Không tìm thấy nút 'Xem thêm' hoặc bảng đã mở sẵn."
            )
        except Exception as exc:
            print(f"    -> [Cảnh báo] Không thể click Xem thêm cấu hình: {exc}")

        return self.parse_detail_html(driver.page_source, url)

    def parse_detail_html(self, html_text: str, url: str) -> Dict[str, Any]:
        """
        Parse Phong Vũ product detail HTML (`h1`, `css-8a82ns`, `css-1lr8xjg`,
        and `css-ciimlz` -> `css-9zbh2u` -> `css-1kkiml9` / `css-prnj7r`).
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

        # 2. Giá khuyến mãi (`css-8a82ns` hoặc `.att-product-detail-latest-price`)
        for div in root.find_all(tag="div"):
            cls_str = div.attr("class")
            if (
                "css-8a82ns" in cls_str
                or "att-product-detail-latest-price" in cls_str
            ) and not product_data["Giá hiện tại"]:
                product_data["Giá hiện tại"] = div.get_text()
            elif "css-1lr8xjg" in cls_str and not product_data["Giá gốc"]:
                product_data["Giá gốc"] = div.get_text()

        if "Hết hàng" in root.get_text():
            product_data["Tình trạng"] = "Hết hàng"

        # 5. Đọc chi tiết thông số (`css-ciimlz` -> `css-9zbh2u` -> `css-1kkiml9` / `css-prnj7r`)
        for container in root.find_all(tag="div"):
            if "css-ciimlz" in container.attr("class"):
                for row in container.find_all(tag="div"):
                    if "css-9zbh2u" in row.attr("class"):
                        label_tag = None
                        value_tag = None
                        for child in row.find_all(tag="div"):
                            c_cls = child.attr("class")
                            if "css-1kkiml9" in c_cls and label_tag is None:
                                label_tag = child
                            elif "css-prnj7r" in c_cls and value_tag is None:
                                value_tag = child
                        if label_tag and value_tag:
                            key = label_tag.get_text()
                            val = value_tag.get_text(separator=" ")
                            if key and val:
                                product_data[key] = val
                                product_data["raw_specs"][key] = val

        return product_data

    # -------------------------------------------------------------------------
    # Payload Extraction & Schema-First Adaptation
    # -------------------------------------------------------------------------
    def extract_raw_items(self, raw_payload: Any) -> List[Dict[str, Any]]:
        if isinstance(raw_payload, list):
            return [self._flatten_teko_item(x) for x in raw_payload]
        if isinstance(raw_payload, dict):
            if "Link sản phẩm" in raw_payload or "Tên sản phẩm" in raw_payload:
                return [raw_payload]
            products = (
                raw_payload.get("products")
                or raw_payload.get("result", {}).get("products")
                or raw_payload.get("data", {}).get("products")
                or []
            )
            return [self._flatten_teko_item(x) for x in products]
        if not isinstance(raw_payload, str) or not raw_payload.strip():
            return []

        text = raw_payload.strip()
        if text.startswith("{") or text.startswith("["):
            try:
                return self.extract_raw_items(json.loads(text))
            except json.JSONDecodeError:
                pass

        if "css-ciimlz" in text or "css-8a82ns" in text:
            return [
                self.parse_detail_html(
                    text, "https://phongvu.vn/vga-sample--s123456"
                )
            ]

        return []

    def adapt_item(self, raw_item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize either:
          (A) Scraped detail dict from `scrape_product_detail` (`css-ciimlz` spec rows), OR
          (B) Teko Discovery JSON product record
        into `NormalizedVGASchema`.
        """
        raw_name = str(
            raw_item.get("Tên sản phẩm") or raw_item.get("raw_name") or ""
        ).strip()
        url_path = str(
            raw_item.get("Link sản phẩm") or raw_item.get("url") or ""
        ).strip()
        short_desc = str(raw_item.get("short_description") or "").strip()

        raw_specs = self.extract_legacy_specs_from_dict(raw_item)
        if isinstance(raw_item.get("attributes"), dict):
            for k, v in raw_item["attributes"].items():
                if k and v is not None:
                    raw_specs.setdefault(str(k), str(v))
        if raw_item.get("brand"):
            raw_specs.setdefault("Thương hiệu", str(raw_item["brand"]))
        if raw_item.get("mpn"):
            raw_specs.setdefault("Part Number", str(raw_item["mpn"]))
        if raw_item.get("warranty"):
            raw_specs.setdefault("Bảo hành", str(raw_item["warranty"]))

        spec_parsed = self.normalizer.parse_spec_table_dict(
            raw_specs=raw_specs,
            raw_title=f"{raw_name} {short_desc}",
            url=url_path,
        )

        raw_price = (
            raw_item.get("Giá hiện tại")
            if "Giá hiện tại" in raw_item
            else raw_item.get("raw_price")
        )
        raw_old_price = (
            raw_item.get("Giá gốc")
            if "Giá gốc" in raw_item
            else raw_item.get("raw_old_price")
        )
        raw_stock = (
            raw_item.get("Tình trạng")
            if "Tình trạng" in raw_item
            else raw_item.get("raw_stock")
        )

        price_vnd = self.normalizer.normalize_price_vnd(raw_price)
        original_price_vnd = self.normalizer.normalize_price_vnd(raw_old_price)
        stock_status = self.normalizer.normalize_stock_status(
            raw_stock, price_vnd=price_vnd
        )

        raw_sku = str(
            raw_item.get("sku")
            or raw_specs.get("SKU")
            or self._extract_sku_from_url(url_path)
        )
        sku = raw_sku if raw_sku.startswith("PV-") else f"PV-{raw_sku}"

        return {
            "sku": sku,
            "raw_name": raw_name,
            "url": self.resolve_url(url_path) or self.category_url,
            "image_url": self.resolve_url(raw_item.get("image_url")),
            "price_vnd": price_vnd,
            "original_price_vnd": original_price_vnd,
            "stock_status": stock_status,
            **spec_parsed,
        }

    def _flatten_teko_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        if "raw_name" in item or "Tên sản phẩm" in item:
            return item

        info = item.get("productInfo") or item
        prices = item.get("prices") or (
            item.get("price") if isinstance(item.get("price"), dict) else {}
        )
        brand_obj = info.get("brand") or {}
        brand_name = (
            brand_obj.get("name")
            if isinstance(brand_obj, dict)
            else str(brand_obj or "")
        )

        canonical = info.get("canonical") or info.get("slug") or info.get("url") or ""
        sku = str(info.get("sku") or item.get("sku") or "UNKNOWN")
        if canonical and not canonical.startswith(("http://", "https://", "/")):
            canonical = f"/{canonical.lstrip('/')}"
            if not canonical.endswith(sku) and f"--s{sku}" not in canonical:
                canonical = f"{canonical}--s{sku}"

        images = info.get("images") or []
        first_img = (
            images[0].get("url")
            if (images and isinstance(images[0], dict))
            else info.get("imageUrl") or info.get("image")
        )

        latest_price = (
            prices.get("latestPrice")
            or prices.get("terminalPrice")
            or prices.get("sellPrice")
            or info.get("latestPrice")
        )
        old_price = (
            prices.get("supplierRetailPrice")
            or prices.get("retailPrice")
            or info.get("supplierRetailPrice")
        )

        raw_attrs = item.get("attributes") or info.get("attributes") or {}
        attrs_dict: Dict[str, Any] = {}
        if isinstance(raw_attrs, list):
            for attr in raw_attrs:
                if isinstance(attr, dict) and attr.get("code"):
                    attrs_dict[str(attr["code"])] = attr.get("value")
        elif isinstance(raw_attrs, dict):
            attrs_dict = raw_attrs

        total_avail = item.get("totalAvailable")
        raw_stock = item.get("status")
        if raw_stock is None and isinstance(total_avail, int):
            raw_stock = "Còn hàng" if total_avail > 0 else "Hết hàng"

        return {
            "sku": sku,
            "mpn": info.get("partNumber") or info.get("mpn"),
            "raw_name": info.get("name") or info.get("displayName") or "",
            "brand": brand_name,
            "url": canonical or f"https://phongvu.vn/p/{sku}",
            "image_url": first_img,
            "raw_price": latest_price,
            "raw_old_price": old_price,
            "raw_stock": raw_stock,
            "warranty": info.get("warranty") or info.get("warrantyMonths"),
            "short_description": info.get("shortDescription") or "",
            "attributes": attrs_dict,
        }

    @staticmethod
    def _extract_sku_from_url(href: str) -> str:
        m = re.search(r"--s(\d{5,10})", href)
        if m:
            return m.group(1)
        slug = href.strip("/").split("/")[-1]
        return slug[:20].upper() if slug else "UNKNOWN"
