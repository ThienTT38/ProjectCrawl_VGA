"""
Upgraded Phi Long Technology Adapter (`https://philong.com.vn/card-do-hoa.html`).
Integrates the user's 2-step Selenium + BeautifulSoup scraper (`div.p-item`,
paging XPath `next`, popup button `'XEM ĐẦY ĐỦ THÔNG SỐ'`, `div#modal table`)
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


class PhilongAdapter(BaseVGAAdapter):
    """
    Adapter for `https://philong.com.vn/card-do-hoa.html`.
    """

    source = SourceSite.PHILONG
    base_url = "https://philong.com.vn"
    category_url = "https://philong.com.vn/card-do-hoa.html"
    save_prefix = "philong_final"
    request_delay_sec = 1.5

    # -------------------------------------------------------------------------
    # Step 1 (Selenium): Quét link sản phẩm từ danh mục Phi Long
    # -------------------------------------------------------------------------
    def get_all_product_links(
        self,
        driver: Any,
        start_url: Optional[str] = None,
        max_pages: Optional[int] = None,
    ) -> List[str]:
        from bs4 import BeautifulSoup
        from selenium.common.exceptions import NoSuchElementException
        from selenium.webdriver.common.by import By

        target_url = start_url or self.category_url
        print(f"\n[BƯỚC 1] ĐANG QUÉT LINK TỪ DANH MỤC PHI LONG: {target_url}")
        driver.get(target_url)
        time.sleep(3)

        product_links: List[str] = []
        seen_links: set[str] = set()
        page_count = 1

        while True:
            print(f" -> Đang quét link sản phẩm ở Trang {page_count}...")
            soup = BeautifulSoup(driver.page_source, "html.parser")
            links_in_page = 0

            product_items = soup.find_all("div", class_="p-item")
            for item in product_items:
                a_tag = item.find("a", href=True)
                if a_tag:
                    href = a_tag["href"]
                    full_url = (
                        href
                        if href.startswith("http")
                        else "https://philong.com.vn" + href
                    )
                    if "philong.com.vn" in full_url and full_url not in seen_links:
                        seen_links.add(full_url)
                        product_links.append(full_url)
                        links_in_page += 1

            print(
                f"    + Thu thập được {links_in_page} link sản phẩm CHUẨN ở trang {page_count}."
            )

            if max_pages is not None and page_count >= max_pages:
                print(f" -> Đã đạt giới hạn max_pages={max_pages}.")
                break

            try:
                xpath_next_btn = "//div[@class='paging']//a[contains(translate(text(), 'NEXT', 'next'), 'next')]"
                next_btn = driver.find_element(By.XPATH, xpath_next_btn)

                driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});", next_btn
                )
                time.sleep(1)
                driver.execute_script("arguments[0].click();", next_btn)

                page_count += 1
                time.sleep(3)
            except NoSuchElementException:
                print(" -> Không tìm thấy nút 'Next'. Đã duyệt đến trang cuối cùng!")
                break
            except Exception as exc:
                print(f" -> [Cảnh báo] Dừng chuyển trang do lỗi: {exc}")
                break

        print(
            f"==> KẾT QUẢ BƯỚC 1: Lọc được tổng cộng {len(product_links)} link sản phẩm duy nhất.\n"
        )
        return product_links

    # -------------------------------------------------------------------------
    # Step 2 (Selenium): Cào chi tiết sản phẩm & mở Popup `XEM ĐẦY ĐỦ THÔNG SỐ` (`div#modal`)
    # -------------------------------------------------------------------------
    def scrape_product_detail(self, driver: Any, url: str) -> Dict[str, Any]:
        from selenium.common.exceptions import TimeoutException
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait

        driver.get(url)
        time.sleep(3)

        try:
            driver.execute_script("window.scrollBy(0, 1000);")
            time.sleep(1.5)

            xpath_spec_btn = "//a[contains(@class, 'show-m') and contains(text(), 'XEM ĐẦY ĐỦ THÔNG SỐ')]"
            show_specs_btn = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, xpath_spec_btn))
            )

            print("    -> Đã tìm thấy nút Popup. Đang click...")
            driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", show_specs_btn
            )
            time.sleep(1)
            driver.execute_script("arguments[0].click();", show_specs_btn)
            time.sleep(2)
        except TimeoutException:
            print(
                "    -> [Thông báo] Sản phẩm này không có nút mở bảng thông số chi tiết."
            )
        except Exception as exc:
            print(f"    -> [Cảnh báo] Không thể mở popup thông số: {exc}")

        return self.parse_detail_html(driver.page_source, url)

    def parse_detail_html(self, html_text: str, url: str) -> Dict[str, Any]:
        """
        Parse Phi Long product detail HTML (`h1`, `span.p-price`, and `div#modal table`).
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

        # Giá hiện tại (`span` có class chứa `'p-price'`)
        price_container = None
        for sp in root.find_all(tag="span"):
            if "p-price" in sp.attr("class"):
                price_container = sp
                break
        if price_container:
            inner_span = price_container.find_first(tag="span")
            product_data["Giá hiện tại"] = (
                inner_span.get_text() if inner_span else price_container.get_text()
            )

        # Giá gốc
        old_price = (
            root.find_first(class_name="p-old-price")
            or root.find_first(class_name="p-unprice")
            or root.find_first(tag="del")
        )
        if old_price:
            product_data["Giá gốc"] = old_price.get_text()

        full_text = root.get_text()
        if "Liên hệ" in full_text or "Hết hàng" in full_text:
            product_data["Tình trạng"] = "Có thể hết hàng (Liên hệ)"

        # Bảng thông số trong `div#modal` -> `table`
        modal_container = root.find_first(tag="div", attr_filters={"id": "modal"})
        if modal_container:
            table = modal_container.find_first(tag="table")
            if table:
                for row in table.find_all(tag="tr"):
                    cols = row.find_all(tag="td")
                    if len(cols) >= 2:
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

        if 'id="modal"' in raw_payload or "id='modal'" in raw_payload:
            return [
                self.parse_detail_html(
                    raw_payload, "https://philong.com.vn/vga-sample.html"
                )
            ]

        root = parse_html_tree(raw_payload)
        cards = (
            root.find_all(class_name="p-item")
            or root.find_all(class_name="pro-item")
            or root.find_all(class_name="product-item")
        )

        items: List[Dict[str, Any]] = []
        for card in cards:
            name_node = (
                card.find_first(class_name="p-name")
                or card.find_first(class_name="pro-name")
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

            sku_node = card.find_first(class_name="p-sku") or card.find_first(
                class_name="pro-sku"
            )
            sku_text = sku_node.get_text() if sku_node else ""
            sku = card.attr("data-id") or self._extract_sku(sku_text, img_src, href)

            price_node = (
                card.find_first(class_name="p-price")
                or card.find_first(class_name="price-new")
            )
            old_price_node = (
                card.find_first(class_name="p-old-price")
                or card.find_first(class_name="price-old")
                or card.find_first(tag="del")
            )
            stock_node = card.find_first(class_name="p-status") or card.find_first(
                class_name="stock-status"
            )
            summary_node = card.find_first(class_name="p-summary") or card.find_first(
                class_name="pro-summary"
            )

            items.append(
                {
                    "sku": sku,
                    "raw_name": raw_name,
                    "url": href,
                    "image_url": img_src,
                    "raw_price": price_node.get_text() if price_node else None,
                    "raw_old_price": old_price_node.get_text() if old_price_node else None,
                    "raw_stock": stock_node.get_text() if stock_node else None,
                    "summary_text": (
                        summary_node.get_text(separator=" | ") if summary_node else ""
                    ),
                }
            )

        return items

    def adapt_item(self, raw_item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize either a `scrape_product_detail` dictionary (with `div#modal table` rows)
        or a category card dictionary into `NormalizedVGASchema`.
        """
        raw_name = str(
            raw_item.get("Tên sản phẩm") or raw_item.get("raw_name") or ""
        ).strip()
        url_path = str(
            raw_item.get("Link sản phẩm") or raw_item.get("url") or ""
        ).strip()
        summary = str(raw_item.get("summary_text") or "").strip()

        raw_specs = self.extract_legacy_specs_from_dict(raw_item)
        if summary:
            # Parse inline `- Key: Value` pairs from `.p-summary` if present
            for part in summary.split("|"):
                part_clean = part.strip().lstrip("-").strip()
                if ":" in part_clean:
                    k, v = part_clean.split(":", 1)
                    raw_specs.setdefault(k.strip(), v.strip())

        spec_parsed = self.normalizer.parse_spec_table_dict(
            raw_specs=raw_specs, raw_title=f"{raw_name} {summary}", url=url_path
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

        sku = str(
            raw_item.get("sku")
            or self._extract_sku(
                raw_specs.get("Mã sản phẩm", ""),
                str(raw_item.get("image_url") or ""),
                url_path,
            )
        )

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
    def _extract_sku(sku_text: str, img_src: str, href: str) -> str:
        if sku_text:
            m = re.search(
                r"(?:mã\s*(?:sp|hàng)?\s*[:\-]?\s*)([A-Z0-9\-_]{3,20})",
                sku_text,
                re.I,
            )
            if m:
                return f"PL-{m.group(1).upper()}"
        if img_src:
            m_img = re.search(r"/media/product/(?:\d{2,3}-)?(\d{4,7})-", img_src)
            if m_img:
                return f"PL-{m_img.group(1)}"
        slug = re.sub(r"\.html.*$", "", href.strip("/").split("/")[-1])
        return f"PL-{slug[:24].upper()}" if slug else "PL-UNKNOWN"
