"""
Canonical VGA Data Contract (Schema-First Scraping Architecture).
All source adapters (Philong, Mega, PhongVu, BuildCores) MUST normalize their raw data
into `NormalizedVGASchema` before any persistence or downstream processing occurs.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from core.compat import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class SourceSite(str, Enum):
    """Supported data sources."""

    PHILONG = "philong"
    MEGA = "mega"
    PHONGVU = "phongvu"
    BUILDCORES = "buildcores"


class ChipManufacturer(str, Enum):
    """GPU silicon designer."""

    NVIDIA = "NVIDIA"
    AMD = "AMD"
    INTEL = "INTEL"
    UNKNOWN = "UNKNOWN"


class AIBBrand(str, Enum):
    """Add-in-Board (AIB) card manufacturer."""

    ASUS = "ASUS"
    MSI = "MSI"
    GIGABYTE = "GIGABYTE"
    ZOTAC = "ZOTAC"
    GALAX = "GALAX"
    COLORFUL = "COLORFUL"
    INNO3D = "INNO3D"
    PALIT = "PALIT"
    PNY = "PNY"
    LEADTEK = "LEADTEK"
    SAPPHIRE = "SAPPHIRE"
    POWERCOLOR = "POWERCOLOR"
    ASROCK = "ASROCK"
    XFX = "XFX"
    ACER = "ACER"
    INTEL = "INTEL"
    NVIDIA = "NVIDIA"
    AMD = "AMD"
    OTHER = "OTHER"


class VRAMType(str, Enum):
    """Graphics memory standard."""

    GDDR7 = "GDDR7"
    GDDR6X = "GDDR6X"
    GDDR6 = "GDDR6"
    GDDR5X = "GDDR5X"
    GDDR5 = "GDDR5"
    HBM2 = "HBM2"
    DDR4 = "DDR4"
    DDR3 = "DDR3"
    UNKNOWN = "UNKNOWN"


class StockStatus(str, Enum):
    """Normalized inventory availability."""

    IN_STOCK = "IN_STOCK"
    OUT_OF_STOCK = "OUT_OF_STOCK"
    PRE_ORDER = "PRE_ORDER"
    CONTACT = "CONTACT"
    UNKNOWN = "UNKNOWN"


VALID_VRAM_SIZES = {1, 2, 3, 4, 6, 8, 10, 11, 12, 16, 20, 24, 32, 48, 64, 80}


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower())
    return cleaned.strip("-")


class NormalizedVGASchema(BaseModel):
    """
    Canonical Schema-First contract for a Graphics Card (VGA) record.
    Enforces strict domain invariants at the scraping boundary.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    # --- 1. Identity & Source Provenance ---
    source: SourceSite = Field(..., description="Origin website identifier")
    sku: str = Field(..., min_length=1, description="Source-specific product SKU or ID")
    mpn: Optional[str] = Field(
        default=None,
        description="Manufacturer Part Number (e.g., DUAL-RTX4060-O8G-V2) for exact cross-site matching",
    )
    raw_name: str = Field(..., min_length=3, description="Original unedited title from source")
    normalized_name: str = Field(
        default="",
        description="Clean standardized display name generated from normalized specs",
    )
    url: str = Field(..., min_length=8, description="Absolute canonical product URL")
    image_url: Optional[str] = Field(default=None, description="Absolute primary product image URL")

    # --- 2. Commercial Metadata ---
    price_vnd: Optional[int] = Field(
        default=None,
        ge=0,
        description="Current selling price in VND (None if Contact/Unlisted)",
    )
    original_price_vnd: Optional[int] = Field(
        default=None,
        ge=0,
        description="Original list price in VND before discount",
    )
    price_usd: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Reference price in USD (primarily from BuildCores)",
    )
    discount_percent: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=99.0,
        description="Computed discount percentage when original_price_vnd > price_vnd",
    )
    stock_status: StockStatus = Field(
        default=StockStatus.UNKNOWN,
        description="Normalized stock status",
    )
    warranty_months: Optional[int] = Field(
        default=None,
        ge=1,
        le=120,
        description="Warranty duration in months (e.g., 36)",
    )

    # --- 3. Normalized Technical Specifications (Core VGA Taxonomy) ---
    chip_manufacturer: ChipManufacturer = Field(
        ...,
        description="GPU silicon vendor (NVIDIA, AMD, INTEL)",
    )
    gpu_model: str = Field(
        ...,
        min_length=3,
        description="Canonical GPU chipset name (e.g., 'RTX 4060', 'RTX 4070 Ti SUPER', 'RX 7800 XT')",
    )
    brand: AIBBrand = Field(
        ...,
        description="Normalized AIB partner brand (e.g., ASUS, MSI, GIGABYTE)",
    )
    series: Optional[str] = Field(
        default=None,
        description="Normalized product line / cooler series (e.g., 'ROG Strix', 'Ventus 2X', 'Gaming OC')",
    )
    is_oc: bool = Field(
        default=False,
        description="True if factory overclocked (OC / TOP / SUPER OC edition)",
    )
    vram_gb: int = Field(
        ...,
        ge=1,
        le=128,
        description="VRAM capacity in Gigabytes (e.g., 8, 12, 16, 24)",
    )
    vram_type: VRAMType = Field(
        default=VRAMType.UNKNOWN,
        description="VRAM memory technology (e.g., GDDR6, GDDR6X, GDDR7)",
    )
    fan_count: Optional[int] = Field(
        default=None,
        ge=0,
        le=4,
        description="Number of cooling fans (0 for passive/liquid block, 1, 2, 3, or 4)",
    )

    # --- 4. Extended Hardware Specs (Enriched from BuildCores or Detail Table) ---
    boost_clock_mhz: Optional[int] = Field(
        default=None,
        ge=300,
        le=5000,
        description="GPU boost clock speed in MHz",
    )
    tdp_watts: Optional[int] = Field(
        default=None,
        ge=15,
        le=1000,
        description="Thermal Design Power (TDP) in Watts",
    )
    recommended_psu_watts: Optional[int] = Field(
        default=None,
        ge=200,
        le=2000,
        description="Recommended PSU wattage (e.g., 550, 650, 750) from Vietnamese retail spec tables",
    )
    length_mm: Optional[int] = Field(
        default=None,
        ge=100,
        le=500,
        description="Physical card length in millimeters",
    )
    slot_width: Optional[float] = Field(
        default=None,
        ge=1.0,
        le=5.0,
        description="Expansion slot width (e.g., 2.0, 2.5, 3.0)",
    )
    power_connectors: Optional[str] = Field(
        default=None,
        description="Normalized power connector requirement (e.g., '1x 8-pin', '1x 16-pin (12VHPWR)')",
    )
    raw_specs: Dict[str, str] = Field(
        default_factory=dict,
        description="Preserved raw key-value specification table scraped from product detail page",
    )

    # --- 5. Cross-Site Matching & Audit Metadata ---
    canonical_key: str = Field(
        default="",
        description="Deterministic slug key (brand + gpu_model + vram_gb + series) for cross-site joining",
    )
    model_match_key: str = Field(
        default="",
        description="Broader key (brand + gpu_model + vram_gb) for fallback spec enrichment",
    )
    spec_enriched_from: Optional[str] = Field(
        default=None,
        description="Indicates if missing hardware specs were enriched from another source (e.g., 'buildcores')",
    )
    crawled_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO-8601 UTC timestamp when the record was normalized at source",
    )

    # --- Field Validators ---
    @field_validator("gpu_model", mode="after")
    def validate_gpu_model(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned or cleaned.upper() == "UNKNOWN":
            raise ValueError(
                "gpu_model cannot be empty or UNKNOWN. Non-VGA items must be filtered out."
            )
        return cleaned

    @field_validator("vram_gb", mode="after")
    def validate_vram_gb(cls, v: int) -> int:
        if v not in VALID_VRAM_SIZES:
            raise ValueError(
                f"Invalid vram_gb={v}GB. Must be a realistic GPU memory size in {sorted(VALID_VRAM_SIZES)}"
            )
        return v

    @field_validator("url", mode="after")
    def validate_url(cls, v: str) -> str:
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError(f"URL must start with http:// or https://, got '{v}'")
        return v

    @model_validator(mode="after")
    def finalize_computed_fields(self) -> "NormalizedVGASchema":
        # 1. Normalize original_price_vnd & calculate discount_percent
        if self.price_vnd is not None and self.price_vnd == 0:
            self.price_vnd = None
        if self.original_price_vnd is not None and self.original_price_vnd == 0:
            self.original_price_vnd = None

        if self.price_vnd is not None and self.original_price_vnd is not None:
            if self.original_price_vnd > self.price_vnd:
                disc = ((self.original_price_vnd - self.price_vnd) / self.original_price_vnd) * 100.0
                self.discount_percent = round(disc, 2)
            else:
                self.original_price_vnd = self.price_vnd
                self.discount_percent = 0.0

        # 2. Auto-infer stock status if price is missing vs present
        if self.stock_status == StockStatus.UNKNOWN:
            if self.source != SourceSite.BUILDCORES:
                self.stock_status = (
                    StockStatus.IN_STOCK if self.price_vnd is not None else StockStatus.CONTACT
                )

        # 3. Generate clean normalized_name if not explicitly set
        if not self.normalized_name:
            parts = [self.brand.value if isinstance(self.brand, Enum) else str(self.brand)]
            if self.series:
                parts.append(self.series)
            chip_prefix = ""
            chip_mfr = (
                self.chip_manufacturer.value
                if isinstance(self.chip_manufacturer, Enum)
                else str(self.chip_manufacturer)
            )
            if chip_mfr == "NVIDIA" and not self.gpu_model.startswith(("GeForce", "RTX", "GTX", "GT")):
                chip_prefix = "GeForce "
            elif chip_mfr == "AMD" and not self.gpu_model.startswith("Radeon"):
                chip_prefix = "Radeon "
            elif chip_mfr == "INTEL" and not self.gpu_model.startswith("Arc"):
                chip_prefix = "Arc "
            parts.append(f"{chip_prefix}{self.gpu_model}".strip())
            if self.is_oc:
                parts.append("OC")
            parts.append(f"{self.vram_gb}GB")
            v_type = (
                self.vram_type.value
                if isinstance(self.vram_type, Enum)
                else str(self.vram_type)
            )
            if v_type != "UNKNOWN":
                parts.append(v_type)
            self.normalized_name = " ".join(parts)

        # 4. Compute deterministic cross-site matching keys
        brand_slug = _slugify(
            self.brand.value if isinstance(self.brand, Enum) else str(self.brand)
        )
        gpu_slug = _slugify(self.gpu_model)
        series_slug = _slugify(self.series or "standard")
        self.model_match_key = f"{brand_slug}_{gpu_slug}_{self.vram_gb}gb"
        self.canonical_key = f"{brand_slug}_{gpu_slug}_{self.vram_gb}gb_{series_slug}"
        return self


class DeadLetterRecord(BaseModel):
    """
    Captures raw items rejected by Schema-First validation or domain filtering
    so broken or non-VGA items never pollute the normalized storage.
    """

    source: str
    raw_identifier: str
    raw_title: str
    reason: str
    raw_payload: Dict[str, Any] = Field(default_factory=dict)
    rejected_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
