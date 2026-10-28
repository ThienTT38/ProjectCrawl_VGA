"""Phân tích & trực quan hóa giá VGA/GPU từ vga_clean.csv.
Chạy: python vga_analysis.py  -> mỗi biểu đồ hiện ra cửa sổ riêng (tắt cửa sổ để sang biểu đồ tiếp theo).
"""
import sys, io
import pandas as pd
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sns.set_theme(style="whitegrid")

# --- palette đã validate bằng dataviz skill (CVD-safe, light surface) ---
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
SEQ = ["#86b6ef", "#6da7ec", "#5598e7", "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281"]
INK, MUTED, GRID = "#0b0b0b", "#898781", "#e1e0d9"
plt.rcParams.update({
    "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb",
    "axes.edgecolor": "#c3c2b7", "axes.labelcolor": INK,
    "text.color": INK, "xtick.color": MUTED, "ytick.color": MUTED,
    "grid.color": GRID, "axes.grid": True, "axes.spines.top": False,
    "axes.spines.right": False, "font.size": 10,
    "axes.titlesize": 13, "axes.titleweight": "bold", "axes.titlepad": 14,
    "legend.frameon": False,
})

df_raw = pd.read_csv("vga_clean.csv")
df = df_raw.copy()
priced = df.dropna(subset=["price_vnd"])
priced = priced[priced["price_vnd"] > 0]

# Placeholder filter: cùng 1 mức giá khớp >= 10 GPU model khác cấp trong cùng 1 seller
# -> đó là giá "liên hệ báo giá"/mặc định, không phải giá thật. Chi tiết ở mục 9.
_sh = priced.groupby(["seller", "price_vnd"])["gpu_model"].nunique().rename("n_model").reset_index()
_ph = _sh[_sh["n_model"] >= 10]
mask = pd.Series(False, index=priced.index)
for _, r in _ph.iterrows():
    mask |= (priced["seller"] == r["seller"]) & (priced["price_vnd"] == r["price_vnd"])
df = df[~df.index.isin(priced.index[mask])]
priced = priced[~mask]
price = priced["price_vnd"]
print(f"Đã loại {mask.sum()} dòng giá placeholder (nghiên cứu ở mục 9): {len(price):,} dòng còn lại để phân tích")


def fmt_vnd(x, _=None):
    return f"{x/1e6:,.1f}tr" if x >= 1e6 else (f"{x/1e3:,.0f}k" if x > 0 else "0")


def show(fig, name):
    """Đặt tên cửa sổ và căn bố cục; plt.show() cuối file sẽ bật tất cả cửa sổ lên màn hình."""
    fig.canvas.manager.set_window_title(name)
    fig.tight_layout()


# ============ 1. DATA OVERVIEW ============
print("=" * 70)
print("1. DATA OVERVIEW")
print("=" * 70)
print(f"Rows: {len(df_raw):,} | Columns: {df_raw.shape[1]}")
print(f"Columns: {', '.join(df_raw.columns)}")
print("\nData types:")
print(df_raw.dtypes.to_string())
print("\nMissing values:")
print(df_raw.isnull().sum().to_string())
print(f"\nExact duplicates: {df_raw.duplicated().sum()}")
dup_key = df_raw.duplicated(subset=["product_name_clean", "price_vnd", "source_domain"]).sum()
print(f"Duplicates theo (tên + giá + domain): {dup_key}")
print(f"Unique gpu_model: {df_raw['gpu_model'].nunique()} | Unique gpu_brand: {df_raw['gpu_brand'].nunique()} "
      f"| Unique card_brand: {df_raw['card_brand'].nunique()} | Unique seller: {df_raw['seller'].nunique()}")
print(f"Sellers: {df_raw['seller'].value_counts().to_dict()}")
print(f"GPU brands: {df_raw['gpu_brand'].value_counts(dropna=False).to_dict()}")
print(f"Card brands: {df_raw['card_brand'].value_counts().head(10).to_dict()}")
p_raw = df_raw["price_vnd"].dropna()
print(f"Giá có hợp lệ (price_vnd > 0): {len(p_raw):,} / {len(df_raw):,} dòng "
      f"({len(p_raw)/len(df_raw)*100:.1f}%) - {df_raw['price_vnd'].isna().sum():,} dòng thiếu giá")
print(f"price_min_vnd / price_max_vnd: rỗng 100% -> không dùng được")

# ============ 2. PRICE SUMMARY ============
print("\n" + "=" * 70)
print("2. THỐNG KÊ GIÁ (VND)")
print("=" * 70)
q1, q3 = price.quantile([0.25, 0.75])
iqr = q3 - q1
stats = {
    "Count": len(price), "Min": price.min(), "Max": price.max(), "Mean": price.mean(),
    "Median": price.median(), "Std": price.std(), "Q1": q1, "Q3": q3, "IQR": iqr,
    "Skewness": price.skew(),
    "Outlier_hi": (price > q3 + 1.5 * iqr).sum(), "Outlier_lo": (price < q1 - 1.5 * iqr).sum(),
}
for k, v in stats.items():
    print(f"{k:12s}: {v:,.0f}" if k not in ("Count", "Skewness", "Outlier_hi", "Outlier_lo") else f"{k:12s}: {v:,.2f}")
hi, lo = q3 + 1.5 * iqr, q1 - 1.5 * iqr
print(f"\nNgõ IQR: [{lo:,.0f} ; {hi:,.0f}]")
for a, b, lab in [(0, 5e6, "< 5 triệu"), (5e6, 10e6, "5-10 triệu"), (10e6, 15e6, "10-15 triệu"),
                  (15e6, 25e6, "15-25 triệu"), (25e6, 1e12, "> 25 triệu")]:
    n = ((price >= a) & (price < b)).sum()
    print(f"  {lab:12s}: {n:5,} ({n/len(price)*100:5.1f}%)")

# ============ 3. DISTRIBUTION ============
print("\n" + "=" * 70)
print("3. PHÂN PHỐI GIÁ")
print("=" * 70)
fig, ax = plt.subplots(figsize=(10, 5.5))
CLIP = 100e6  # shortcut: trục histogram cắt ở 100tr, các listing workstation cao hơn rơi vào bin cuối; nâng ngưỡng nếu cần nhìn dải cao
ax.hist(price[price <= CLIP], bins=40, color=BLUE, edgecolor="#fcfcfb", linewidth=1.5)
ax.axvline(price.median(), color=ORANGE, lw=2, ls="--",
           label=f"Median = {price.median()/1e6:.1f} triệu")
ax.set_title("Phân phối giá VGA/GPU tại Việt Nam (trục giá cắt ở 100 triệu VND)")
ax.set_xlabel("Giá (triệu VND)")
ax.set_ylabel("Số lượng sản phẩm")
ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x/1e6:.0f}"))
ax.legend()
show(fig, "03a_histogram_price")

fig, ax = plt.subplots(figsize=(10, 3.2))
sns.boxplot(data=price.clip(upper=CLIP), orient="h", ax=ax, color=BLUE, width=0.5,
            flierprops=dict(marker="o", ms=4, mfc=ORANGE, mec="none", alpha=0.6))
ax.set_title("Boxplot phân phối giá VGA/GPU (thang giá cắt ở 100 triệu VND)")
ax.set_xlabel("Giá (triệu VND)")
ax.set_ylabel("")
ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x/1e6:.0f}"))
show(fig, "03b_boxplot_price")

print(f"Skewness = {price.skew():.2f} -> phân phối lệch phải (right-skewed)")
print(f"IQR = {iqr/1e6:.1f} triệu; {stats['Outlier_hi']:.0f} sản phẩm (> {hi/1e6:.1f} triệu) "
      f"và {stats['Outlier_lo']:.0f} sản phẩm (< {lo/1e6:.1f} triệu) là outlier")

# ============ 4 & 5. TOP / BOTTOM GPU ============
for sec, col, n, asc in [(4, "expensive", 10, False), (5, "cheap", 10, True)]:
    sub = df.dropna(subset=["price_vnd"]).sort_values("price_vnd", ascending=asc).head(n)
    print("\n" + "=" * 70)
    print(f"{sec}. {'TOP 10 GPU ĐẮT NHẤT' if not asc else 'TOP 10 GPU RẺ NHẤT'}")
    print("=" * 70)
    print(sub[["gpu_model", "product_name_clean", "card_brand", "price_vnd", "seller"]].to_string(index=False))

    fig, ax = plt.subplots(figsize=(11, 5.8))
    labels = [f"{r.gpu_model} — {r.product_name_clean[:34]}{'…' if len(r.product_name_clean) > 34 else ''}"
              for _, r in sub.iterrows()]
    bars = ax.barh(range(len(sub)), sub["price_vnd"], color=BLUE if not asc else AQUA, height=0.68)
    span = sub["price_vnd"].max()
    for bar, val in zip(bars, sub["price_vnd"]):
        ax.text(bar.get_width() + span * 0.012, bar.get_y() + bar.get_height()/2,
                f"{val/1e6:,.2f} tr", va="center", ha="left", fontsize=9, color=INK)
    ax.set_yticks(range(len(sub)), labels)
    ax.invert_yaxis()
    ax.set_xlim(0, span * 1.18)
    ax.set_title(f"Top 10 GPU {'có giá cao nhất' if not asc else 'có giá thấp nhất'}")
    ax.set_xlabel("Giá (VND)")
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: fmt_vnd(x)))
    ax.grid(axis="y", visible=False)
    show(fig, f"0{sec}_top10_{col}")

# ============ 6. THEO GPU MODEL ============
print("\n" + "=" * 70)
print("6. SO SÁNH GIÁ THEO GPU MODEL")
print("=" * 70)
g = (df.dropna(subset=["price_vnd"]).groupby("gpu_model")["price_vnd"]
     .agg(count="size", avg="mean", median="median", min="min", max="max")
     .reset_index())
print(f"Tổng {len(g)} GPU model có giá hợp lệ. Model xuất hiện nhiều nhất:")
print(g.sort_values("count", ascending=False).head(15).to_string(index=False))
print("\nModel có giá trung bình cao nhất (n>=5):")
print(g[g["count"] >= 5].sort_values("avg", ascending=False).head(10).to_string(index=False))
print("\nModel có giá trung bình thấp nhất (n>=5):")
print(g[g["count"] >= 5].sort_values("avg").head(10).to_string(index=False))

top = g.sort_values("count", ascending=False).head(15).sort_values("avg")
fig, ax = plt.subplots(figsize=(11, 6.5))
bars = ax.barh(top["gpu_model"], top["avg"], color=BLUE, height=0.7)
for bar, n in zip(bars, top["count"]):
    ax.text(bar.get_width() + ax.get_xlim()[1] * 0.004, bar.get_y() + bar.get_height()/2,
            f"{bar.get_width()/1e6:,.1f}tr (n={n})", va="center", fontsize=9, color=INK)
ax.set_title("Giá trung bình theo GPU model — Top 15 model phổ biến nhất")
ax.set_xlabel("Giá trung bình (VND)")
ax.set_ylabel("")
ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: fmt_vnd(x)))
ax.grid(axis="y", visible=False)
ax.set_xlim(0, top["avg"].max() * 1.28)
show(fig, "06_avg_price_by_model")

# ============ 7. THEO BRAND ============
print("\n" + "=" * 70)
print("7. SO SÁNH GIÁ THEO BRAND (card_brand = AIB partner)")
print("=" * 70)
b = (df.dropna(subset=["price_vnd", "card_brand"]).groupby("card_brand")["price_vnd"]
     .agg(count="size", avg="mean", median="median", min="min", max="max").reset_index())
b["n_model"] = df.dropna(subset=["price_vnd", "card_brand"]).groupby("card_brand")["gpu_model"].nunique().values
bb = b[b["count"] >= 10].sort_values("avg", ascending=False)
print(f"Có {len(b)} card_brand; {len(bb)} brand có >= 10 listing:")
print(bb.to_string(index=False))

fig, ax = plt.subplots(figsize=(11, 6))
bars = ax.bar(bb["card_brand"], bb["avg"], color=AQUA, width=0.66)
for bar, med, n in zip(bars, bb["median"], bb["count"]):
    ax.plot([bar.get_x() + bar.get_width()/2], [med], marker="D", ms=7, color=INK, zorder=3)
    ax.text(bar.get_x() + bar.get_width()/2, max(bar.get_height(), med) + bb["avg"].max()*0.02,
            f"n={n}", ha="center", fontsize=9, color=MUTED)
ax.set_title("Giá trung bình theo brand (hình thoi đen = median)")
ax.set_ylabel("Giá trung bình (VND)")
ax.set_xlabel("")
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: fmt_vnd(x)))
ax.set_ylim(0, bb["avg"].max() * 1.15)
ax.tick_params(axis="x", labelrotation=30)
plt.setp(ax.get_xticklabels(), ha="right")
ax.grid(axis="x", visible=False)
show(fig, "07_avg_price_by_brand")

# ============ BONUS: brand AIB vs chip vendor ============
print("\n" + "=" * 70)
print("BONUS. PHÂN TÍCH HỖ TRỢ: GPU brand (NVIDIA/AMD/Intel) & VRAM")
print("=" * 70)
gb = df.dropna(subset=["price_vnd"]).groupby("gpu_brand")["price_vnd"].agg(["size", "mean", "median"])
print(gb.to_string())
vr = df.dropna(subset=["price_vnd", "vram_gb"]).groupby("vram_gb")["price_vnd"].agg(["size", "mean"]).query("size >= 10")
print(vr.to_string())
fig, ax = plt.subplots(figsize=(9, 4.8))
ax.bar([i for i, _ in enumerate(vr.index)], vr["mean"], color=[SEQ[min(len(SEQ)-1, int(i))] for i in range(len(vr))], width=0.7)
ax.set_xticks(range(len(vr)), [f"{v:g}GB" for v in vr.index])
for i, (m, n) in enumerate(zip(vr["mean"], vr["size"])):
    ax.text(i, m + vr["mean"].max()*0.015, f"{m/1e6:.1f}tr\n(n={n})", ha="center", fontsize=9, color=INK)
ax.set_title("Giá trung bình theo dung lượng VRAM")
ax.set_ylabel("Giá trung bình (VND)")
ax.set_xlabel("VRAM")
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: fmt_vnd(x)))
ax.set_ylim(0, vr["mean"].max() * 1.22)
ax.grid(axis="x", visible=False)
show(fig, "08_vram_vs_price")

# ============ 9. DATA QUALITY: placeholder price ============
print("\n" + "=" * 70)
print("9. KIỂM TRA CHẤT LƯỢNG: giá placeholder (cùng 1 mức giá cho nhiều dòng GPU khác cấp)")
print("=" * 70)
d = df_raw.dropna(subset=["price_vnd"])
share = d.groupby(["seller", "price_vnd"])["gpu_model"].nunique().rename("n_model").reset_index()
ph = share[share["n_model"] >= 10][["seller", "price_vnd", "n_model"]]
print("Giá nghi là placeholder / 'liên hệ báo giá':")
print(ph.to_string(index=False))
mask_ph = pd.Series(False, index=d.index)
for _, r in ph.iterrows():
    mask_ph |= (d["seller"] == r["seller"]) & (d["price_vnd"] == r["price_vnd"])
clean = d[~mask_ph]["price_vnd"]
c1, c3 = clean.quantile([0.25, 0.75])
print(f"\nTrước khi loại: n={len(p_raw):,}, median={p_raw.median()/1e6:.1f}tr, mean={p_raw.mean()/1e6:.1f}tr")
print(f"Sau khi loại placeholder: n={len(clean):,}, median={clean.median()/1e6:.1f}tr, "
      f"mean={clean.mean()/1e6:.1f}tr, Q1={c1/1e6:.1f}tr, Q3={c3/1e6:.1f}tr, "
      f"IQR={(c3-c1)/1e6:.1f}tr, skew={clean.skew():.2f}, max={clean.max()/1e6:.0f}tr")

g_raw = (d.groupby("gpu_model")["price_vnd"]
         .agg(count="size", avg="mean", median="median", min="min", max="max"))
gcl = (d[~mask_ph].groupby("gpu_model")["price_vnd"]
       .agg(count="size", avg="mean", median="median", min="min", max="max"))
print("\nẢnh hưởng lên các model bị placeholder (trước -> sau):")
for m in ["RTX 5090", "RTX 5080", "RTX 5070 TI", "RTX 5070", "RTX 5060 TI", "GT 1030"]:
    a, b2 = g_raw[g_raw.index == m], gcl[gcl.index == m]
    if len(a) and len(b2):
        print(f"  {m:12s} median {a['median'].iloc[0]/1e6:5.1f} -> {b2['median'].iloc[0]/1e6:6.1f}tr | "
              f"min {a['min'].iloc[0]/1e6:5.1f} -> {b2['min'].iloc[0]/1e6:6.1f}tr | "
              f"n {a['count'].iloc[0]:3d} -> {b2['count'].iloc[0]:3d}")

fig, ax = plt.subplots(figsize=(10, 4.6))
order = d.groupby("seller")["price_vnd"].median().sort_values().index
sns.boxplot(data=d[d["seller"].isin(order)], x="seller", y="price_vnd", ax=ax,
            order=list(order), color=BLUE, width=0.6,
            flierprops=dict(marker="o", ms=3, mfc=ORANGE, mec="none", alpha=0.4))
ax.set_yscale("log")
ax.set_title("Giá theo từng người bán (thang log) — Mega lệch chuẩn vì giá placeholder 13,9tr")
ax.set_ylabel("Giá (VND, thang log)")
ax.set_xlabel("")
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: fmt_vnd(x)))
show(fig, "09_price_by_seller")

print("\nĐang mở 8 cửa sổ biểu đồ trên màn hình (đóng các cửa sổ để kết thúc chương trình)...")
plt.show()
