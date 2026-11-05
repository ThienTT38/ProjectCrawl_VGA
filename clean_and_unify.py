"""
VGA Data Cleaning & Unified Currency (VND) Pipeline
----------------------------------------------------
Thực hiện các nhiệm vụ làm sạch chuyên sâu và đồng nhất giá toàn bộ hệ thống về VND:
1. Sửa lỗi trùng lặp SKU ở các nguồn bằng cách sinh SKU duy nhất (Unambiguous SKU) dựa trên slug URL.
2. Nhận diện thêm các thương hiệu AIB quốc tế (EVGA, Gainward, Yeston, Sparkle, Maxsun, Arktek...) thay vì để 'OTHER'.
3. Đồng nhất toàn bộ giá về VND (`price_vnd_unified` & `original_price_vnd_unified`):
   - Nguồn VN (Phong Vũ, Phi Long, Mega): giữ nguyên giá VND thực tế.
   - Nguồn Quốc tế (BuildCores): quy đổi `price_usd` sang VND theo tỷ giá thị trường chuẩn (25.450 VND/USD), làm tròn đến hàng nghìn.
   - Gắn cờ nguồn gốc giá (`price_currency_original`: 'VND' | 'USD' | 'UNLISTED').
4. Gắn cờ cảnh báo bất thường giá (`price_status`):
   - 'NORMAL': Giá hợp lý.
   - 'UNLISTED': Hết hàng / Liên hệ / Không có giá niêm yết.
   - 'ANOMALY_HIGH': Giá bất thường cao so với phân khúc (>150M đối với các card không phải RTX 5090 / 4090 / Quadro).
   - 'ANOMALY_LOW': Giá bất thường thấp (< 1.000.000đ).
   - 'MEGA_PLACEHOLDER': Phát hiện giá mặc định lặp lại của Mega (14.290.000đ, 13.900.000đ) khi sản phẩm thuộc phân khúc khác.
5. Xuất ra file chuẩn hóa làm sạch cuối cùng: `output/vga_cleaned_unified.csv`, `output/vga_cleaned_unified.json` và cơ sở dữ liệu SQLite.
"""

from __future__ import annotations

import csv
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import pandas as pd

USD_TO_VND_RATE = 25450  # Tỷ giá chuẩn USD sang VND

EXTENDED_BRAND_PATTERNS = [
    (re.compile(r"\bevga\b", re.I), "EVGA"),
    (re.compile(r"\bgainward\b", re.I), "Gainward"),
    (re.compile(r"\byeston\b", re.I), "Yeston"),
    (re.compile(r"\bsparkle\b", re.I), "Sparkle"),
    (re.compile(r"\bmaxsun\b", re.I), "MAXSUN"),
    (re.compile(r"\barktek\b", re.I), "ARKTEK"),
    (re.compile(r"\bvisiontek\b", re.I), "VisionTek"),
    (re.compile(r"\bonix\b", re.I), "ONIX"),
    (re.compile(r"\bcolorfire\b", re.I), "Colorfire"),
    (re.compile(r"\bmanli\b", re.I), "Manli"),
    (re.compile(r"\bbiostar\b", re.I), "Biostar"),
]


def fix_brand(row: pd.Series) -> str:
    current_brand = str(row.get("brand", "")).strip()
    if current_brand != "OTHER" and current_brand:
        return current_brand
    raw_name = str(row.get("raw_name", ""))
    for pattern, brand_name in EXTENDED_BRAND_PATTERNS:
        if pattern.search(raw_name):
            return brand_name
    return current_brand


def fix_sku(row: pd.Series) -> str:
    source = str(row.get("source", "")).strip()
    sku = str(row.get("sku", "")).strip()
    url = str(row.get("url", "")).strip()

    if source in ("mega", "philong"):
        slug = url.split("/")[-1].replace(".html", "").strip().upper()
        if source == "mega":
            return f"MEGA-{slug}"
        elif source == "philong":
            return f"PL-{slug}"
    return sku


def detect_price_status(row: pd.Series, price_vnd_unified: Optional[float]) -> str:
    if pd.isna(price_vnd_unified) or price_vnd_unified is None or price_vnd_unified <= 0:
        return "UNLISTED"

    source = str(row.get("source", "")).strip()
    gpu_model = str(row.get("gpu_model", "")).upper()
    raw_name = str(row.get("raw_name", "")).upper()

    # Kiểm tra placeholder của Mega:
    if source == "mega":
        p = float(price_vnd_unified)
        if p in (14290000.0, 13900000.0):
            if any(k in gpu_model for k in ["GT 710", "GT 730", "GT 1030", "RX 550", "RTX 5090", "RTX 5080", "RTX 5070 TI"]):
                return "MEGA_PLACEHOLDER"

    # Kiểm tra giá quá cao:
    if price_vnd_unified > 120_000_000:
        is_flagship = any(k in gpu_model for k in ["5090", "4090", "6000", "A6000", "A5500", "A5000", "A4500", "QUADRO", "TITAN"])
        if not is_flagship:
            return "ANOMALY_HIGH"

    # Kiểm tra giá quá thấp:
    if price_vnd_unified < 1_000_000:
        return "ANOMALY_LOW"

    return "NORMAL"


def clean_and_unify_data(
    input_csv: str = r"D:\vga-crawler\output\vga_normalized.csv",
    output_dir: str = r"D:\vga-crawler\output",
    usd_rate: int = USD_TO_VND_RATE,
) -> Dict[str, Any]:
    print(f"[*] Đang tải dữ liệu gốc từ: {input_csv}")
    df = pd.read_csv(input_csv)
    total_raw = len(df)
    print(f"[*] Tổng số bản ghi ban đầu: {total_raw}")

    # 1. Sửa SKU duy nhất
    df["sku_cleaned"] = df.apply(fix_sku, axis=1)

    # 2. Làm sạch nhãn thương hiệu (Brand)
    df["brand_cleaned"] = df.apply(fix_brand, axis=1)

    # 3. Đồng nhất Giá về VND
    price_unified_list: List[Optional[int]] = []
    original_price_unified_list: List[Optional[int]] = []
    price_currency_orig_list: List[str] = []

    for _, row in df.iterrows():
        source = str(row.get("source", "")).strip()
        p_vnd = row.get("price_vnd")
        orig_p_vnd = row.get("original_price_vnd")
        p_usd = row.get("price_usd")

        final_vnd: Optional[int] = None
        final_orig_vnd: Optional[int] = None
        curr_orig = "UNLISTED"

        if pd.notna(p_vnd) and float(p_vnd) > 0:
            final_vnd = int(round(float(p_vnd)))
            curr_orig = "VND"
            if pd.notna(orig_p_vnd) and float(orig_p_vnd) > 0:
                final_orig_vnd = int(round(float(orig_p_vnd)))
            else:
                final_orig_vnd = final_vnd
        elif pd.notna(p_usd) and float(p_usd) > 0:
            final_vnd = int(round(float(p_usd) * usd_rate, -3))  # làm tròn đến nghìn
            final_orig_vnd = final_vnd
            curr_orig = "USD"
        else:
            final_vnd = None
            final_orig_vnd = None
            curr_orig = "UNLISTED"

        price_unified_list.append(final_vnd)
        original_price_unified_list.append(final_orig_vnd)
        price_currency_orig_list.append(curr_orig)

    df["price_vnd_unified"] = price_unified_list
    df["original_price_vnd_unified"] = original_price_unified_list
    df["price_currency_original"] = price_currency_orig_list

    # Tính lại discount_percent nếu có giá gốc
    recomputed_discounts: List[Optional[float]] = []
    for cur, orig in zip(price_unified_list, original_price_unified_list):
        if cur is not None and orig is not None and orig > cur:
            disc = ((orig - cur) / orig) * 100.0
            recomputed_discounts.append(round(disc, 2))
        elif cur is not None:
            recomputed_discounts.append(0.0)
        else:
            recomputed_discounts.append(None)
    df["discount_percent_unified"] = recomputed_discounts

    # 4. Gắn cờ Price Status & Anomaly Detection
    price_status_list = [
        detect_price_status(row, p_u)
        for (_, row), p_u in zip(df.iterrows(), df["price_vnd_unified"])
    ]
    df["price_status"] = price_status_list

    # 5. Cập nhật lại stock_status đối với các sản phẩm thiếu giá
    updated_stock = []
    for st, p_u in zip(df["stock_status"], df["price_vnd_unified"]):
        if p_u is None or p_u <= 0:
            if st != "OUT_OF_STOCK":
                updated_stock.append("UNLISTED")
            else:
                updated_stock.append(st)
        else:
            updated_stock.append(st if st != "UNKNOWN" else "IN_STOCK")
    df["stock_status_cleaned"] = updated_stock

    # Sắp xếp lại thứ tự cột cho rõ ràng, chuẩn hóa
    cols_order = [
        "source",
        "sku_cleaned",
        "mpn",
        "normalized_name",
        "raw_name",
        "chip_manufacturer",
        "gpu_model",
        "brand_cleaned",
        "series",
        "is_oc",
        "vram_gb",
        "vram_type",
        "fan_count",
        # Cột giá đồng nhất
        "price_vnd_unified",
        "original_price_vnd_unified",
        "discount_percent_unified",
        "price_currency_original",
        "price_usd",
        "price_status",
        "stock_status_cleaned",
        "warranty_months",
        # Thông số kỹ thuật
        "boost_clock_mhz",
        "tdp_watts",
        "recommended_psu_watts",
        "length_mm",
        "slot_width",
        "power_connectors",
        "canonical_key",
        "spec_enriched_from",
        "url",
        "crawled_at",
    ]

    df_cleaned = df[cols_order].rename(
        columns={
            "sku_cleaned": "sku",
            "brand_cleaned": "brand",
            "stock_status_cleaned": "stock_status",
            "discount_percent_unified": "discount_percent",
        }
    )

    # 6. Xuất ra file
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = out_dir / "vga_cleaned_unified.csv"
    json_path = out_dir / "vga_cleaned_unified.json"
    db_path = out_dir / "vga_catalog_cleaned.db"

    df_cleaned.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"[+] Đã xuất file CSV làm sạch & đồng nhất VND: {csv_path}")

    # Xuất JSON
    df_cleaned.to_json(json_path, orient="records", force_ascii=False, indent=2)
    print(f"[+] Đã xuất file JSON làm sạch & đồng nhất VND: {json_path}")

    # Xuất SQLite
    with sqlite3.connect(db_path) as conn:
        df_cleaned.to_sql("vga_cleaned", conn, if_exists="replace", index=False)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_vga_clean_canonical ON vga_cleaned(canonical_key)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_vga_clean_price ON vga_cleaned(price_vnd_unified)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_vga_clean_gpu ON vga_cleaned(gpu_model)")
        conn.commit()
    print(f"[+] Đã lưu vào cơ sở dữ liệu SQLite: {db_path}")

    # 7. Thống kê kết quả làm sạch
    stats = {
        "total_records": len(df_cleaned),
        "unique_skus": df_cleaned["sku"].nunique(),
        "unique_urls": df_cleaned["url"].nunique(),
        "sources": df_cleaned["source"].value_counts().to_dict(),
        "price_currency_orig": df_cleaned["price_currency_original"].value_counts().to_dict(),
        "price_status": df_cleaned["price_status"].value_counts().to_dict(),
        "vnd_price_count": df_cleaned["price_vnd_unified"].notnull().sum(),
        "unlisted_price_count": df_cleaned["price_vnd_unified"].isnull().sum(),
        "min_vnd": df_cleaned["price_vnd_unified"].min(),
        "max_vnd": df_cleaned["price_vnd_unified"].max(),
        "median_vnd": df_cleaned["price_vnd_unified"].median(),
        "brands_other_count": (df_cleaned["brand"] == "OTHER").sum(),
    }
    return stats


if __name__ == "__main__":
    stats = clean_and_unify_data()
    print("\n" + "=" * 60)
    print("BÁO CÁO KẾT QUẢ LÀM SẠCH & ĐỒNG NHẤT DỮ LIỆU VGA TOÀN BỘ HỆ THỐNG")
    print("=" * 60)
    for k, v in stats.items():
        print(f"  - {k:<25}: {v}")
