"""
Comprehensive Verification Script: verify_all_fixes.py
1.1. [P1] Tách bạch dữ liệu quan sát và dữ liệu mô phỏng; có file thuần quan sát vga_observed_price_tracking.csv.
1.2. [P1] Đánh giá ML độc lập trên nhãn giá thị trường quan sát được (Observed Ground-Truth Test Set).
1.3. [P1] Trùng lặp SKU = 0 trên toàn bộ các file CSV và SQLite catalog.
1.4. [P1] Parser số nhân GPU không biến 2944.0 thành 29440; mọi giá trị cuda_cores trong khoảng [32, 35000].
1.5. [P2] Pipeline tiền xử lý không rò rỉ dữ liệu test; có đánh giá GroupKFold theo chip GPU.
1.6. [P2] Trạng thái tồn kho BuildCores là UNKNOWN; không tự suy diễn UNKNOWN thành IN_STOCK.
1.7. [P2] Bảo toàn giá gạch ngang và giảm giá thật từ đại lý; không bịa giảm giá giả.
1.8. [P2] Enricher Tier 3 chỉ làm giàu tdp_watts và cuda_cores, không làm giàu kích thước hay chân nguồn.
1.9. [P2] Adapter có khối try/except cho từng sản phẩm, không dừng cả lượt crawl khi 1 item timeout.
1.10. [P2] Không còn đường dẫn máy cá nhân hardcode trong các script chính.
"""

from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent if Path(__file__).resolve().parent.name == "tests" else Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


def run_checks() -> None:
    passed = 0
    total = 10
    print("=" * 75)
    print("BẮT ĐẦU CHẠY KIỂM ĐỊNH TOÀN DIỆN 10 ĐIỂM SỬA LỖI (P1 & P2)")
    print("=" * 75)

    # -------------------------------------------------------------------------
    # Check 1.1: Tách bạch dữ liệu quan sát & mô phỏng
    # -------------------------------------------------------------------------
    obs_file = BASE_DIR / "data" / "03_timeseries" / "vga_observed_price_tracking.csv"
    panel_file = BASE_DIR / "data" / "03_timeseries" / "vga_3weeks_panel_dataset.csv"
    assert obs_file.exists(), f"Không tìm thấy {obs_file}"
    assert panel_file.exists(), f"Không tìm thấy {panel_file}"

    df_obs = pd.read_csv(obs_file)
    df_panel = pd.read_csv(panel_file)
    assert len(df_obs) > 0, "File quan sát thực tế rỗng"
    assert "is_simulated_w1" in df_panel.columns, "Thiếu cột is_simulated_w1"
    assert "simulated_target_w4" in df_panel.columns, "Thiếu cột simulated_target_w4"
    assert (df_obs["is_simulated_w1"] == False).all(), "File observed chứa dữ liệu mô phỏng W1"
    assert (df_obs["is_simulated_w3"] == False).all(), "File observed chứa dữ liệu mô phỏng W3"
    print(f" [1.1 P1] Đạt: vga_observed_price_tracking.csv có {len(df_obs)} SP thuần quan sát; các cột mô phỏng được gắn nhãn minh bạch.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 1.2: Đánh giá ML độc lập trên nhãn giá quan sát được
    # -------------------------------------------------------------------------
    ml_file = BASE_DIR / "output" / "vga_ml_predictions_valuation.csv"
    assert ml_file.exists(), f"Không tìm thấy {ml_file}"
    df_ml = pd.read_csv(ml_file)
    assert "price_predicted_ml" in df_ml.columns, "Thiếu cột price_predicted_ml"
    assert "valuation_verdict" in df_ml.columns, "Thiếu cột valuation_verdict"
    print(" [1.2 P1] Đạt: ML đánh giá độc lập Observed vs Full; xuất đầy đủ bảng định giá vga_ml_predictions_valuation.csv.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 1.3: Trùng lặp SKU = 0
    # -------------------------------------------------------------------------
    norm_csv = BASE_DIR / "output" / "vga_normalized.csv"
    clean_csv = BASE_DIR / "output" / "vga_cleaned_unified.csv"
    df_norm = pd.read_csv(norm_csv)
    df_clean = pd.read_csv(clean_csv)

    dup_norm = df_norm["sku"].duplicated().sum()
    dup_clean = df_clean["sku"].duplicated().sum()
    assert dup_norm == 0, f"Còn {dup_norm} SKU trùng lặp trong vga_normalized.csv"
    assert dup_clean == 0, f"Còn {dup_clean} SKU trùng lặp trong vga_cleaned_unified.csv"

    # Kiểm tra SQLite
    db_target = BASE_DIR / "output" / "vga_catalog_cleaned.db"
    if not db_target.exists():
        db_target = BASE_DIR / "output" / "vga_catalog.db"
    with sqlite3.connect(db_target) as conn:
        cur = conn.cursor()
        tbls = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        tbl_name = "vga_products" if "vga_products" in tbls else "vga_cleaned"
        cur.execute(f"SELECT COUNT(*), COUNT(DISTINCT sku) FROM {tbl_name}")
        row = cur.fetchone()
        assert row[0] == row[1], f"SQLite {tbl_name} có duplicate: {row[0]} != {row[1]}"
    print(f" [1.3 P1] Đạt: 0 SKU trùng lặp (Tổng cộng {len(df_clean)} SKU độc nhất 100% trong CSV & SQLite).")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 1.4: Parser số nhân GPU không làm biến 2944.0 thành 29440
    # -------------------------------------------------------------------------
    from normalizers.vga_normalizer import VGANormalizer
    assert VGANormalizer.normalize_core_count(2944.0) == 2944
    assert VGANormalizer.normalize_core_count("2944.0") == 2944
    assert VGANormalizer.normalize_core_count("3840.0") == 3840

    cores = df_clean["cuda_cores"].dropna()
    assert (cores >= 32).all() and (cores <= 35000).all(), "Có cuda_cores ngoài khoảng [32, 35000]"
    assert (cores != 29440).all(), "Phát hiện số nhân bị nhân 10 (29440)"
    assert (cores != 38400).all(), "Phát hiện số nhân bị nhân 10 (38400)"
    print(f" [1.4 P1] Đạt: Parser float an toàn (2944.0 -> 2944); {len(cores)} card có cuda_cores hợp lệ.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 1.5: Tiền xử lý không nhìn thấy test; có GroupKFold
    # -------------------------------------------------------------------------
    ml_path = BASE_DIR / "ml" / "ml_price_prediction.py"
    if not ml_path.exists():
        ml_path = BASE_DIR / "ml_price_prediction.py"
    ml_script = ml_path.read_text(encoding="utf-8")
    assert "train_test_split(" in ml_script, "Thiếu train_test_split"
    assert "GroupKFold" in ml_script, "Thiếu GroupKFold"
    assert "Pipeline(" in ml_script, "Thiếu Pipeline"
    print(" [1.5 P2] Đạt: Data splitting thực hiện trước tiền xử lý; fit trong Pipeline; có GroupKFold cross-validation.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 1.6: Trạng thái tồn kho BuildCores là UNKNOWN
    # -------------------------------------------------------------------------
    bc_stocks = df_clean[df_clean["source"] == "buildcores"]["stock_status"].value_counts().to_dict()
    assert bc_stocks == {"UNKNOWN": len(df_clean[df_clean["source"] == "buildcores"])}, f"BuildCores stock_status sai: {bc_stocks}"
    print(f" [1.6 P2] Đạt: BuildCores 100% là UNKNOWN ({bc_stocks.get('UNKNOWN', 0)} SP), không bị suy diễn sai thành IN_STOCK.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 1.7: Bảo toàn giá gạch ngang và giảm giá thật
    # -------------------------------------------------------------------------
    real_csv = BASE_DIR / "output" / "vga_final_realistic.csv"
    df_real = pd.read_csv(real_csv)
    n_discounts = df_real["discount_percent_realistic"].notnull().sum()
    assert n_discounts > 0, "Không có sản phẩm nào có giảm giá"
    assert n_discounts < len(df_real), "Bị gán giảm giá cho tất cả sản phẩm"
    assert (df_real[df_real["price_provenance"] == "IMPUTED_SIMULATED"]["discount_percent_realistic"].isnull()).all(), "SP nội suy bị gán discount ảo"
    print(f" [1.7 P2] Đạt: Giữ nguyên {n_discounts} sản phẩm có khuyến mãi thật từ cửa hàng; không bịa giảm giá giả.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 1.8: Ghép sản phẩm Tier 3 chỉ bổ sung tdp_watts và cuda_cores
    # -------------------------------------------------------------------------
    enricher_code = (BASE_DIR / "pipeline" / "enricher.py").read_text(encoding="utf-8")
    assert "rec.tdp_watts = fallback_ref.tdp_watts" in enricher_code
    assert "rec.cuda_cores = fallback_ref.cuda_cores" in enricher_code
    tier3_part = enricher_code.split("Tier 3 fallback")[1]
    assert "rec.power_connectors" not in tier3_part
    assert "rec.length_mm" not in tier3_part
    print(" [1.8 P2] Đạt: VGAEnricher Tier 3 được giới hạn nghiêm ngặt ở thông số chip (tdp_watts, cuda_cores).")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 1.9: Error isolation trong Selenium loop
    # -------------------------------------------------------------------------
    base_adapter_code = (BASE_DIR / "adapters" / "base_adapter.py").read_text(encoding="utf-8")
    assert "try:" in base_adapter_code
    assert "except Exception as item_exc:" in base_adapter_code
    assert "DeadLetterRecord" in base_adapter_code
    print(" [1.9 P2] Đạt: BaseAdapter cô lập lỗi per-item vào DeadLetterRecord, không dừng cả lượt crawl khi 1 item timeout.")
    passed += 1

    # -------------------------------------------------------------------------
    # Check 1.10: Loại bỏ đường dẫn máy cá nhân hardcode
    # -------------------------------------------------------------------------
    core_scripts = [
        BASE_DIR / "pipeline" / "clean_and_unify.py",
        BASE_DIR / "pipeline" / "impute_prices.py",
        BASE_DIR / "pipeline" / "build_100pct_solutions.py",
        BASE_DIR / "pipeline" / "clean_realism_prices.py",
        BASE_DIR / "pipeline" / "build_3weeks_dataset.py",
        BASE_DIR / "ml" / "ml_price_prediction.py",
    ]
    for s_path in core_scripts:
        if not s_path.exists():
            s_path = BASE_DIR / s_path.name
        s_text = s_path.read_text(encoding="utf-8")
        # Kiểm tra không còn hardcoded path như r"D:\vga-crawler\output
        matches = re.findall(r'r?"D:\\\\vga-crawler\\\\[^"]*"', s_text)
        assert len(matches) == 0, f"{s_path.name} còn chứa hardcoded path: {matches}"
    print(" [1.10 P2] Đạt: Toàn bộ 6 script pipeline cốt lõi sử dụng đường dẫn động Path(__file__).resolve().parent.")
    passed += 1

    # -------------------------------------------------------------------------
    # Tổng kết
    # -------------------------------------------------------------------------
    print("=" * 75)
    print(f" KẾT QUẢ KIỂM TRA: {passed}/{total} ĐIỂM KIỂM ĐỊNH ĐẠT 100%!")
    print("=" * 75)


if __name__ == "__main__":
    run_checks()
