"""
Script: refresh_normalized_baseline.py
Mục đích:
  Cập nhật lại baseline `output/vga_normalized.csv`, `output/vga_normalized.json` và SQLite `output/vga_catalog.db`:
  1. Loại bỏ triệt để việc cắt ngắn SKU (slug[:24]) ở Mega và Phi Long -> 0 trùng lặp SKU.
  2. Bổ sung trường `cuda_cores` đã chuẩn hóa chuẩn (float 2944.0 -> int 2944, không biến thành 29440).
  3. Làm giàu `cuda_cores` cho các card bán lẻ VN cùng dòng chip GPU.
  4. Đặt trạng thái tồn kho của BuildCores về `UNKNOWN` (đúng bản chất catalog thông số).
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent if Path(__file__).resolve().parent.name == "pipeline" else Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from normalizers.vga_normalizer import VGANormalizer
NORM_CSV = BASE_DIR / "output" / "vga_normalized.csv"
NORM_JSON = BASE_DIR / "output" / "vga_normalized.json"
CATALOG_DB = BASE_DIR / "output" / "vga_catalog.db"
RAW_BC_PATH = BASE_DIR / "data" / "01_raw" / "week_1_2026_10_07" / "vga_buildcores_data.csv"
W3_RAW_CSV = BASE_DIR / "data" / "01_raw" / "week_3_2026_10_30" / "vga_normalized.csv"


def update_sku(row: pd.Series) -> str:
    src = str(row["source"]).lower()
    url = str(row["url"])
    if src == "mega":
        slug = re.sub(r"\.html.*$", "", url.strip("/").split("/")[-1])
        slug = re.sub(r"^vga-", "", slug, flags=re.I).strip("-")
        return slug.upper() if slug else str(row["sku"])
    elif src == "philong":
        slug = re.sub(r"\.html.*$", "", url.strip("/").split("/")[-1])
        return f"PL-{slug.upper()}" if slug else str(row["sku"])
    return str(row["sku"])


def refresh_baseline() -> None:
    print(f"[*] Đang tải: {NORM_CSV}")
    df = pd.read_csv(NORM_CSV)
    print(f"    Ban đầu: {len(df)} dòng, {df['sku'].duplicated().sum()} SKU trùng lặp.")

    # 1. Cập nhật SKU đầy đủ
    df["sku"] = df.apply(update_sku, axis=1)
    print(f"    Sau khi cập nhật SKU: {df['sku'].duplicated().sum()} SKU trùng lặp (Mục tiêu: 0).")

    # 2. Chuẩn hóa cuda_cores từ raw BuildCores
    if RAW_BC_PATH.exists():
        df_bc = pd.read_csv(RAW_BC_PATH)
        url_to_cores = {}
        for _, r in df_bc.iterrows():
            u = str(r.get("Link sản phẩm", "")).strip()
            c = VGANormalizer.normalize_core_count(r.get("Core Count"))
            if u and c:
                url_to_cores[u] = c
        df["cuda_cores"] = df["url"].map(url_to_cores)
        print(f"    Đã map trực tiếp cuda_cores từ BuildCores: {df['cuda_cores'].notnull().sum()} card.")

        # Làm giàu cấp chip cho các card bán lẻ VN
        chip_cores = df.groupby("gpu_model")["cuda_cores"].median().dropna().to_dict()
        for idx, r in df.iterrows():
            if pd.isna(df.at[idx, "cuda_cores"]) and r["gpu_model"] in chip_cores:
                df.at[idx, "cuda_cores"] = int(chip_cores[r["gpu_model"]])
        print(f"    Sau làm giàu chéo cấp chip: {df['cuda_cores'].notnull().sum()} card có cuda_cores.")
    else:
        if "cuda_cores" not in df.columns:
            df["cuda_cores"] = None

    # 3. Đặt BuildCores stock_status về UNKNOWN
    df.loc[df["source"] == "buildcores", "stock_status"] = "UNKNOWN"

    # 4. Sắp xếp lại thứ tự cột chuẩn
    expected_cols = [
        "source", "sku", "mpn", "normalized_name", "raw_name",
        "chip_manufacturer", "gpu_model", "brand", "series", "is_oc",
        "vram_gb", "vram_type", "fan_count",
        "price_vnd", "original_price_vnd", "discount_percent", "price_usd",
        "stock_status", "warranty_months",
        "cuda_cores", "boost_clock_mhz", "tdp_watts", "recommended_psu_watts",
        "length_mm", "slot_width", "power_connectors",
        "canonical_key", "spec_enriched_from", "url", "image_url", "crawled_at"
    ]
    # Chỉ giữ các cột có trong expected_cols hoặc df
    final_cols = [c for c in expected_cols if c in df.columns] + [c for c in df.columns if c not in expected_cols]
    df = df[final_cols]

    # 5. Lưu lại các file
    df.to_csv(NORM_CSV, index=False, encoding="utf-8-sig")
    df.to_json(NORM_JSON, orient="records", force_ascii=False, indent=2)
    if W3_RAW_CSV.parent.exists():
        df.to_csv(W3_RAW_CSV, index=False, encoding="utf-8-sig")

    # 6. Cập nhật SQLite
    with sqlite3.connect(CATALOG_DB) as conn:
        df.to_sql("vga_products", conn, if_exists="replace", index=False)
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS uidx_source_sku ON vga_products(source, sku)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_gpu_model ON vga_products(gpu_model)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_canonical_key ON vga_products(canonical_key)")
        conn.commit()

    print(f"[+] Đã cập nhật thành công: {NORM_CSV}")
    print(f"[+] Đã cập nhật thành công: {NORM_JSON}")
    print(f"[+] Đã cập nhật thành công SQLite: {CATALOG_DB}")


if __name__ == "__main__":
    refresh_baseline()
