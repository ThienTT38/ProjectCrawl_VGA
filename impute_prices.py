"""
Multi-tier Price Imputation Engine for VGA Dataset
--------------------------------------------------
Triển khai Giải pháp 1: Điền giá ước lượng đa tầng (Multi-tier Price Imputation)
Quy tắc:
1. KHÔNG ghi đè giá thực tế: Giữ nguyên `price_vnd_unified` gốc.
2. Tạo các cột mới:
   - `price_vnd_final`: Giá thực tế nếu có; nếu thiếu thì lấy giá ước tính từ mô hình 4 cấp.
   - `price_impute_method`:
       + 'ORIGINAL_ACTUAL': Có giá thực tế từ nguồn Việt Nam (Phong Vũ, Phi Long, Mega).
       + 'ORIGINAL_USD_CONV': Có giá thực tế từ BuildCores quy đổi USD -> VND.
       + 'IMPUTE_L1_CANONICAL': Nội suy chính xác 100% cùng Hãng + Model + VRAM + Series.
       + 'IMPUTE_L2_BRAND_GPU': Nội suy cùng Hãng + Model + VRAM.
       + 'IMPUTE_L3_GPU_VRAM': Nội suy cùng Chip GPU Model + VRAM (Trung vị toàn thị trường).
       + 'IMPUTE_L4_GPU_BASE': Nội suy theo Chip GPU Model cơ sở.
       + 'UNIMPUTED': Không có sản phẩm cùng hệ chip để tham chiếu.
   - `price_market_min`: Mức giá thấp nhất trên thị trường cho hệ GPU/VRAM này.
   - `price_market_max`: Mức giá cao nhất trên thị trường cho hệ GPU/VRAM này.
   - `price_market_median`: Mức giá trung vị thị trường cho hệ GPU/VRAM này.
3. Xuất file:
   - `output/vga_cleaned_imputed.csv`
   - `output/vga_cleaned_imputed.json`
   - Bảng `vga_imputed` trong SQLite `output/vga_catalog_cleaned.db`
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def run_price_imputation(
    input_csv: str = r"D:\vga-crawler\output\vga_cleaned_unified.csv",
    output_dir: str = r"D:\vga-crawler\output",
) -> Dict[str, Any]:
    print(f"[*] Đang đọc dữ liệu đã làm sạch từ: {input_csv}")
    df = pd.read_csv(input_csv)
    total_rows = len(df)
    print(f"[*] Tổng số sản phẩm trong cơ sở dữ liệu: {total_rows}")

    # Lọc tập sản phẩm có giá đáng tin cậy (loại trừ placeholder của Mega) để làm ground-truth
    valid_prices = df[
        df["price_vnd_unified"].notnull()
        & (df["price_status"] == "NORMAL")
        & (df["price_vnd_unified"] > 0)
    ].copy()

    print(f"[*] Số sản phẩm có giá thực tế chuẩn dùng làm mốc nội suy: {len(valid_prices)}")

    # 1. Chuẩn bị các bảng tra cứu theo từng cấp
    # Cấp 1: Canonical Key (Hãng + Model + VRAM + Series)
    l1_map = valid_prices.groupby("canonical_key")["price_vnd_unified"].median().to_dict()

    # Cấp 2: Brand + GPU Model + VRAM
    valid_prices["k_l2"] = (
        valid_prices["brand"] + "_" + valid_prices["gpu_model"] + "_" + valid_prices["vram_gb"].astype(str)
    )
    df["k_l2"] = df["brand"] + "_" + df["gpu_model"] + "_" + df["vram_gb"].astype(str)
    l2_map = valid_prices.groupby("k_l2")["price_vnd_unified"].median().to_dict()

    # Cấp 3: GPU Model + VRAM (Trung vị toàn thị trường)
    valid_prices["k_l3"] = valid_prices["gpu_model"] + "_" + valid_prices["vram_gb"].astype(str)
    df["k_l3"] = df["gpu_model"] + "_" + df["vram_gb"].astype(str)
    l3_median = valid_prices.groupby("k_l3")["price_vnd_unified"].median().to_dict()
    l3_min = valid_prices.groupby("k_l3")["price_vnd_unified"].min().to_dict()
    l3_max = valid_prices.groupby("k_l3")["price_vnd_unified"].max().to_dict()

    # Cấp 4: GPU Model cơ sở
    l4_median = valid_prices.groupby("gpu_model")["price_vnd_unified"].median().to_dict()

    # 2. Tiến hành nội suy
    final_prices: List[Optional[float]] = []
    impute_methods: List[str] = []
    market_mins: List[Optional[float]] = []
    market_maxs: List[Optional[float]] = []
    market_medians: List[Optional[float]] = []

    counts = {
        "ORIGINAL_ACTUAL": 0,
        "ORIGINAL_USD_CONV": 0,
        "IMPUTE_L1_CANONICAL": 0,
        "IMPUTE_L2_BRAND_GPU": 0,
        "IMPUTE_L3_GPU_VRAM": 0,
        "IMPUTE_L4_GPU_BASE": 0,
        "UNIMPUTED": 0,
    }

    for _, row in df.iterrows():
        p_act = row.get("price_vnd_unified")
        p_status = row.get("price_status")
        orig_curr = row.get("price_currency_original")
        k_canon = row.get("canonical_key")
        k2 = row.get("k_l2")
        k3 = row.get("k_l3")
        gpu_m = row.get("gpu_model")

        # Thị trường min/max/median cho dòng GPU+VRAM này
        m_min = l3_min.get(k3)
        m_max = l3_max.get(k3)
        m_med = l3_median.get(k3)

        market_mins.append(m_min)
        market_maxs.append(m_max)
        market_medians.append(m_med)

        # Kiểm tra nếu đã có giá thực tế chuẩn
        if pd.notna(p_act) and p_act > 0 and p_status == "NORMAL":
            final_prices.append(float(p_act))
            if orig_curr == "VND":
                impute_methods.append("ORIGINAL_ACTUAL")
                counts["ORIGINAL_ACTUAL"] += 1
            else:
                impute_methods.append("ORIGINAL_USD_CONV")
                counts["ORIGINAL_USD_CONV"] += 1
            continue

        # Bắt đầu mô hình nội suy 4 cấp cho các sản phẩm thiếu giá hoặc bị placeholder
        if k_canon in l1_map:
            final_prices.append(float(round(l1_map[k_canon], -3)))
            impute_methods.append("IMPUTE_L1_CANONICAL")
            counts["IMPUTE_L1_CANONICAL"] += 1
        elif k2 in l2_map:
            final_prices.append(float(round(l2_map[k2], -3)))
            impute_methods.append("IMPUTE_L2_BRAND_GPU")
            counts["IMPUTE_L2_BRAND_GPU"] += 1
        elif k3 in l3_median:
            final_prices.append(float(round(l3_median[k3], -3)))
            impute_methods.append("IMPUTE_L3_GPU_VRAM")
            counts["IMPUTE_L3_GPU_VRAM"] += 1
        elif gpu_m in l4_median:
            final_prices.append(float(round(l4_median[gpu_m], -3)))
            impute_methods.append("IMPUTE_L4_GPU_BASE")
            counts["IMPUTE_L4_GPU_BASE"] += 1
        else:
            final_prices.append(None)
            impute_methods.append("UNIMPUTED")
            counts["UNIMPUTED"] += 1

    df["price_vnd_final"] = final_prices
    df["price_impute_method"] = impute_methods
    df["price_market_min"] = market_mins
    df["price_market_max"] = market_maxs
    df["price_market_median"] = market_medians

    # Dọn dẹp các cột tạm
    df.drop(columns=["k_l2", "k_l3"], inplace=True)

    # 3. Xuất file kết quả
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = out_dir / "vga_cleaned_imputed.csv"
    json_path = out_dir / "vga_cleaned_imputed.json"
    db_path = out_dir / "vga_catalog_cleaned.db"

    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    df.to_json(json_path, orient="records", force_ascii=False, indent=2)

    with sqlite3.connect(db_path) as conn:
        df.to_sql("vga_imputed", conn, if_exists="replace", index=False)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_vga_imp_final ON vga_imputed(price_vnd_final)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_vga_imp_gpu ON vga_imputed(gpu_model)")
        conn.commit()

    total_priced = total_rows - counts["UNIMPUTED"]
    coverage_pct = round((total_priced / total_rows) * 100.0, 2)

    print("\n" + "=" * 65)
    print("KẾT QUẢ TRIỂN KHAI NỘI SUY GIÁ ĐA TẦNG (SOLUTION 1)")
    print("=" * 65)
    print(f"[*] Tổng số sản phẩm xử lý          : {total_rows}")
    print(f"[*] Có giá thực tế bán lẻ VN        : {counts['ORIGINAL_ACTUAL']}")
    print(f"[*] Có giá quy đổi USD từ BuildCores: {counts['ORIGINAL_USD_CONV']}")
    print("---")
    print(f"[+] Điền Cấp 1 (Khớp cùng Series)   : {counts['IMPUTE_L1_CANONICAL']}")
    print(f"[+] Điền Cấp 2 (Khớp cùng Hãng+VRAM): {counts['IMPUTE_L2_BRAND_GPU']}")
    print(f"[+] Điền Cấp 3 (Trung vị dòng GPU)  : {counts['IMPUTE_L3_GPU_VRAM']}")
    print(f"[+] Điền Cấp 4 (Khớp chip cơ sở)    : {counts['IMPUTE_L4_GPU_BASE']}")
    print(f"[!] Không thể nội suy (Hệ chip hiếm): {counts['UNIMPUTED']}")
    print("---")
    print(f"[🎉] TỔNG SẢN PHẨM CÓ GIÁ SAU NỘI SUY: {total_priced} / {total_rows} ({coverage_pct}%)")
    print(f"[+] File CSV: {csv_path}")
    print(f"[+] File JSON: {json_path}")
    print(f"[+] Bảng SQLite 'vga_imputed' trong: {db_path}")

    return {
        "total_rows": total_rows,
        "total_priced": total_priced,
        "coverage_pct": coverage_pct,
        "breakdown": counts,
        "csv_path": str(csv_path),
    }


if __name__ == "__main__":
    run_price_imputation()
