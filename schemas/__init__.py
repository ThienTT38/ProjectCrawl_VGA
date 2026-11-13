"""Canonical Schema definitions for VGA Schema-First Scraping."""

from schemas.vga_schema import (
    AIBBrand,
    ChipManufacturer,
    DeadLetterRecord,
    NormalizedVGASchema,
    SourceSite,
    StockStatus,
    VRAMType,
)

__all__ = [
    "SourceSite",
    "ChipManufacturer",
    "AIBBrand",
    "VRAMType",
    "StockStatus",
    "NormalizedVGASchema",
    "DeadLetterRecord",
]
