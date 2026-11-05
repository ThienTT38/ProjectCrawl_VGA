"""
Upgraded MEGA Technology Adapter (`https://mega.com.vn/card-do-hoa`).
Integrates the user's 2-step Selenium + BeautifulSoup scraper (`div.product-item`,
pagination `'»'` / `rel='next'`, button `'Xem toàn bộ'`, `table.table-spec`)
with Schema-First Normalization (`NormalizedVGASchema`).
"""

from __future__ import annotations

import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from adapters.base_adapter import BaseVGAAdapter
from core.http_html import parse_html_tree
from schemas.vga_schema import SourceSite


class MegaAdapter(BaseVGAAdapter):
    """
    Adapter for `https://mega.com.vn/card-do-hoa`.
    """

    source = SourceSite.MEGA
    base_url = "https://mega.com.vn"
    category_url = "https://mega.com.vn/card-do-hoa"
    save_prefix = "mega_final"
    request_delay_sec = 1.0

    # -------------------------------------------------------------------------
    # Step 1 (Selenium): Quét link từ danh mục Mega (`https://mega.com.vn/card-do-hoa`)
    # -------------------------------------------------------------------------
    def get_all_product_links(
        self,
        driver: Any,
        start_url: Optional[str] = None,
        max_pages: Optional[int] = None,
    ) -> List[str]:
        from bs4 import BeautifulSoup

        target_url = start_url or self.category_url
        print(f"\n[BƯỚC 1] ĐANG QUÉT LINK TỪ DANH MỤC MEGA: {target_url}")

        driver.get(target_url)
        time.sleep(3)

        product_links: List[str] = []
        seen_links: set[str] = set()
        page_count = 1

        while True:
            print(f" -> Đang quét dữ liệu ở Trang {page_count}...")
            soup = BeautifulSoup(driver.page_source, "html.parser")

            product_items = soup.find_all("div", class_="product-item") or soup.find_all(
                "div", class_="p-item"
            )
            links_in_page = 0

            for item in product_items:
                a_tag = item.find("a", href=True)
                if a_tag:
                    href = a_tag["href"]
                    full_url = (
                        href
                        if href.startswith("http")
                        else "https://mega.com.vn" + href
                    )
                    if "mega.com.vn" in full_url and full_url not in seen_links:
                        seen_links.add(full_url)
                        product_links.append(full_url)
                        links_in_page += 1

            print(f"    + Thu thập được {links_in_page} link VGA ở trang {page_count}.")

            if max_pages is not None and page_count >= max_pages:
                print(f" -> Đã đạt giới hạn max_pages={max_pages}.")
                break

            next_btn = soup.find("a", class_="page-link", string="»")
            if not next_btn:
                next_btn = soup.find("a", rel="next")

            if next_btn and "href" in next_btn.attrs:
                next_url = next_btn["href"]
                full_next_url = (
                    next_url
                    if next_url.startswith("http")
                    else "https://mega.com.vn" + next_url
                )
                print("    -> Đang chuyển sang trang tiếp theo...")
                driver.get(full_next_url)
                page_count += 1
                time.sleep(3)
            else:
                print(
                    " -> [Hoàn tất] Không tìm thấy nút 'Next' (»). Đã duyệt đến trang cuối cùng!"
                )
                break

        print(
            f"==> KẾT QUẢ BƯỚC 1: Lọc được tổng cộng {len(product_links)} link sản phẩm duy nhất.\n"
        )
        return product_links

    # -------------------------------------------------------------------------
    # Step 2 (Selenium): Cào chi tiết sản phẩm & mở bảng thông số (`table-spec`)
    # -------------------------------------------------------------------------
    def scrape_product_detail(self, driver: Any, url: str) -> Dict[str, Any]:
        from selenium.common.exceptions import TimeoutException
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait

        driver.get(url)
        time.sleep(2.5)

        try:
            driver.execute_script("window.scrollBy(0, 700);")
            time.sleep(1.5)

            xpath_btn = "//button[contains(@class, 'btn-view-all') and contains(text(), 'Xem toàn bộ')]"
            show_specs_btn = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, xpath_btn))
            )

            print("    -> Đã tìm thấy nút 'Xem toàn bộ'. Đang mở bảng thông số...")
            driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", show_specs_btn
            )
            time.sleep(0.5)
            driver.execute_script("arguments[0].click();", show_specs_btn)
            time.sleep(1.5)
        except TimeoutException:
            print(
                "    -> [Thông báo] Bảng thông số đã được mở sẵn hoặc sản phẩm không có nút."
            )
        except Exception as exc:
            print(f"    -> [Cảnh báo] Không thể mở nút Xem toàn bộ: {exc}")

        return self.parse_detail_html(driver.page_source, url)

    def parse_detail_html(self, html_text: str, url: str) -> Dict[str, Any]:
        """
        Parse MEGA product detail HTML (`h1`, `.price/.p-price/.box-price`, and `table.table-spec`).
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

        price_node = (
            root.find_first(class_name="price")
            or root.find_first(class_name="p-price")
            or root.find_first(class_name="box-price")
        )
        if price_node:
            product_data["Giá hiện tại"] = price_node.get_text()

        old_price_node = (
            root.find_first(class_name="p-unprice")
            or root.find_first(class_name="old-price")
            or root.find_first(tag="del")
        )
        if old_price_node:
            product_data["Giá gốc"] = old_price_node.get_text()

        full_text = root.get_text()
        if "Liên hệ" in full_text or "Hết hàng" in full_text:
            product_data["Tình trạng"] = "Có thể hết hàng (Liên hệ)"

        # Tìm bảng `table` có class chứa `'table-spec'`
        for table in root.find_all(tag="table"):
            if "table-spec" in table.attr("class"):
                for row in table.find_all(tag="tr"):
                    cols = row.find_all(tag="td")
                    if len(cols) == 2:
                        key = cols[0].get_text()
                        val = cols[1].get_text(separator=" ")
                        if key and key != ":" and val:
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
            return [raw_payload]
        if not isinstance(raw_payload, str) or not raw_payload.strip():
            return []

        # Check if detail page HTML vs category page HTML
        if "table-spec" in raw_payload and "<h1" in raw_payload:
            return [
                self.parse_detail_html(
                    raw_payload, "https://mega.com.vn/vga-sample.html"
                )
            ]

        root = parse_html_tree(raw_payload)
        cards = (
            root.find_all(class_name="product-item")
            or root.find_all(class_name="p-item")
            or root.find_all(class_name="item-product")
        )

        items: List[Dict[str, Any]] = []
        for card in cards:
            name_node = (
                card.find_first(class_name="p-name")
                or card.find_first(class_name="product-name")
                or card.find_first(tag="h3")
            )
            link_node = (
                name_node
                if (name_node and name_node.tag == "a")
                else (
                    name_node.find_first(tag="a")
                    if name_node
                    else card.find_first(tag="a")
                )
            )
            raw_name = (
                name_node.get_text()
                if name_node
                else (link_node.get_text() if link_node else "")
            )
            href = link_node.attr("href") if link_node else ""
            if not raw_name and not href:
                continue

            img_node = card.find_first(tag="img")
            img_src = ""
            if img_node:
                img_src = (
                    img_node.attr("data-src")
                    or img_node.attr("data-original")
                    or img_node.attr("src")
                )

            code_node = card.find_first(class_name="p-code") or card.find_first(
                class_name="p-sku"
            )
            code_text = code_node.get_text() if code_node else ""
            sku = card.attr("data-id") or self._extract_sku(code_text, href)

            price_node = (
                card.find_first(class_name="p-price")
                or card.find_first(class_name="price")
                or card.find_first(class_name="box-price")
            )
            old_price_node = (
                card.find_first(class_name="p-unprice")
                or card.find_first(class_name="old-price")
                or card.find_first(tag="del")
            )
            stock_node = card.find_first(class_name="p-qty") or card.find_first(
                class_name="p-status"
            )
            warranty_node = card.find_first(class_name="p-warranty")
            spec_node = card.find_first(class_name="p-summary") or card.find_first(
                class_name="hover-content"
            )

            items.append(
                {
                    "sku": f"MEGA-{sku}" if not str(sku).startswith("MEGA-") else str(sku),
                    "raw_name": raw_name,
                    "url": href,
                    "image_url": img_src,
                    "raw_price": price_node.get_text() if price_node else None,
                    "raw_old_price": old_price_node.get_text() if old_price_node else None,
                    "raw_stock": stock_node.get_text() if stock_node else None,
                    "raw_warranty": warranty_node.get_text() if warranty_node else None,
                    "spec_text": spec_node.get_text(separator=" | ") if spec_node else "",
                }
            )
        return items

    def adapt_item(self, raw_item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize either a `scrape_product_detail` dictionary (with `table-spec` rows)
        or a category card dictionary into `NormalizedVGASchema`.
        """
        raw_name = str(
            raw_item.get("Tên sản phẩm") or raw_item.get("raw_name") or ""
        ).strip()
        url_path = str(
            raw_item.get("Link sản phẩm") or raw_item.get("url") or ""
        ).strip()
        spec_text = str(raw_item.get("spec_text") or "").strip()

        raw_specs = self.extract_legacy_specs_from_dict(raw_item)
        if spec_text and "Thông số tóm tắt" not in raw_specs:
            raw_specs["Thông số tóm tắt"] = spec_text
        if raw_item.get("raw_warranty") and "Bảo hành" not in raw_specs:
            raw_specs["Bảo hành"] = str(raw_item["raw_warranty"])

        spec_parsed = self.normalizer.parse_spec_table_dict(
            raw_specs=raw_specs, raw_title=f"{raw_name} {spec_text}", url=url_path
        )

        # Fallback MPN extraction from MEGA SEO URL slug (e.g. `...-dual-rtx4060-o8g-v2.html`)
        if not spec_parsed.get("mpn"):
            spec_parsed["mpn"] = self._extract_mpn_from_mega_slug(url_path)

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

        sku = str(
            raw_item.get("sku")
            or raw_specs.get("Mã sản phẩm")
            or self._extract_sku("", url_path)
        )
        if not sku.startswith("MEGA-"):
            sku = f"MEGA-{sku}"

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

    @staticmethod
    def _extract_sku(code_text: str, href: str) -> str:
        if code_text:
            m = re.search(
                r"(?:mã\s*(?:sp)?\s*[:\-]?\s*)([A-Z0-9\-_]{3,20})", code_text, re.I
            )
            if m:
                return m.group(1).upper()
        slug = re.sub(r"\.html.*$", "", href.strip("/").split("/")[-1])
        slug = re.sub(r"^vga-", "", slug, flags=re.I)
        return slug[:24].upper() if slug else "UNKNOWN"

    @staticmethod
    def _extract_mpn_from_mega_slug(url_path: str) -> Optional[str]:
        slug = re.sub(r"\.html.*$", "", url_path.strip("/").split("/")[-1])
        m_asus = re.search(
            r"((?:dual|tuf|rog-strix|proart)-rtx\d{4}[a-z0-9\-]*)$", slug, re.I
        )
        if m_asus:
            return m_asus.group(1).upper()
        m_giga = re.search(r"(gv-[a-z0-9\-]+)$", slug, re.I)
        if m_giga:
            return m_giga.group(1).upper()
        return None
