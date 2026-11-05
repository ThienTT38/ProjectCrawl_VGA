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
  - Target:
      + price_vnd (Mức giá thị trường VNĐ)
  - Mô hình huấn luyện so sánh:
      1. Random Forest Regressor (Mô hình cây tổ hợp mạnh mẽ cho giá phi tuyến)
      2. Gradient Boosting Regressor (Mô hình boosting chính xác cao)
      3. Ridge / Linear Regression (Mô hình hồi quy tuyến tính chuẩn)
  - Đánh giá chất lượng:
      + R² Score (Hệ số xác định độ chính xác)
      + MAE (Sai số tuyệt đối trung bình - VNĐ)
      + MAPE (Sai số phần trăm trung bình - %)
  - Tính năng:
      + Lưu mô hình tốt nhất (`output/vga_price_predictor.joblib`)
      + Dự đoán mức định giá chuẩn cho toàn bộ 4.299 sản phẩm và so sánh "Định giá vs Giá bán" (Overpriced / Underpriced)
      + Cung cấp hàm `predict_vga_price(specs)` để người dùng nhập bất kỳ cấu hình card nào và nhận ngay định giá thị trường!
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
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error, r2_score
from sklearn.model_selection import KFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, RobustScaler
from sklearn.compose import ColumnTransformer

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def train_and_evaluate_models(
    input_csv: str = r"D:\vga-crawler\output\vga_100pct_solution2_used_market.csv",
    output_dir: str = r"D:\vga-crawler\output",
) -> Dict[str, Any]:
    print(f"[*] Đang tải dữ liệu huấn luyện từ: {input_csv}")
    df = pd.read_csv(input_csv)
    total_samples = len(df)
    print(f"[*] Tổng số mẫu dữ liệu: {total_samples}")

    # Chuẩn bị Features và Target
    numeric_features = [
        "vram_gb",
        "is_oc",
        "fan_count",
        "boost_clock_mhz",
        "tdp_watts",
        "length_mm",
    ]
    categorical_features = [
        "chip_manufacturer",
        "brand",
        "vram_type",
        "gpu_model",
    ]

    target = "price_vnd_final"

    # Đảm bảo dữ liệu số
    for col in numeric_features:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    X = df[numeric_features + categorical_features].copy()
    y = df[target].values

    # Preprocessing Pipeline
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

    # Chia tập Train (80%) / Test (20%)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42
    )
    print(f"[*] Tập Train: {len(X_train)} mẫu | Tập Test: {len(X_test)} mẫu")

    # Danh sách các mô hình ứng viên
    models = {
        "Random Forest": RandomForestRegressor(n_estimators=150, max_depth=20, random_state=42, n_jobs=-1),
        "Gradient Boosting": GradientBoostingRegressor(n_estimators=150, max_depth=6, learning_rate=0.1, random_state=42),
        "Ridge Regression": Ridge(alpha=1.0),
    }

    results = {}
    best_model_name = None
    best_r2 = -float("inf")
    best_pipeline = None

    print("\n" + "=" * 65)
    print("KẾT QUẢ HUẤN LUYỆN & ĐÁNH GIÁ MÔ HÌNH DỰ ĐOÁN GIÁ VGA")
    print("=" * 65)

    for name, model in models.items():
        pipeline = Pipeline(steps=[("preprocessor", preprocessor), ("regressor", model)])
        pipeline.fit(X_train, y_train)
        y_pred = pipeline.predict(X_test)

        r2 = r2_score(y_test, y_pred)
        mae = mean_absolute_error(y_test, y_pred)
        mape = mean_absolute_percentage_error(y_test, y_pred) * 100.0

        results[name] = {
            "R2_Score": round(float(r2), 4),
            "MAE_VND": int(round(mae)),
            "MAPE_Percent": round(float(mape), 2),
        }

        print(f"📌 Mô hình: {name:<20}")
        print(f"   - R² Score (Độ chính xác)     : {r2:.4f} ({r2*100:.2f}%)")
        print(f"   - Sai số trung bình (MAE)      : {mae:,.0f} đ")
        print(f"   - Tỷ lệ sai số tương đối (MAPE): {mape:.2f} %")
        print("-" * 65)

        if r2 > best_r2:
            best_r2 = r2
            best_model_name = name
            best_pipeline = pipeline

    print(f"🏆 MÔ HÌNH XUẤT SẮC NHẤT: {best_model_name} (R² = {best_r2*100:.2f}%)")

    # 1. Lưu mô hình tốt nhất vào file joblib
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    model_path = out_dir / "vga_price_predictor.joblib"
    joblib.dump(best_pipeline, model_path)
    print(f"[+] Đã lưu mô hình huấn luyện vào: {model_path}")

    # 2. Sử dụng mô hình tốt nhất để dự đoán mức định giá chuẩn (Fair Value) cho toàn bộ tập dữ liệu
    df["price_predicted_ml"] = np.round(best_pipeline.predict(X), -3)

    # Tính độ lệch định giá: (Giá thực tế - Giá dự đoán)
    # > 0: Sản phẩm bị đội giá (Overpriced); < 0: Sản phẩm giá hời/rẻ hơn thị trường (Good Deal)
    df["price_valuation_diff"] = df["price_vnd_final"] - df["price_predicted_ml"]
    df["price_valuation_diff_pct"] = np.round((df["price_valuation_diff"] / df["price_predicted_ml"]) * 100.0, 2)

    valuation_status = []
    for diff_pct in df["price_valuation_diff_pct"]:
        if diff_pct > 15.0:
            valuation_status.append("OVERPRICED")       # Bán đắt hơn giá trị máy tính toán
        elif diff_pct < -15.0:
            valuation_status.append("GOOD_DEAL")        # Giá hời / Rẻ hơn thị trường
        else:
            valuation_status.append("FAIR_PRICE")      # Đúng giá trị thực
    df["valuation_verdict"] = valuation_status

    # 3. Xuất tập dữ liệu dự đoán hoàn chỉnh
    out_csv = out_dir / "vga_ml_predictions_valuation.csv"
    out_json = out_dir / "vga_ml_predictions_valuation.json"
    df.to_csv(out_csv, index=False, encoding="utf-8-sig")
    df.to_json(out_json, orient="records", force_ascii=False, indent=2)

    # Lưu vào SQLite
    db_path = out_dir / "vga_catalog_cleaned.db"
    with sqlite3.connect(db_path) as conn:
        df.to_sql("vga_ml_valuations", conn, if_exists="replace", index=False)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_vga_ml_verdict ON vga_ml_valuations(valuation_verdict)")
        conn.commit()

    print(f"[+] Đã xuất file đánh giá định giá: {out_csv}")
    print(f"[+] Đã cập nhật bảng SQLite 'vga_ml_valuations' trong: {db_path}")

    # In mẫu một số deal hời và deal đắt
    print("\n🔍 TOP 3 SẢN PHẨM GIÁ HỜI NHẤT THỊ TRƯỜNG (GOOD DEAL):")
    good_deals = df[df["valuation_verdict"] == "GOOD_DEAL"].sort_values("price_valuation_diff_pct").head(3)
    for _, r in good_deals.iterrows():
        print(f"  * {r['normalized_name']} ({r['source'].upper()})")
        print(f"    Giá bán: {r['price_vnd_final']:,.0f} đ | Máy định giá: {r['price_predicted_ml']:,.0f} đ | Rẻ hơn: {abs(r['price_valuation_diff_pct'])}%")

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
    model_path: str = r"D:\vga-crawler\output\vga_price_predictor.joblib",
) -> float:
    """Hàm tiện ích cho phép nhập bất kỳ cấu hình card nào và nhận ngay mức giá dự đoán."""
    pipeline = joblib.load(model_path)
    sample_df = pd.DataFrame([
        {
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
    ])
    pred = pipeline.predict(sample_df)[0]
    return float(round(pred, -3))


if __name__ == "__main__":
    train_and_evaluate_models()

    # Thử nghiệm dự đoán một số card điển hình
    print("\n" + "=" * 65)
    print("TEST HÀM DỰ ĐOÁN GIÁ (INFERENCE DEMO):")
    print("=" * 65)

    test_cards = [
        ("RTX 4060", "ASUS", 8, "GDDR6", "NVIDIA", True, 2, 2535, 115, 227),
        ("RTX 4070 SUPER", "MSI", 12, "GDDR6X", "NVIDIA", True, 2, 2505, 220, 242),
        ("RX 7800 XT", "GIGABYTE", 16, "GDDR6", "AMD", True, 3, 2565, 263, 302),
        ("RTX 5090", "ASUS", 32, "GDDR7", "NVIDIA", True, 3, 2600, 500, 340),
        ("Arc B580", "ASROCK", 12, "GDDR6", "INTEL", True, 3, 2800, 190, 298),
    ]

    for model, brand, vram, vtype, mfr, oc, fans, clock, tdp, length in test_cards:
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
        )
        print(f"👉 {brand} {model} {vram}GB {vtype} ({fans} quạt, {tdp}W) -> Giá dự đoán: {predicted:,.0f} VNĐ")
