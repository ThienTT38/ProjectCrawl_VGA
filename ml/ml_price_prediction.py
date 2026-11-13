"""
VGA Machine Learning Price Prediction & Valuation Model
-------------------------------------------------------
Xây dựng mô hình Học máy (Machine Learning) dự đoán giá thị trường cho Card màn hình (VGA)
dựa trên các thông số kỹ thuật phần cứng và đặc tính thương mại:
  - Input Features:
      + gpu_model (One-Hot Encoded)
      + brand (One-Hot Encoded)
      + chip_manufacturer (NVIDIA / AMD / INTEL)
      + vram_gb (1..48 GB)
      + vram_type (GDDR6, GDDR6X, GDDR7, GDDR5...)
      + is_oc (0 hoặc 1)
      + fan_count (1, 2, 3, 4)
      + boost_clock_mhz (Xung nhịp MHz)
      + tdp_watts (Công suất tiêu thụ điện)
      + length_mm (Chiều dài card mm)
      + cuda_cores (Số nhân xử lý GPU nếu có)
  - Target:
      + price_vnd_realistic (hoặc price_vnd_final)
  - Quy trình đánh giá chuẩn (Zero Data Leakage):
      + Split Train/Test TRƯỚC bất kỳ bước tiền xử lý hay học thống kê nào.
      + Preprocessing (Imputer + Scaler + OneHot) chỉ fit trên Train set bên trong Pipeline.
      + GroupKFold Cross-Validation theo `gpu_model` để đo lường khả năng tổng quát hóa trên chip mới.
      + Báo cáo độc lập 2 bộ metric:
          1. Đánh giá trên toàn bộ Test set (Full Test Set)
          2. Đánh giá ĐỘC LẬP trên mẫu có giá thị trường thực tế quan sát được (Ground-Truth Observed Set)
  - Đầu ra:
      + Mô hình tốt nhất (`output/vga_price_predictor.joblib`)
      + Bộ định giá toàn thị trường (`output/vga_ml_predictions_valuation.csv`)
      + Tiện ích suy luận thời gian thực `predict_custom_vga(...)`
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error, r2_score
from sklearn.model_selection import GroupKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, RobustScaler

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent if Path(__file__).resolve().parent.name == "ml" else Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
DEFAULT_INPUT_CSV = BASE_DIR / "output" / "vga_final_realistic.csv"
FALLBACK_INPUT_CSV = BASE_DIR / "output" / "vga_100pct_solution2_used_market.csv"


def train_and_evaluate_models(
    input_csv: Optional[str | Path] = None,
    output_dir: Optional[str | Path] = None,
) -> Dict[str, Any]:
    if input_csv is None:
        target_path = DEFAULT_INPUT_CSV if DEFAULT_INPUT_CSV.exists() else FALLBACK_INPUT_CSV
    else:
        target_path = Path(input_csv)

    if output_dir is None:
        out_dir = BASE_DIR / "output"
    else:
        out_dir = Path(output_dir)

    print(f"[*] Đang tải dữ liệu huấn luyện từ: {target_path}")
    if not target_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file dữ liệu: {target_path}")

    df = pd.read_csv(target_path)
    total_samples = len(df)
    print(f"[*] Tổng số mẫu dữ liệu: {total_samples}")

    # Xác định cột mục tiêu Target
    if "price_vnd_realistic" in df.columns:
        target = "price_vnd_realistic"
    elif "price_vnd_final" in df.columns:
        target = "price_vnd_final"
    elif "price_vnd" in df.columns:
        target = "price_vnd"
    else:
        raise KeyError("Không tìm thấy cột giá (price_vnd_realistic, price_vnd_final, price_vnd) trong dữ liệu.")

    print(f"[*] Cột mục tiêu huấn luyện: '{target}'")

    # Xác định các đặc trưng đầu vào Features
    numeric_features = [
        "vram_gb",
        "is_oc",
        "fan_count",
        "boost_clock_mhz",
        "tdp_watts",
        "length_mm",
    ]
    if "cuda_cores" in df.columns:
        numeric_features.append("cuda_cores")

    categorical_features = [
        "chip_manufacturer",
        "brand",
        "vram_type",
        "gpu_model",
    ]

    # Đảm bảo định dạng dữ liệu
    for col in numeric_features:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    for col in categorical_features:
        df[col] = df[col].fillna("UNKNOWN").astype(str)

    # -------------------------------------------------------------------------
    # BƯỚC 1: TRAIN / TEST SPLIT TRƯỚC BẤT KỲ BƯỚC TIỀN XỬ LÝ NÀO (Zero Leakage)
    # -------------------------------------------------------------------------
    df_train, df_test = train_test_split(df, test_size=0.20, random_state=42)
    print(f"[*] Tập Train: {len(df_train)} mẫu | Tập Test: {len(df_test)} mẫu")

    feature_cols = numeric_features + categorical_features
    X_train = df_train[feature_cols].copy()
    y_train = df_train[target].values

    X_test = df_test[feature_cols].copy()
    y_test = df_test[target].values

    # Xác định mẫu thực tế quan sát được (Observed Ground-Truth) trong tập Test
    if "price_provenance" in df_test.columns:
        obs_mask = df_test["price_provenance"].isin(["ACTUAL_STORE_RETAIL", "OFFICIAL_USD_CONVERTED"]).values
    elif "price_impute_method" in df_test.columns:
        obs_mask = df_test["price_impute_method"].isin(["ORIGINAL_ACTUAL", "ORIGINAL_USD_CONVERTED", "RAW_CRAWLED_EXACT"]).values
    else:
        obs_mask = np.ones(len(df_test), dtype=bool)

    n_observed_test = int(np.sum(obs_mask))
    print(f"[*] Số mẫu quan sát giá thực tế trong tập Test (Ground-Truth): {n_observed_test}/{len(df_test)} mẫu ({n_observed_test/len(df_test)*100:.1f}%)")

    # -------------------------------------------------------------------------
    # BƯỚC 2: THIẾT KẾ PREPROCESSING PIPELINE (FIT CHỈ TRÊN TRAIN)
    # -------------------------------------------------------------------------
    numeric_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", RobustScaler()),
        ]
    )

    categorical_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="constant", fill_value="UNKNOWN")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]
    )

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", numeric_transformer, numeric_features),
            ("cat", categorical_transformer, categorical_features),
        ]
    )

    # -------------------------------------------------------------------------
    # BƯỚC 3: GROUP-K-FOLD VALIDATION (ĐÁNH GIÁ TRÊN GPU MỚI CHƯA GẶP)
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("ĐÁNH GIÁ KHẢ NĂNG TỔNG QUÁT HÓA NGOÀI TẬP GPU (5-FOLD GROUP-K-FOLD)")
    print("=" * 70)
    gkf = GroupKFold(n_splits=5)
    train_groups = df_train["gpu_model"].values

    models = {
        "Random Forest": RandomForestRegressor(n_estimators=150, max_depth=20, random_state=42, n_jobs=-1),
        "Gradient Boosting": GradientBoostingRegressor(n_estimators=150, max_depth=6, learning_rate=0.1, random_state=42),
        "Ridge Regression": Ridge(alpha=1.0),
    }

    for name, model in models.items():
        pipe_cv = Pipeline(steps=[("preprocessor", preprocessor), ("regressor", model)])
        cv_scores = cross_val_score(pipe_cv, X_train, y_train, cv=gkf, groups=train_groups, scoring="r2", n_jobs=-1)
        print(f"  * {name:<18} GroupKFold R² trung bình: {cv_scores.mean():.4f} (± {cv_scores.std():.4f})")

    # -------------------------------------------------------------------------
    # BƯỚC 4: HUẤN LUYỆN & ĐÁNH GIÁ ĐỘC LẬP TRÊN TẬP TEST
    # -------------------------------------------------------------------------
    results = {}
    best_model_name = None
    best_r2_observed = -float("inf")
    best_pipeline = None

    print("\n" + "=" * 70)
    print("KẾT QUẢ ĐÁNH GIÁ ĐỘC LẬP TRÊN TẬP TEST (TÁCH BIỆT OBSERVED VS FULL)")
    print("=" * 70)

    for name, model in models.items():
        pipeline = Pipeline(steps=[("preprocessor", preprocessor), ("regressor", model)])
        pipeline.fit(X_train, y_train)
        y_pred = pipeline.predict(X_test)

        # 1. Đánh giá trên toàn bộ tập Test (Full Test Set)
        r2_full = r2_score(y_test, y_pred)
        mae_full = mean_absolute_error(y_test, y_pred)
        mape_full = mean_absolute_percentage_error(y_test, y_pred) * 100.0

        # 2. Đánh giá ĐỘC LẬP trên mẫu quan sát giá thực tế (Ground-Truth Observed Only)
        if n_observed_test > 0:
            y_test_obs = y_test[obs_mask]
            y_pred_obs = y_pred[obs_mask]
            r2_obs = r2_score(y_test_obs, y_pred_obs)
            mae_obs = mean_absolute_error(y_test_obs, y_pred_obs)
            mape_obs = mean_absolute_percentage_error(y_test_obs, y_pred_obs) * 100.0
        else:
            r2_obs, mae_obs, mape_obs = r2_full, mae_full, mape_full

        results[name] = {
            "Full_Test_R2": round(float(r2_full), 4),
            "Full_Test_MAE_VND": int(round(mae_full)),
            "Full_Test_MAPE_Percent": round(float(mape_full), 2),
            "Observed_Test_R2": round(float(r2_obs), 4),
            "Observed_Test_MAE_VND": int(round(mae_obs)),
            "Observed_Test_MAPE_Percent": round(float(mape_obs), 2),
        }

        print(f"📌 Mô hình: {name:<20}")
        print(f"   [A] Trên Toàn bộ Test Set ({len(df_test)} mẫu):")
        print(f"       - R² Score: {r2_full:.4f} ({r2_full*100:.2f}%) | MAE: {mae_full:,.0f} đ | MAPE: {mape_full:.2f}%")
        print(f"   [B] Trên Mẫu QUAN SÁT THỰC TẾ ({n_observed_test} mẫu Ground Truth):")
        print(f"       - R² Score: {r2_obs:.4f} ({r2_obs*100:.2f}%) | MAE: {mae_obs:,.0f} đ | MAPE: {mape_obs:.2f}%")
        print("-" * 70)

        # Chọn model dựa trên chất lượng trên nhãn giá thực tế quan sát được
        if r2_obs > best_r2_observed:
            best_r2_observed = r2_obs
            best_model_name = name
            best_pipeline = pipeline

    print(f"🏆 MÔ HÌNH XUẤT SẮC NHẤT TRÊN GIÁ THỰC TẾ: {best_model_name} (R² = {best_r2_observed*100:.2f}%)")

    # -------------------------------------------------------------------------
    # BƯỚC 5: LƯU TRỮ MÔ HÌNH & XUẤT ĐỊNH GIÁ (VALUATION VERDICT)
    # -------------------------------------------------------------------------
    out_dir.mkdir(parents=True, exist_ok=True)
    model_path = out_dir / "vga_price_predictor.joblib"
    joblib.dump(best_pipeline, model_path)
    print(f"[+] Đã lưu mô hình huấn luyện vào: {model_path}")

    # Dự đoán định giá cho toàn bộ tập dữ liệu
    all_features = df[feature_cols].copy()
    df["price_predicted_ml"] = np.round(best_pipeline.predict(all_features), -3)

    # Tính độ lệch định giá: (Giá thực tế - Giá dự đoán)
    # > 0: Sản phẩm bị đội giá (Overpriced); < 0: Sản phẩm giá hời/rẻ hơn thị trường (Good Deal)
    df["price_valuation_diff"] = df[target] - df["price_predicted_ml"]
    df["price_valuation_diff_pct"] = np.round((df["price_valuation_diff"] / df["price_predicted_ml"]) * 100.0, 2)

    valuation_status = []
    for diff_pct in df["price_valuation_diff_pct"]:
        if diff_pct > 15.0:
            valuation_status.append("OVERPRICED")
        elif diff_pct < -15.0:
            valuation_status.append("GOOD_DEAL")
        else:
            valuation_status.append("FAIR_PRICE")
    df["valuation_verdict"] = valuation_status

    out_csv = out_dir / "vga_ml_predictions_valuation.csv"
    out_json = out_dir / "vga_ml_predictions_valuation.json"
    df.to_csv(out_csv, index=False, encoding="utf-8-sig")
    df.to_json(out_json, orient="records", force_ascii=False, indent=2)

    db_path = out_dir / "vga_catalog_cleaned.db"
    with sqlite3.connect(db_path) as conn:
        df.to_sql("vga_ml_valuations", conn, if_exists="replace", index=False)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_vga_ml_verdict ON vga_ml_valuations(valuation_verdict)")
        conn.commit()

    print(f"[+] Đã xuất file đánh giá định giá: {out_csv}")
    print(f"[+] Đã cập nhật bảng SQLite 'vga_ml_valuations' trong: {db_path}")

    return {
        "best_model": best_model_name,
        "metrics": results,
        "model_file": str(model_path),
        "predictions_file": str(out_csv),
    }


def predict_custom_vga(
    gpu_model: str,
    brand: str,
    vram_gb: int,
    vram_type: str = "GDDR6",
    chip_manufacturer: str = "NVIDIA",
    is_oc: bool = False,
    fan_count: int = 2,
    boost_clock_mhz: Optional[int] = None,
    tdp_watts: Optional[int] = None,
    length_mm: Optional[int] = None,
    cuda_cores: Optional[int] = None,
    model_path: Optional[str | Path] = None,
) -> float:
    """Hàm tiện ích cho phép nhập bất kỳ cấu hình card nào và nhận ngay mức giá dự đoán."""
    if model_path is None:
        model_path = BASE_DIR / "output" / "vga_price_predictor.joblib"
    else:
        model_path = Path(model_path)

    if not model_path.exists():
        raise FileNotFoundError(f"Không tìm thấy model tại {model_path}")

    pipeline = joblib.load(model_path)

    sample_dict: Dict[str, Any] = {
        "gpu_model": gpu_model,
        "brand": brand,
        "chip_manufacturer": chip_manufacturer,
        "vram_gb": vram_gb,
        "vram_type": vram_type,
        "is_oc": 1 if is_oc else 0,
        "fan_count": fan_count,
        "boost_clock_mhz": boost_clock_mhz,
        "tdp_watts": tdp_watts,
        "length_mm": length_mm,
    }
    # Thêm cuda_cores nếu mô hình có sử dụng
    if hasattr(pipeline.named_steps["preprocessor"], "transformers_"):
        num_cols = pipeline.named_steps["preprocessor"].transformers_[0][2]
        if "cuda_cores" in num_cols:
            sample_dict["cuda_cores"] = cuda_cores

    sample_df = pd.DataFrame([sample_dict])
    pred = pipeline.predict(sample_df)[0]
    return float(round(pred, -3))


if __name__ == "__main__":
    train_and_evaluate_models()

    print("\n" + "=" * 70)
    print("TEST HÀM DỰ ĐOÁN GIÁ (INFERENCE DEMO):")
    print("=" * 70)

    test_cards = [
        ("RTX 4060", "ASUS", 8, "GDDR6", "NVIDIA", True, 2, 2535, 115, 227, 3072),
        ("RTX 4070 SUPER", "MSI", 12, "GDDR6X", "NVIDIA", True, 2, 2505, 220, 242, 7168),
        ("RX 7800 XT", "GIGABYTE", 16, "GDDR6", "AMD", True, 3, 2565, 263, 302, 3840),
        ("RTX 5090", "ASUS", 32, "GDDR7", "NVIDIA", True, 3, 2600, 500, 340, 21760),
        ("Arc B580", "ASROCK", 12, "GDDR6", "INTEL", True, 3, 2800, 190, 298, 2560),
    ]

    for model, brand, vram, vtype, mfr, oc, fans, clock, tdp, length, cores in test_cards:
        predicted = predict_custom_vga(
            gpu_model=model,
            brand=brand,
            vram_gb=vram,
            vram_type=vtype,
            chip_manufacturer=mfr,
            is_oc=oc,
            fan_count=fans,
            boost_clock_mhz=clock,
            tdp_watts=tdp,
            length_mm=length,
            cuda_cores=cores,
        )
        print(f"👉 {brand} {model} {vram}GB {vtype} ({fans} quạt, {tdp}W, {cores} cores) -> Giá dự đoán: {predicted:,.0f} VNĐ")
