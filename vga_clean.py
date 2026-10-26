# vga_clean.py — Pipeline làm sạch dataset VGA/GPU crawl (chạy lại được: python vga_clean.py)
# Đầu vào: mọi file vga_*.csv trong thư mục hiện tại. Đầu ra: vga_clean.csv
import glob
import re
import unicodedata
from urllib.parse import urlsplit

import numpy as np
import pandas as pd

MISSING_PRICE = re.compile(
    r"^\s*(li[êe]n h[ệe]|lien he|call|contact|n/?a|na|null|none|-{1,3}|\?|ch[ươ]a c[ậo]p nh[ậa]t)\s*$",
    re.I,
)

def clean_text(s):
    if pd.isna(s):
        return np.nan
    s = str(s)
    s = (
        s.replace("™", " ").replace("\xae", " ").replace(" ", " ")
        .replace("–", "-").replace("—", "-").replace("’", "'")
    )
    s = re.sub(r"<[^>]+>", " ", s)
    s = (
        s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&quot;", '"')
        .replace("&#039;", "'").replace("&#39;", "'").replace("&#x27;", "'")
    )
    s = unicodedata.normalize("NFC", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s or np.nan

def parse_price(raw):
    """Return (price, currency, price_min, price_max). Missing => NaN, never 0."""
    if pd.isna(raw) or MISSING_PRICE.match(str(raw).strip()):
        return np.nan, np.nan, np.nan, np.nan
    s = clean_text(raw) or ""
    if not re.search(r"\d", s):
        return np.nan, np.nan, np.nan, np.nan

    def to_num(tok):
        tok = re.sub(r"[^\d.,]", "", tok)
        if not tok:
            return np.nan
        if re.search(r"\.\d{1,2}$", tok):  # USD / decimal tail: $1,179.99 or $700.00
            tok = tok.replace(",", "")
        elif re.search(r",\d{1,2}$", tok):  # European decimal tail: 1.179,99
            tok = tok.replace(".", "").replace(",", ".")
        else:  # VND thousands grouping: 15.990.000 / 15,990,000 / 15990000
            tok = tok.replace(".", "").replace(",", "")
        try:
            return float(tok)
        except ValueError:
            return np.nan

    m = re.match(r"^\s*\$", s)
    cur = "USD" if m else "VND"
    rng = re.match(r"^(.*?[\d.,]+.*?)(?:\s*(?:-|–|~|đến|to)\s*)(.*?[\d.,]+.*)$", s, re.I)
    if rng:
        lo, hi = to_num(rng.group(1)), to_num(rng.group(2))
        if pd.notna(lo) and pd.notna(hi) and lo > 0 and hi >= lo:
            return np.nan, cur, lo, hi
    return to_num(s), cur, np.nan, np.nan

# GPU model: prefix bắt buộc (RTX/GTX/Quadro/Tesla/FirePro/Radeon RX/Vega/GeForce),
# không bao giờ match từ ngoài tên GPU -> không gộp nhầm model, không bịa model.
GPU_RE = re.compile(
    r"(?i)\b(?:(?:nvidia|amd)\s+)?(?:geforce\s+)?"
    r"(rtx|gtx|gt|gts|mx|quadro|tesla|firepro|nvs|pro\s+wx|wx)\s*(?:pro\s*)?([akmpvtw]?\d{3,4}[a-z]?)\b"
    r"(?:[\s-]+(ti|super|ultimate|xtx|xt|se|ada))?"
    r"(?:[\s-]+(ti|super|ultimate|xtx|xt|se|ada))?"
    r"|\b(?:radeon\s+)?(rx)\s*[\s-]?(\d{3,4})\b"
    r"(?:[\s-]+(xtx|xt|xl|pro|se))?"
    r"(?:[\s-]+(xtx|xt|xl|pro|se))?"
    r"|\b(radeon)\s+(?:(hd|r\d[0-9]?)\s+)?(\d{3,4}x?)\b"
    r"(?:[\s-]+(xtx|xt|xl|pro|se|x))?"
    r"|\b(?:radeon\s+)?pro\s+(w\d{3,4})\b"
    r"|\b(?:nvidia\s+)?(t[456]00|t1000|t2000)\b(?!\s*series)"
    r"|\b(?:geforce\s+)?(210|310|610|710|730)\b(?!\s*(?:gb|ghz|mb|w))"
    r"|\b(arc)\s+([ab]\d{3})\b"
    r"|\bvega\s+(\d{2,3})\b"
)

def extract_gpu_model(text):
    if pd.isna(text):
        return np.nan
    s = re.sub(r"(?i)(\d{3,4})(ti|super|xt)\b", r"\1 \2", str(text))
    m = GPU_RE.search(s)
    if not m:
        return np.nan
    g = m.groups()
    if g[0]:
        if g[0].upper() in {"PRO WX", "WX"}:
            parts = ["RADEON PRO WX", g[1]]
        else:
            parts = [g[0], g[1], g[2], g[3]]
    elif g[4]:
        parts = ["RX", g[5], g[6], g[7]]
    elif g[8]:
        parts = ["RADEON", g[9], g[10], g[11]]
    elif g[12]:
        parts = ["RADEON PRO", g[12]]
    elif g[13]:
        parts = [g[13]]
    elif g[14]:
        parts = ["GEFORCE", g[14]]
    elif g[15]:
        parts = ["ARC", g[16]]
    else:
        parts = ["VEGA", g[17]]
    return " ".join(p.upper() for p in parts if p) or np.nan

def gpu_brand_of(model):
    if pd.isna(model):
        return np.nan
    if model.startswith(("RTX", "GTX", "GT ", "GTS", "MX", "QUADRO", "TESLA", "NVS", "GEFORCE", "T400", "T500", "T600", "T1000", "T2000")):
        return "NVIDIA"
    if model.startswith(("RX", "RADEON", "FIREPRO", "VEGA")):
        return "AMD"
    if model.startswith("ARC"):
        return "INTEL"
    return np.nan

CARD_BRANDS = {
    "asus": "ASUS", "asrock": "ASRock", "msi": "MSI", "gigabyte": "Gigabyte",
    "galax": "GALAX", "kfa2": "KFA2", "pny": "PNY", "evga": "EVGA", "zotac": "ZOTAC",
    "palit": "Palit", "gainward": "Gainward", "colorful": "Colorful", "maxsun": "Maxsun",
    "leadtek": "Leadtek", "sapphire": "Sapphire", "xfx": "XFX", "powercolor": "PowerColor",
    "visiontek": "VisionTek", "bfg": "BFG", "nvidia": "NVIDIA", "amd": "AMD",
    "ocpc": "OCPC", "huananzhi": "Huananzhi", "arktek": "ARTEK", "biostar": "Biostar",
    "inno3d": "Inno3D", "manli": "Manli", "dataland": "Diamond", "diamond": "Diamond",
    "coolmaster": "Cooler Master", "intel": "Intel", "lenovo": "Lenovo", "supermicro": "Supermicro",
    "barracuda": "OpenBox", "openbox": "OpenBox", "apha": "Apha", "ftek": "FTek", "gskill": "",
}
VENDOR_MAP = {
    "philong.com.vn": "Phi Long", "mega.com.vn": "Mega", "phongvu.vn": "Phong Vũ",
    "sp-one.vn": "SP-One", "buildcores.com": "BuildCores",
}
NON_GPU = re.compile(r"(?i)\b(holder kit|graphics card holder|bộ dựng|dựng đứng|dựng dọc|riser cable|water ?block|giá đỡ vga)")
VRAM_GB_RE = re.compile(r"(?i)\b(\d{1,3})\s*(?:gb|g)\b(?!\s*bps)")
VRAM_TYPE_RE = re.compile(r"(?i)\b(gddr[5-7]x?|hbm\d?|ddr3)\b")
# Thứ tự ưu tiên cột thô cho từng trường (không giả định, chỉ dùng cột tồn tại trong file)
BRAND_COLS = ["Thương hiệu", "Thương Hiệu", "THƯƠNG HIỆU", "Hãng", "Hãng sản xuất", "Nhà sản xuất", "Brand", "Manufacturer", "Card Manufacturer"]
MODEL_COLS = ["GPU", "Nhân đồ họa", "Nhân đồ hoạ", "Graphics Processing Unit", "Chipset", "Tên model", "Chip GPU", "Engine đồ họa", "Graphics Engine", "MODEL NAME", "Name"]
VRAM_COLS = ["Bộ nhớ", "BỘ NHỚ", "VRAM", "MEMORY", "Memory", "Video Memory", "Dung lượng", "Dung lượng bộ nhớ", "Bộ nhớ Video", "Frame Buffer Memory", "Dung lượng VRAM"]
VTYPE_COLS = ["Loại bộ nhớ", "Loại Bộ Nhớ", "Kiểu bộ nhớ", "THẾ HỆ BỘ NHỚ", "Memory Type", "Bộ nhớ GPU"]

def first_val(row, cols):
    for c in cols:
        if c in row.index:
            v = clean_text(row[c])
            if isinstance(v, str) and v:
                return v
    return np.nan

def load_file(path):
    df = pd.read_csv(path, low_memory=False, dtype=str)
    n_before = len(df)
    rows = []
    for _, r in df.iterrows():
        name_raw = clean_text(r.get("Tên sản phẩm"))
        name_str = name_raw if isinstance(name_raw, str) else ""
        url = str(r.get("Link sản phẩm") or "").strip().split("#")[0]
        domain = urlsplit(url).netloc.lower().removeprefix("www.")
        seller = VENDOR_MAP.get(domain)
        price, cur, pmin, pmax = parse_price(r.get("Giá hiện tại"))
        price_orig, _, _, _ = parse_price(r.get("Giá gốc"))
        blob = " | ".join(x for x in [name_str, first_val(r, MODEL_COLS), first_val(r, VRAM_COLS)] if isinstance(x, str))
        if NON_GPU.search(name_str) or "/c/" in url:  # phụ kiện / trang danh mục, không phải listing VGA
            continue
        model = extract_gpu_model(name_str)
        if pd.isna(model):  # tên sản phẩm đáng tin hơn cột crawler gây nhiễu (vd "RTX 6500 XT" của shop)
            model = extract_gpu_model(first_val(r, MODEL_COLS))
        gbrand = gpu_brand_of(model)
        cb = np.nan
        for src in (first_val(r, BRAND_COLS), name_str):
            if isinstance(src, str):
                for k, v in CARD_BRANDS.items():
                    if re.search(rf"(?i)\b{k}\b", src) and v:
                        cb = v
                        break
            if isinstance(cb, str):
                break
        gb, vt = np.nan, np.nan
        mphrase = re.search(r"(?i)(\d{1,3})\s*(?:gb|g)\s*[^\s,|]{0,12}?\b(gddr[5-7]x?|ddr3)\b", blob)
        if mphrase:
            gb, vt = float(mphrase.group(1)), mphrase.group(2).upper()
        else:
            mg, mt = VRAM_GB_RE.search(blob or ""), VRAM_TYPE_RE.search(blob or "")
            gb = float(mg.group(1)) if mg else np.nan
            vt = mt.group(1).upper() if mt else np.nan
        rows.append({
            "product_name_raw": r.get("Tên sản phẩm"),
            "product_name_clean": name_raw,
            "price_raw": r.get("Giá hiện tại"),
            "price_vnd": price if cur == "VND" else np.nan,
            "price_usd": price if cur == "USD" else np.nan,
            "currency": cur,
            "price_min_vnd": pmin, "price_max_vnd": pmax,
            "original_price_raw": r.get("Giá gốc"), "original_price_vnd": price_orig,
            "gpu_brand": gbrand, "gpu_model": model, "card_brand": cb,
            "vram_gb": gb, "vram_type": vt,
            "status": clean_text(r.get("Tình trạng")),
            "crawl_date": clean_text(r.get("Thời gian cào")),
            "source_url": url or np.nan, "source_domain": domain or np.nan,
            "seller": seller, "source_file": path,
        })
    out = pd.DataFrame(rows)
    print(f"{path}: {n_before} rows -> {len(out)} kept")
    return out

def detect_anomalies(df):
    flag = np.full(len(df), "normal", dtype=object)
    flag[df["price_vnd"].le(0).fillna(False) | df["price_usd"].le(0).fillna(False)] = "invalid"
    for _, g in df[df["gpu_model"].notna() & (df["price_vnd"].notna() | df["price_usd"].notna())].groupby("gpu_model"):
        if len(g) < 4:
            continue
        for cur, col in (("VND", "price_vnd"), ("USD", "price_usd")):
            gg = g[g["currency"].eq(cur)]
            if len(gg) < 4:
                continue
            med = gg[col].median()
            mad = (gg[col] - med).abs().median()
            lim = max(med * 0.5, mad * 8)
            mask = gg.index[(gg[col] - med).abs() > lim]
            flag[df.index.get_indexer(mask)] = "suspicious"
    df["price_anomaly"] = flag
    return df

def main():
    files = sorted(f for f in glob.glob("vga_*.csv") if f != "vga_clean.csv")
    print("Input files:", files)
    df = pd.concat([load_file(f) for f in files], ignore_index=True)
    miss_before = df.isna().sum()
    df = df.drop_duplicates(subset=["source_url", "product_name_raw", "price_raw", "seller"])
    df = detect_anomalies(df)
    df = df.sort_values(["gpu_model", "seller", "price_vnd", "price_usd"], na_position="last").reset_index(drop=True)
    df.to_csv("vga_clean.csv", index=False, encoding="utf-8-sig")
    print(f"\nRows sau dedup: {len(df)}")
    print("Missing TRƯỚC clean (trên cleaned frame, cột giá NaN gồm cả 'Liên hệ'):\n", miss_before.to_string())
    print("Missing SAU clean:\n", df.isna().sum().to_string())
    print("price_anomaly:", df["price_anomaly"].value_counts().to_dict())
    print("Top gpu_model:\n", df["gpu_model"].value_counts().head(15).to_string())
    print("Đã ghi vga_clean.csv")

if __name__ == "__main__":
    assert parse_price("15.990.000đ")[0] == 15990000
    assert parse_price("15,990,000 VND")[0] == 15990000
    assert parse_price("15 990 000 ₫")[0] == 15990000
    assert parse_price("15990000")[0] == 15990000
    assert parse_price("Liên hệ")[0] is np.nan or (pd.isna(parse_price("Liên hệ")[0]))
    assert pd.isna(parse_price("-")[0])
    assert parse_price("$1,179.99")[0] == 1179.99 and parse_price("$1,179.99")[1] == "USD"
    p, c, mn, mx = parse_price("15.000.000 - 17.000.000 VNĐ")
    assert pd.isna(p) and mn == 15000000 and mx == 17000000
    assert extract_gpu_model("Card Màn Hình MSI GeForce RTX 5060 Ti 16G SHADOW 2X OC PLUS GDDR7") == "RTX 5060 TI"
    assert extract_gpu_model("RTX 4070 SUPER 12GB") == "RTX 4070 SUPER"
    assert extract_gpu_model("GeForce RTX3050 DUAL 8GB") == "RTX 3050"
    assert extract_gpu_model("Radeon RX 9060 XT GAMING OC 8G") == "RX 9060 XT"
    assert extract_gpu_model("ASUS Dual Radeon RX 7600 EVO OC") == "RX 7600"
    assert extract_gpu_model("RTX 4060") != extract_gpu_model("RTX 4060 Ti")
    assert extract_gpu_model("VGA Gigabyte GeForce RTX 4090 Windforce 24G") == "RTX 4090"
    assert extract_gpu_model("Bộ Dựng Dọc VGA Cooler Master Holder Kit V3") is np.nan
    main()
