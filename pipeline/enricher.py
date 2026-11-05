"""
Cross-Source Spec Enrichment & Price Comparison Engine (`VGAEnricher`).
Leverages the shared `NormalizedVGASchema` contract (`mpn`, `canonical_key`, `model_match_key`)
to enrich Vietnamese retailer listings (Phi Long, Mega, Phong Vũ) with granular hardware specs
from BuildCores and generate cross-site price comparison groups.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from schemas.vga_schema import NormalizedVGASchema, SourceSite


class VGAEnricher:
    """
    Matches retail VGA records against BuildCores reference hardware records
    and aggregates cross-store pricing.
    """

    SPEC_FIELDS = (
        "boost_clock_mhz",
        "tdp_watts",
        "length_mm",
        "slot_width",
        "power_connectors",
        "fan_count",
    )

    @classmethod
    def enrich_records(
        cls, records: List[NormalizedVGASchema]
    ) -> List[NormalizedVGASchema]:
        """
        Enrich missing hardware specifications on retail listings (Philong, Mega, PhongVu)
        using reference records from BuildCores via 3-tier matching:
          Tier 1: Exact MPN match (`mpn`)
          Tier 2: Exact Canonical Key match (`brand + gpu_model + vram_gb + series`)
          Tier 3: Model Match Key fallback (`brand + gpu_model + vram_gb` for TDP/power)
        """
        by_mpn: Dict[str, NormalizedVGASchema] = {}
        by_canonical: Dict[str, NormalizedVGASchema] = {}
        by_model: Dict[str, NormalizedVGASchema] = {}

        for rec in records:
            if rec.source == SourceSite.BUILDCORES:
                if rec.mpn:
                    by_mpn[rec.mpn.upper()] = rec
                if rec.canonical_key:
                    by_canonical[rec.canonical_key] = rec
                if rec.model_match_key and rec.model_match_key not in by_model:
                    by_model[rec.model_match_key] = rec

        for rec in records:
            if rec.source == SourceSite.BUILDCORES:
                continue

            # Find best matching BuildCores reference record
            ref: Optional[NormalizedVGASchema] = None
            if rec.mpn and rec.mpn.upper() in by_mpn:
                ref = by_mpn[rec.mpn.upper()]
            elif rec.canonical_key in by_canonical:
                ref = by_canonical[rec.canonical_key]

            if ref is not None:
                enriched_any = False
                for field_name in cls.SPEC_FIELDS:
                    if getattr(rec, field_name) is None and getattr(ref, field_name) is not None:
                        setattr(rec, field_name, getattr(ref, field_name))
                        enriched_any = True
                if not rec.mpn and ref.mpn:
                    rec.mpn = ref.mpn
                if enriched_any:
                    rec.spec_enriched_from = f"buildcores:{ref.sku}"
            elif rec.model_match_key in by_model:
                # Tier 3 fallback: Only copy chip-level TDP & power connector if missing
                fallback_ref = by_model[rec.model_match_key]
                enriched_any = False
                for field_name in ("tdp_watts", "power_connectors"):
                    if (
                        getattr(rec, field_name) is None
                        and getattr(fallback_ref, field_name) is not None
                    ):
                        setattr(rec, field_name, getattr(fallback_ref, field_name))
                        enriched_any = True
                if enriched_any:
                    rec.spec_enriched_from = f"buildcores:{fallback_ref.sku} (chip-level)"

        return records

    @staticmethod
    def build_price_comparison_report(
        records: List[NormalizedVGASchema],
    ) -> List[Dict[str, Any]]:
        """
        Group normalized VGA records by `canonical_key` to compare prices across
        Phi Long, Mega, Phong Vũ, and BuildCores reference specs.
        """
        groups: Dict[str, List[NormalizedVGASchema]] = {}
        for rec in records:
            groups.setdefault(rec.canonical_key, []).append(rec)

        report: List[Dict[str, Any]] = []
        for canonical_key, items in sorted(groups.items()):
            sample = items[0]
            vnd_offers = [
                r for r in items if r.price_vnd is not None and r.source != SourceSite.BUILDCORES
            ]
            vnd_offers.sort(key=lambda x: x.price_vnd or 0)

            lowest_vnd = vnd_offers[0].price_vnd if vnd_offers else None
            highest_vnd = vnd_offers[-1].price_vnd if vnd_offers else None
            best_store = vnd_offers[0].source.value if vnd_offers else None
            spread_vnd = (
                (highest_vnd - lowest_vnd)
                if (lowest_vnd is not None and highest_vnd is not None)
                else 0
            )

            report.append(
                {
                    "canonical_key": canonical_key,
                    "normalized_name": sample.normalized_name,
                    "chip_manufacturer": sample.chip_manufacturer.value,
                    "gpu_model": sample.gpu_model,
                    "brand": sample.brand.value,
                    "series": sample.series,
                    "vram_gb": sample.vram_gb,
                    "vram_type": sample.vram_type.value,
                    "fan_count": sample.fan_count,
                    "tdp_watts": sample.tdp_watts,
                    "length_mm": sample.length_mm,
                    "lowest_price_vnd": lowest_vnd,
                    "highest_price_vnd": highest_vnd,
                    "price_spread_vnd": spread_vnd,
                    "best_price_source": best_store,
                    "sources_count": len({r.source.value for r in items}),
                    "offers": [
                        {
                            "source": r.source.value,
                            "sku": r.sku,
                            "mpn": r.mpn,
                            "price_vnd": r.price_vnd,
                            "original_price_vnd": r.original_price_vnd,
                            "discount_percent": r.discount_percent,
                            "price_usd": r.price_usd,
                            "stock_status": r.stock_status.value,
                            "url": r.url,
                        }
                        for r in items
                    ],
                }
            )

        return report
