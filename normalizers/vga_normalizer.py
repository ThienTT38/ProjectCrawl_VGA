"""
VGA Domain Normalization Engine (`VGANormalizer`).
Responsible for transforming unstructured/semi-structured Vietnamese & English strings
from Philong, Mega, PhongVu, and BuildCores into canonical schema values at the source.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from schemas.vga_schema import (
     VALID_VRAM_SIZES,
    AIBBrand,
    ChipManufacturer,
    StockStatus,
    VRAMType,
)


class NonVGAAccessoryError(ValueError):
    """Raised when an item in a VGA category is actually an accessory (holder, riser, cable)."""


# Keywords that identify non-VGA accessories mixed into VGA category pages
NON_VGA_ACCESSORY_PATTERNS: List[re.Pattern[str]] = [
    re.compile(r"\bgiá\s+đỡ\s+(vga|card)\b", re.IGNORECASE),
    re.compile(r"\bđỡ\s+(vga|card\s+màn\s+hình)\b", re.IGNORECASE),
    re.compile(r"\bchân\s+đế\s+.*?\bvga\b", re.IGNORECASE),
    re.compile(r"\bcáp\s+nối\s+dài\b.*?\b(vga|pcie|riser)\b", re.IGNORECASE),
    re.compile(r"\bdây\s+riser\b", re.IGNORECASE),
    re.compile(r"\briser\s+cable\b", re.IGNORECASE),
    re.compile(r"\bpcie\s+[345]\.0\s+x16\s+riser\b", re.IGNORECASE),
    re.compile(r"\bkhung\s+dựng\s+(vga|card)\b", re.IGNORECASE),
    re.compile(r"\bvga\s+holder\b", re.IGNORECASE),
    re.compile(r"\bgpu\s+support\s+bracket\b", re.IGNORECASE),
    re.compile(r"\bcầu\s+nối\s+nvlink\b", re.IGNORECASE),
]

# Brand alias mapping (ordered from specific to general)
BRAND_PATTERNS: List[Tuple[re.Pattern[str], AIBBrand]] = [
    (re.compile(r"\b(asus|rog\s+strix|rog\s+astral|rog\s+matrix|tuf\s+gaming|proart)\b", re.I), AIBBrand.ASUS),
    (re.compile(r"\b(gigabyte|giga|aorus)\b", re.I), AIBBrand.GIGABYTE),
    (re.compile(r"\b(msi|suprim|ventus)\b", re.I), AIBBrand.MSI),
    (re.compile(r"\b(zotac)\b", re.I), AIBBrand.ZOTAC),
    (re.compile(r"\b(galax|kfa2)\b", re.I), AIBBrand.GALAX),
    (re.compile(r"\b(colorful|igame)\b", re.I), AIBBrand.COLORFUL),
    (re.compile(r"\b(inno3d|ichill)\b", re.I), AIBBrand.INNO3D),
    (re.compile(r"\b(palit|gamerock|jetstream)\b", re.I), AIBBrand.PALIT),
    (re.compile(r"\b(pny|verto|xlr8)\b", re.I), AIBBrand.PNY),
    (re.compile(r"\b(leadtek|winfast)\b", re.I), AIBBrand.LEADTEK),
    (re.compile(r"\b(sapphire|nitro\+?|pulse)\b", re.I), AIBBrand.SAPPHIRE),
    (re.compile(r"\b(power\s*color|red\s+devil|hellhound|red\s+dragon)\b", re.I), AIBBrand.POWERCOLOR),
    (re.compile(r"\b(asrock|taichi|phantom\s+gaming|steel\s+legend|challenger)\b", re.I), AIBBrand.ASROCK),
    (re.compile(r"\b(xfx|speedster|qick|merc|swft)\b", re.I), AIBBrand.XFX),
    (re.compile(r"\b(acer|predator\s+bifrost|nitro)\b", re.I), AIBBrand.ACER),
    (re.compile(r"\bfounders\s+edition\b", re.I), AIBBrand.NVIDIA),
]

# Canonical Series patterns (ordered from most specific to general)
SERIES_PATTERNS: List[Tuple[re.Pattern[str], str, Optional[int]]] = [
    # ASUS
    (re.compile(r"\brog[\s\-]+astral\b", re.I), "ROG Astral", 4),
    (re.compile(r"\brog[\s\-]+matrix\b", re.I), "ROG Matrix", 3),
    (re.compile(r"\brog[\s\-]+strix\b", re.I), "ROG Strix", 3),
    (re.compile(r"\btuf[\s\-]+gaming\b|\btuf\b", re.I), "TUF Gaming", 3),
    (re.compile(r"\bproart\b", re.I), "ProArt", 3),
    (re.compile(r"\bprime\b", re.I), "Prime", 3),
    (re.compile(r"\bdual\b", re.I), "Dual", 2),
    (re.compile(r"\bphoenix\b", re.I), "Phoenix", 1),
    # MSI
    (re.compile(r"\bsuprim[\s\-]+liquid\s*x?\b", re.I), "Suprim Liquid X", 2),
    (re.compile(r"\bsuprim\s*x\b|\bsuprim\b", re.I), "Suprim X", 3),
    (re.compile(r"\bvanguard\b", re.I), "Vanguard", 3),
    (re.compile(r"\bgaming\s*x\s*trio\b|\bgaming\s*trio\b", re.I), "Gaming X Trio", 3),
    (re.compile(r"\bgaming\s*x\s*slim\b|\bgaming\s*slim\b", re.I), "Gaming X Slim", 3),
    (re.compile(r"\bgaming\s*x\b", re.I), "Gaming X", 2),
    (re.compile(r"\bventus\s*3x\b", re.I), "Ventus 3X", 3),
    (re.compile(r"\bventus\s*2x\b", re.I), "Ventus 2X", 2),
    (re.compile(r"\bshadow\s*3x\b", re.I), "Shadow 3X", 3),
    (re.compile(r"\bshadow\s*2x\b", re.I), "Shadow 2X", 2),
    (re.compile(r"\binspire\s*3x\b", re.I), "Inspire 3X", 3),
    (re.compile(r"\baero\s*itx\b", re.I), "Aero ITX", 1),
    # GIGABYTE
    (re.compile(r"\baorus[\s\-]+xtreme\s+waterforce\b", re.I), "Aorus Xtreme Waterforce", 3),
    (re.compile(r"\baorus[\s\-]+master\b", re.I), "Aorus Master", 3),
    (re.compile(r"\baorus[\s\-]+elite\b", re.I), "Aorus Elite", 3),
    (re.compile(r"\baero\s+oc\b|\baero\b", re.I), "Aero", 3),
    (re.compile(r"\bgaming\s+oc\b", re.I), "Gaming OC", 3),
    (re.compile(r"\bwindforce\s*3x\b|\bwf3\b", re.I), "Windforce 3X", 3),
    (re.compile(r"\bwindforce\s*2x\b|\bwf2\b|\bwindforce\b", re.I), "Windforce", 2),
    (re.compile(r"\beagle\b", re.I), "Eagle", 3),
    # ZOTAC
    (re.compile(r"\bamp[\s\-]+extreme[\s\-]+airo\b|\bamp[\s\-]+extreme\b", re.I), "AMP Extreme", 3),
    (re.compile(r"\btrinity\b", re.I), "Trinity", 3),
    (re.compile(r"\btwin[\s\-]+edge\b", re.I), "Twin Edge", 2),
    (re.compile(r"\bsolo\b", re.I), "Solo", 1),
    # COLORFUL
    (re.compile(r"\bigame[\s\-]+vulcan\b|\bvulcan\b", re.I), "iGame Vulcan", 3),
    (re.compile(r"\bigame[\s\-]+ultra\b|\bultra\s*w\b", re.I), "iGame Ultra", 3),
    (re.compile(r"\bigame[\s\-]+advanced\b", re.I), "iGame Advanced", 3),
    (re.compile(r"\bbattle[\s\-]*ax\b", re.I), "Battle Ax", 2),
    # GALAX
    (re.compile(r"\b1[\s\-]*click[\s\-]*oc\s*3x\b|\bsg\b", re.I), "SG 1-Click OC", 3),
    (re.compile(r"\bex[\s\-]+gamer\b", re.I), "EX Gamer", 3),
    (re.compile(r"\b1[\s\-]*click[\s\-]*oc\b", re.I), "1-Click OC", 2),
    # SAPPHIRE & POWERCOLOR & ASROCK & XFX
    (re.compile(r"\bnitro\+\b|\bnitro\s+plus\b", re.I), "Nitro+", 3),
    (re.compile(r"\bpulse\b", re.I), "Pulse", 2),
    (re.compile(r"\bpure\b", re.I), "Pure", 3),
    (re.compile(r"\bred[\s\-]+devil\b", re.I), "Red Devil", 3),
    (re.compile(r"\bhellhound\b", re.I), "Hellhound", 3),
    (re.compile(r"\bred[\s\-]+dragon\b", re.I), "Red Dragon", 2),
    (re.compile(r"\bfighter\b", re.I), "Fighter", 2),
    (re.compile(r"\btaichi\b", re.I), "Taichi", 3),
    (re.compile(r"\bphantom[\s\-]+gaming\b", re.I), "Phantom Gaming", 3),
    (re.compile(r"\bsteel[\s\-]+legend\b", re.I), "Steel Legend", 3),
    (re.compile(r"\bchallenger\b", re.I), "Challenger", 2),
    (re.compile(r"\bspeedster\s+merc\b|\bmerc\s*31[09]\b", re.I), "Speedster MERC", 3),
    (re.compile(r"\bspeedster\s+qick\b|\bqick\s*319\b", re.I), "Speedster QICK", 3),
    (re.compile(r"\bspeedster\s+swft\b|\bswft\s*210\b", re.I), "Speedster SWFT", 2),
]

# Default VRAM lookup when a listing omits explicit GB but specifies an unambiguous GPU model
DEFAULT_GPU_VRAM_GB: Dict[str, Tuple[int, VRAMType]] = {
    "RTX 5090": (32, VRAMType.GDDR7),
    "RTX 5080": (16, VRAMType.GDDR7),
    "RTX 5070 Ti": (16, VRAMType.GDDR7),
    "RTX 5070": (12, VRAMType.GDDR7),
    "RTX 5060 Ti": (16, VRAMType.GDDR7),
    "RTX 5060": (8, VRAMType.GDDR7),
    "RTX 4090 D": (24, VRAMType.GDDR6X),
    "RTX 4090": (24, VRAMType.GDDR6X),
    "RTX 4080 SUPER": (16, VRAMType.GDDR6X),
    "RTX 4080": (16, VRAMType.GDDR6X),
    "RTX 4070 Ti SUPER": (16, VRAMType.GDDR6X),
    "RTX 4070 Ti": (12, VRAMType.GDDR6X),
    "RTX 4070 SUPER": (12, VRAMType.GDDR6X),
    "RTX 4070": (12, VRAMType.GDDR6X),
    "RTX 4060 Ti": (8, VRAMType.GDDR6),
    "RTX 4060": (8, VRAMType.GDDR6),
    "RTX 3090 Ti": (24, VRAMType.GDDR6X),
    "RTX 3090": (24, VRAMType.GDDR6X),
    "RTX 3080 Ti": (12, VRAMType.GDDR6X),
    "RTX 3080": (10, VRAMType.GDDR6X),
    "RTX 3070 Ti": (8, VRAMType.GDDR6X),
    "RTX 3070": (8, VRAMType.GDDR6),
    "RTX 3060 Ti": (8, VRAMType.GDDR6),
    "RTX 3060": (12, VRAMType.GDDR6),
    "RTX 3050": (8, VRAMType.GDDR6),
    "GTX 1660 SUPER": (6, VRAMType.GDDR6),
    "GTX 1650": (4, VRAMType.GDDR6),
    "GT 1030": (2, VRAMType.GDDR5),
    "GT 730": (4, VRAMType.DDR3),
    "RX 9070 XT": (16, VRAMType.GDDR6),
    "RX 9070": (16, VRAMType.GDDR6),
    "RX 7900 XTX": (24, VRAMType.GDDR6),
    "RX 7900 XT": (20, VRAMType.GDDR6),
    "RX 7900 GRE": (16, VRAMType.GDDR6),
    "RX 7800 XT": (16, VRAMType.GDDR6),
    "RX 7700 XT": (12, VRAMType.GDDR6),
    "RX 7600 XT": (16, VRAMType.GDDR6),
    "RX 7600": (8, VRAMType.GDDR6),
    "RX 6800 XT": (16, VRAMType.GDDR6),
    "RX 6750 XT": (12, VRAMType.GDDR6),
    "RX 6700 XT": (12, VRAMType.GDDR6),
    "RX 6650 XT": (8, VRAMType.GDDR6),
    "RX 6600 XT": (8, VRAMType.GDDR6),
    "RX 6600": (8, VRAMType.GDDR6),
    "RX 6500 XT": (4, VRAMType.GDDR6),
    "RX 5600 XT": (6, VRAMType.GDDR6),
    "RX 580": (8, VRAMType.GDDR5),
    "Arc B580": (12, VRAMType.GDDR6),
    "Arc B570": (10, VRAMType.GDDR6),
    "Arc A770": (16, VRAMType.GDDR6),
    "Arc A750": (8, VRAMType.GDDR6),
    "Arc A580": (8, VRAMType.GDDR6),
    "Arc A380": (6, VRAMType.GDDR6),
}


class VGANormalizer:
    """
    Stateless normalizer utility class invoked by all source Adapters to transform
    raw website data into `NormalizedVGASchema` fields right at the scraping boundary.
    """

    @staticmethod
    def assert_is_vga_product(raw_title: str) -> None:
        """Raise NonVGAAccessoryError if the title matches known non-VGA accessories."""
        cleaned = raw_title.strip()
        for pattern in NON_VGA_ACCESSORY_PATTERNS:
            if pattern.search(cleaned):
                raise NonVGAAccessoryError(
                    f"Item '{cleaned}' matched non-VGA accessory filter ({pattern.pattern})"
                )

    @staticmethod
    def extract_gpu_chipset(text: str) -> Optional[str]:
        """
        Extract and normalize GPU chipset model from product title or spec text.
        Examples:
          - 'VGA ASUS Dual GeForce RTX 4060 Ti OC 8GB' -> 'RTX 4060 Ti'
          - 'Card màn hình MSI RTX4070Ti SUPER 16G VENTUS 3X' -> 'RTX 4070 Ti SUPER'
          - 'PowerColor Hellhound AMD Radeon RX 7800XT 16GB' -> 'RX 7800 XT'
          - 'Intel Arc B580 Limited Edition 12GB' -> 'Arc B580'
        """
        if not text:
            return None

        # Pre-normalize trademarks and hyphens between prefix and digits
        s = re.sub(r"[™®]", " ", text)

        # 1. NVIDIA GeForce RTX / GTX / GT
        nvidia_match = re.search(
            r"\b(RTX|GTX|GT)[\s\-]*(\d{3,4})(?:[\s\-]*(Ti[\s\-]+SUPER|Ti|SUPER|D\b))?(?![0-9])",
            s,
            re.IGNORECASE,
        )
        if nvidia_match:
            prefix = nvidia_match.group(1).upper()
            number = nvidia_match.group(2)
            suffix_raw = (nvidia_match.group(3) or "").strip()
            suffix = ""
            if suffix_raw:
                su_upper = re.sub(r"[\s\-]+", " ", suffix_raw.upper())
                if su_upper == "TI SUPER":
                    suffix = " Ti SUPER"
                elif su_upper == "TI":
                    suffix = " Ti"
                elif su_upper == "SUPER":
                    suffix = " SUPER"
                elif su_upper == "D":
                    suffix = " D"
            return f"{prefix} {number}{suffix}"

        # Also check workstation NVIDIA GPUs (e.g. RTX A4000, RTX A2000, RTX 4000 Ada, T1000, T400)
        ws_match = re.search(
            r"\b(RTX\s*A\d{4}|RTX\s*\d{4}\s*Ada|Quadro\s+RTX\s*\d{4}|T1000|T600|T400)\b",
            s,
            re.IGNORECASE,
        )
        if ws_match:
            val = re.sub(r"\s+", " ", ws_match.group(1)).strip()
            val = re.sub(r"^rtx\s*a(\d{4})$", r"RTX A\1", val, flags=re.I)
            return val

        # 2. AMD Radeon RX
        amd_match = re.search(
            r"\b(RX)[\s\-]*(\d{3,4})(?:[\s\-]*(XTX|XT|GRE))?(?![0-9])",
            s,
            re.IGNORECASE,
        )
        if amd_match:
            number = amd_match.group(2)
            suffix_raw = (amd_match.group(3) or "").strip().upper()
            suffix = f" {suffix_raw}" if suffix_raw else ""
            return f"RX {number}{suffix}"

        # 3. Intel Arc
        intel_match = re.search(
            r"\bArc[\s\-]*([AB]\d{3})\b",
            s,
            re.IGNORECASE,
        )
        if intel_match:
            return f"Arc {intel_match.group(1).upper()}"

        return None

    @staticmethod
    def extract_chip_manufacturer(
        gpu_model: Optional[str], raw_text: str = ""
    ) -> ChipManufacturer:
        """Infer NVIDIA / AMD / INTEL from normalized gpu_model or raw text."""
        combined = f"{gpu_model or ''} {raw_text}"
        if gpu_model:
            if gpu_model.startswith(("RTX", "GTX", "GT", "Quadro", "T1000", "T600", "T400")):
                return ChipManufacturer.NVIDIA
            if gpu_model.startswith(("RX", "Radeon", "Vega")):
                return ChipManufacturer.AMD
            if gpu_model.startswith("Arc"):
                return ChipManufacturer.INTEL

        if re.search(r"\b(nvidia|geforce|rtx|gtx|quadro)\b", combined, re.I):
            return ChipManufacturer.NVIDIA
        if re.search(r"\b(amd|radeon|rx\s*\d{3,4})\b", combined, re.I):
            return ChipManufacturer.AMD
        if re.search(r"\b(intel|arc\s*[ab]\d{3})\b", combined, re.I):
            return ChipManufacturer.INTEL
        return ChipManufacturer.UNKNOWN

    @staticmethod
    def extract_aib_brand(
        raw_title: str, explicit_brand: Optional[str] = None
    ) -> AIBBrand:
        """Extract canonical AIB brand from explicit brand field or product title."""
        # Check explicit brand first
        if explicit_brand:
            for pattern, brand_enum in BRAND_PATTERNS:
                if pattern.search(explicit_brand):
                    return brand_enum
            eb_upper = explicit_brand.strip().upper()
            if eb_upper in AIBBrand.__members__:
                return AIBBrand[eb_upper]

        # Search in raw_title
        for pattern, brand_enum in BRAND_PATTERNS:
            if pattern.search(raw_title):
                return brand_enum

        if re.search(r"\bintel\b", raw_title, re.I):
            return AIBBrand.INTEL
        if re.search(r"\bnvidia\b", raw_title, re.I):
            return AIBBrand.NVIDIA
        if re.search(r"\bamd\b", raw_title, re.I):
            return AIBBrand.AMD
        return AIBBrand.OTHER

    @staticmethod
    def extract_series_and_fans(
        raw_title: str,
        explicit_series: Optional[str] = None,
        explicit_cooling: Optional[str] = None,
    ) -> Tuple[Optional[str], Optional[int]]:
        """
        Extract canonical product series (e.g., 'ROG Strix', 'Ventus 2X', 'Windforce')
        and infer fan count (1, 2, 3, 4).
        """
        search_target = f"{explicit_series or ''} {raw_title}".strip()
        detected_series: Optional[str] = None
        inferred_fans: Optional[int] = None

        for pattern, canonical_series, default_fans in SERIES_PATTERNS:
            if pattern.search(search_target):
                detected_series = canonical_series
                inferred_fans = default_fans
                break

        # Override fan count if explicit cooling text or title states exact fan count
        fan_source = f"{explicit_cooling or ''} {raw_title}"
        fan_match = re.search(
            r"\b([1-4])\s*(?:fans?|quạt|x\s*fan)\b|\b([1-4])x\s*(?:oc|fan)\b",
            fan_source,
            re.IGNORECASE,
        )
        if fan_match:
            fan_num = fan_match.group(1) or fan_match.group(2)
            if fan_num:
                inferred_fans = int(fan_num)
        elif re.search(r"\bpassive\b|\bfanless\b|\b0\s*fan\b", fan_source, re.I):
            inferred_fans = 0
        elif re.search(r"\b(3\s*fan|triple\s*fan|3x)\b", fan_source, re.I):
            inferred_fans = 3
        elif re.search(r"\b(2\s*fan|dual\s*fan|2x)\b", fan_source, re.I):
            inferred_fans = 2
        elif re.search(r"\b(1\s*fan|single\s*fan|itx)\b", fan_source, re.I):
            inferred_fans = inferred_fans or 1

        return detected_series, inferred_fans

    @staticmethod
    def extract_is_oc(raw_title: str) -> bool:
        """Detect whether the card is an Overclocked (OC) edition."""
        return bool(
            re.search(
                r"\b(OC|O\d{1,2}G|1-Click\s*OC|SUPER\s+OC|TOP\s+EDITION)\b",
                raw_title,
                re.IGNORECASE,
            )
        )

    @staticmethod
    def extract_vram(
        raw_title: str,
        gpu_model: Optional[str] = None,
        explicit_vram_gb: Optional[Any] = None,
        explicit_vram_type: Optional[str] = None,
    ) -> Tuple[int, VRAMType]:
        """
        Extract VRAM capacity (in GB) and VRAM type (GDDR6, GDDR6X, GDDR7, etc.).
        Handles patterns like:
          - '8GB GDDR6', '12GB GDDR6X', '16G DDR6', 'O8G', '8GD', '12G'
        """
        vram_gb: Optional[int] = None
        vram_type: VRAMType = VRAMType.UNKNOWN

        # 1. Explicit VRAM GB if passed from structured JSON/spec table
        if explicit_vram_gb is not None:
            if isinstance(explicit_vram_gb, (int, float)):
                candidate = int(explicit_vram_gb)
                if candidate in VALID_VRAM_SIZES:
                    vram_gb = candidate
            elif isinstance(explicit_vram_gb, str):
                m_gb = re.search(r"\b(\d{1,2})\s*G(?:B)?\b", explicit_vram_gb, re.I)
                if m_gb and int(m_gb.group(1)) in VALID_VRAM_SIZES:
                    vram_gb = int(m_gb.group(1))

        # 2. Extract VRAM GB from raw_title
        if vram_gb is None:
            # Priority A: '8GB', '12 GB', '16G GDDR6'
            for m in re.finditer(r"\b(\d{1,2})\s*GB\b", raw_title, re.IGNORECASE):
                val = int(m.group(1))
                if val in VALID_VRAM_SIZES:
                    vram_gb = val
                    break

        if vram_gb is None:
            # Priority B: Shorthand like '12G', 'O8G', '8GD', '16GD6' (avoiding '3X', '2X', '4060')
            for m in re.finditer(
                r"\b(?:O|A)?(\d{1,2})G(?:D|DDR\d?)?\b", raw_title, re.IGNORECASE
            ):
                val = int(m.group(1))
                if val in VALID_VRAM_SIZES:
                    vram_gb = val
                    break

        # 3. Extract VRAM Type from explicit_vram_type or raw_title
        type_search = f"{explicit_vram_type or ''} {raw_title}"
        if re.search(r"\bGDDR7\b", type_search, re.I):
            vram_type = VRAMType.GDDR7
        elif re.search(r"\bGDDR6X\b|\bD6X\b", type_search, re.I):
            vram_type = VRAMType.GDDR6X
        elif re.search(r"\bGDDR6\b|\bDDR6\b|\bD6\b", type_search, re.I):
            vram_type = VRAMType.GDDR6
        elif re.search(r"\bGDDR5X\b|\bD5X\b", type_search, re.I):
            vram_type = VRAMType.GDDR5X
        elif re.search(r"\bGDDR5\b|\bDDR5\b|\bD5\b", type_search, re.I):
            vram_type = VRAMType.GDDR5
        elif re.search(r"\bHBM2e?\b", type_search, re.I):
            vram_type = VRAMType.HBM2
        elif re.search(r"\b(?:G)?DDR4\b|\bD4\b", type_search, re.I):
            vram_type = VRAMType.DDR4
        elif re.search(r"\b(?:G)?DDR3\b|\bD3\b", type_search, re.I):
            vram_type = VRAMType.DDR3

        # 4. Fallback to canonical GPU model defaults if missing
        if gpu_model and gpu_model in DEFAULT_GPU_VRAM_GB:
            def_gb, def_type = DEFAULT_GPU_VRAM_GB[gpu_model]
            if vram_gb is None:
                vram_gb = def_gb
            if vram_type == VRAMType.UNKNOWN:
                vram_type = def_type

        return (vram_gb or 0), vram_type

    @staticmethod
    def extract_mpn(raw_title: str, explicit_mpn: Optional[str] = None) -> Optional[str]:
        """
        Extract Manufacturer Part Number (MPN) from explicit field or parenthetical code in title.
        Examples:
          - 'VGA ASUS Dual RTX 4060 OC 8GB (DUAL-RTX4060-O8G-V2)' -> 'DUAL-RTX4060-O8G-V2'
          - 'Card màn hình Gigabyte RTX 4060 Windforce OC 8G (GV-N4060WF2OC-8GD)' -> 'GV-N4060WF2OC-8GD'
        """
        if explicit_mpn and len(explicit_mpn.strip()) >= 4:
            return explicit_mpn.strip().upper()

        # Look for parenthetical codes at the end or middle of title
        for m in re.finditer(r"\(([A-Z0-9][A-Z0-9\-\./]{5,35})\)", raw_title, re.I):
            candidate = m.group(1).strip().upper()
            # Filter out generic spec strings in parentheses like (8GB GDDR6)
            if not re.search(r"\b(GDDR\d|BIT|HDMI|FAN|BH)\b", candidate, re.I):
                if "-" in candidate or re.search(r"\d.*[A-Z]|[A-Z].*\d", candidate):
                    return candidate

        # Known MPN prefixes directly in title (ASUS, Gigabyte, Galax, PowerColor)
        known_mpn = re.search(
            r"\b((?:DUAL|TUF|ROG-STRIX|PROART)-[A-Z0-9\-]{6,25}|GV-[A-Z0-9\-]{7,20}|AXRX\s*[A-Z0-9\-]{6,20})\b",
            raw_title,
            re.IGNORECASE,
        )
        if known_mpn:
            return known_mpn.group(1).strip().upper()

        return None

    @staticmethod
    def normalize_price_vnd(raw_price: Any) -> Optional[int]:
        """
        Convert Vietnamese price representations into integer VND.
        Examples:
          - '8.490.000 đ' -> 8490000
          - '15,990,000₫' -> 15990000
          - 'Liên hệ' / '0đ' / None -> None
        """
        if raw_price is None:
            return None
        if isinstance(raw_price, (int, float)):
            val = int(raw_price)
            return val if val >= 100_000 else None

        s = str(raw_price).strip()
        if not s or re.search(r"liên\s*hệ|call|hết\s*hàng", s, re.I):
            return None

        digits = re.sub(r"[^\d]", "", s)
        if not digits:
            return None
        val = int(digits)
        # Sanity check: a real VGA in VND is at least 100,000 VND
        return val if val >= 100_000 else None

    @staticmethod
    def normalize_warranty_months(raw_warranty: Any) -> Optional[int]:
        """
        Normalize warranty strings like '36 tháng', '3 năm', '36M', 36 -> int months.
        """
        if raw_warranty is None:
            return None
        if isinstance(raw_warranty, int):
            return raw_warranty if 1 <= raw_warranty <= 120 else None

        s = str(raw_warranty).strip()
        m_months = re.search(r"(\d{1,2})\s*(?:tháng|thang|months?|m\b)", s, re.I)
        if m_months:
            return int(m_months.group(1))
        m_years = re.search(r"(\d{1})\s*(?:năm|nam|years?)", s, re.I)
        if m_years:
            return int(m_years.group(1)) * 12
        if s.isdigit() and 1 <= int(s) <= 120:
            return int(s)
        return None

    @staticmethod
    def normalize_stock_status(
        raw_stock: Optional[str], price_vnd: Optional[int] = None
    ) -> StockStatus:
        """Normalize Vietnamese/English stock status strings."""
        if raw_stock:
            s = raw_stock.strip().lower()
            if any(
                k in s
                for k in ("còn hàng", "sẵn hàng", "có hàng", "in stock", "available", "active")
            ):
                return StockStatus.IN_STOCK
            if any(k in s for k in ("đặt hàng", "pre-order", "order", "sắp về", "hàng đặt")):
                return StockStatus.PRE_ORDER
            if any(k in s for k in ("hết hàng", "tạm hết", "out of stock", "sold out", "ngừng kd")):
                return StockStatus.OUT_OF_STOCK
            if any(k in s for k in ("liên hệ", "call", "contact")):
                return StockStatus.CONTACT

        return StockStatus.IN_STOCK if price_vnd is not None else StockStatus.CONTACT

    @staticmethod
    def format_power_connectors(power_dict: Optional[Any]) -> Optional[str]:
        """Convert BuildCores power_connectors object or raw string into canonical text."""
        if not power_dict:
            return None
        if isinstance(power_dict, str):
            cleaned = re.sub(r"\s+", " ", power_dict).strip()
            return cleaned if cleaned and cleaned.lower() not in ("unknown", "none", "không") else None

        parts: List[str] = []
        mapping = [
            ("pcie_12V_2x6", "16-pin (12V-2x6)"),
            ("pcie_12VHPWR", "16-pin (12VHPWR)"),
            ("pcie_8_pin", "8-pin"),
            ("pcie_6_pin", "6-pin"),
        ]
        for key, label in mapping:
            count = power_dict.get(key, 0)
            if isinstance(count, int) and count > 0:
                parts.append(f"{count}x {label}")
        return ", ".join(parts) if parts else "PCIe Slot Powered"

    @staticmethod
    def normalize_price_usd(raw_price: Any) -> Optional[float]:
        """
        Convert USD price strings from BuildCores (e.g. '$309.99', '$1,249.00 USD') into float.
        """
        if raw_price is None:
            return None
        if isinstance(raw_price, (int, float)):
            val = float(raw_price)
            return round(val, 2) if 10.0 <= val <= 20000.0 else None

        s = str(raw_price).strip()
        if not s or "unknown" in s.lower() or "out of stock" in s.lower():
            return None
        m = re.search(r"(\d[\d,]*\.?\d*)", s)
        if not m:
            return None
        try:
            val = float(m.group(1).replace(",", ""))
            return round(val, 2) if 10.0 <= val <= 20000.0 else None
        except ValueError:
            return None

    @classmethod
    def parse_spec_table_dict(
        cls,
        raw_specs: Dict[str, Any],
        raw_title: str = "",
        url: str = "",
    ) -> Dict[str, Any]:
        """
        Unified Spec-Table Normalizer for the detail pages of:
          - BuildCores (`div[data-part-details-spec-row='true']`)
          - Mega (`table.table-spec`)
          - Phi Long (`div#modal table`)
          - Phong Vũ (`div.css-ciimlz` -> `div.css-9zbh2u`)

        Extracts and normalizes all canonical fields from arbitrary Vietnamese/English
        table labels combined with `raw_title` and `url`.
        """
        clean_specs: Dict[str, str] = {}
        for k, v in (raw_specs or {}).items():
            k_str = str(k).strip().rstrip(":")
            v_str = re.sub(r"\s+", " ", str(v)).strip()
            if k_str and v_str and v_str.lower() != "unknown":
                clean_specs[k_str] = v_str

        def _find_spec(*key_patterns: str) -> Optional[str]:
            for kp in key_patterns:
                regex = re.compile(kp, re.IGNORECASE)
                for k, v in clean_specs.items():
                    if regex.search(k):
                        return v
            return None

        raw_gpu_spec = _find_spec(
            r"^chipset$",
            r"chip\s*đồ\s*họa",
            r"nhân\s*đồ\s*họa",
            r"engine\s*đồ\s*họa",
            r"graphics\s*processing",
            r"^gpu$",
            r"gpu\s*chipset",
            r"series\s*chip",
        )
        raw_brand_spec = _find_spec(
            r"^manufacturer$",
            r"hãng\s*sản\s*xuất",
            r"thương\s*hiệu",
            r"nhà\s*sản\s*xuất",
            r"^brand$",
        )
        raw_chip_mfr_spec = _find_spec(
            r"chipset\s*manufacturer",
            r"hãng\s*chip",
        )
        raw_series_spec = _find_spec(
            r"^series$",
            r"^variant$",
            r"dòng\s*sản\s*phẩm",
        )
        raw_vram_spec = _find_spec(
            r"^memory$",
            r"dung\s*lượng\s*bộ\s*nhớ",
            r"^bộ\s*nhớ",
            r"bộ\s*nhớ\s*vram",
            r"vram",
            r"memory\s*size",
        )
        raw_vram_type_spec = _find_spec(
            r"memory\s*type",
            r"loại\s*bộ\s*nhớ",
            r"kiểu\s*bộ\s*nhớ",
            r"chuẩn\s*bộ\s*nhớ",
        )
        raw_cooling_spec = _find_spec(
            r"^cooling$",
            r"tản\s*nhiệt",
            r"số\s*quạt",
            r"quạt\s*làm\s*mát",
        )
        raw_mpn_spec = _find_spec(
            r"part[\s\-]*numbers?",
            r"mã\s*sản\s*phẩm",
            r"^p/n$",
            r"^mpn$",
        )
        raw_warranty_spec = _find_spec(
            r"bảo\s*hành",
            r"warranty",
        )
        raw_boost_spec = _find_spec(
            r"core\s*boost\s*clock",
            r"boost\s*clock",
            r"xung\s*nhịp",
            r"core\s*clock",
        )
        raw_tdp_spec = _find_spec(
            r"^tdp$",
            r"công\s*suất\s*tiêu\s*thụ",
        )
        raw_psu_spec = _find_spec(
            r"nguồn\s*đề\s*(?:xuất|nghị)",
            r"công\s*suất\s*nguồn",
            r"recommended\s*psu",
            r"psu\s*đề\s*nghị",
        )
        raw_length_spec = _find_spec(
            r"^length$",
            r"kích\s*thước",
            r"chiều\s*dài",
            r"dimensions",
        )
        raw_slot_spec = _find_spec(
            r"total\s*slot\s*width",
            r"slot\s*width",
            r"số\s*khe\s*cắm",
        )
        raw_power_conn_spec = _find_spec(
            r"power\s*connectors?",
            r"đầu\s*cấp\s*nguồn",
            r"nguồn\s*phụ",
            r"cổng\s*kết\s*nối\s*nguồn",
        )

        combined_text = " | ".join(
            filter(
                None,
                [
                    raw_gpu_spec,
                    raw_title,
                    raw_vram_spec,
                    raw_vram_type_spec,
                    raw_cooling_spec,
                    url,
                ],
            )
        )

        gpu_model = cls.extract_gpu_chipset(combined_text) or ""
        chip_manufacturer = cls.extract_chip_manufacturer(
            gpu_model, f"{raw_chip_mfr_spec or ''} {combined_text}"
        )
        brand = cls.extract_aib_brand(raw_title, explicit_brand=raw_brand_spec)
        series, fan_count = cls.extract_series_and_fans(
            raw_title,
            explicit_series=raw_series_spec,
            explicit_cooling=raw_cooling_spec,
        )
        is_oc = cls.extract_is_oc(f"{raw_title} {raw_series_spec or ''} {raw_mpn_spec or ''} {url}")
        vram_gb, vram_type = cls.extract_vram(
            combined_text,
            gpu_model=gpu_model,
            explicit_vram_gb=raw_vram_spec,
            explicit_vram_type=raw_vram_type_spec or raw_vram_spec,
        )
        mpn = cls.extract_mpn(f"{raw_title} ({raw_mpn_spec or ''})", explicit_mpn=raw_mpn_spec)
        warranty_months = cls.normalize_warranty_months(raw_warranty_spec) or 36

        # Boost clock (MHz)
        boost_clock_mhz: Optional[int] = None
        if raw_boost_spec:
            # Find highest MHz number in boost clock string
            mhz_matches = [
                int(m)
                for m in re.findall(r"\b(\d{3,4})\s*(?:MHz)?\b", raw_boost_spec, re.I)
                if 800 <= int(m) <= 4500
            ]
            if mhz_matches:
                boost_clock_mhz = max(mhz_matches)

        # TDP (Watts)
        tdp_watts: Optional[int] = None
        if raw_tdp_spec:
            m_tdp = re.search(r"\b(\d{2,4})\s*W?\b", raw_tdp_spec, re.I)
            if m_tdp and 15 <= int(m_tdp.group(1)) <= 1000:
                tdp_watts = int(m_tdp.group(1))

        # Recommended PSU (Watts)
        recommended_psu_watts: Optional[int] = None
        if raw_psu_spec:
            m_psu = re.search(r"\b(\d{3,4})\s*W?\b", raw_psu_spec, re.I)
            if m_psu and 250 <= int(m_psu.group(1)) <= 2000:
                recommended_psu_watts = int(m_psu.group(1))

        # Physical card length (mm)
        length_mm: Optional[int] = None
        if raw_length_spec:
            # Matches either '242 mm' or '242 x 125 x 43 mm' or '24.2 cm'
            m_dim = re.search(
                r"\b(\d{2,3}(?:\.\d+)?)\s*(?:[xX×]\s*\d+|\s*mm\b)",
                raw_length_spec,
                re.I,
            )
            if m_dim:
                val_f = float(m_dim.group(1))
                if "cm" in raw_length_spec.lower() and val_f < 60:
                    val_f *= 10.0
                if 100 <= round(val_f) <= 500:
                    length_mm = int(round(val_f))
            elif raw_length_spec.strip().isdigit():
                val_i = int(raw_length_spec.strip())
                if 100 <= val_i <= 500:
                    length_mm = val_i

        # Slot width
        slot_width: Optional[float] = None
        if raw_slot_spec:
            m_slot = re.search(r"(\d(?:\.\d+)?)", raw_slot_spec)
            if m_slot and 1.0 <= float(m_slot.group(1)) <= 5.0:
                slot_width = float(m_slot.group(1))

        power_connectors = cls.format_power_connectors(raw_power_conn_spec)

        return {
            "mpn": mpn,
            "chip_manufacturer": chip_manufacturer,
            "gpu_model": gpu_model,
            "brand": brand,
            "series": series,
            "is_oc": is_oc,
            "vram_gb": vram_gb,
            "vram_type": vram_type,
            "fan_count": fan_count,
            "warranty_months": warranty_months,
            "boost_clock_mhz": boost_clock_mhz,
            "tdp_watts": tdp_watts,
            "recommended_psu_watts": recommended_psu_watts,
            "length_mm": length_mm,
            "slot_width": slot_width,
            "power_connectors": power_connectors,
            "raw_specs": clean_specs,
        }
