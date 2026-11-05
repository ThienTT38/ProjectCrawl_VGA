"""
Multi-Source Crawl Pipeline Orchestrator (`CrawlPipelineOrchestrator`).
Coordinates adapter execution across Philong, Mega, PhongVu, and BuildCores,
enforces Schema-First validation, and triggers cross-source enrichment.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from adapters.base_adapter import AdapterBatchResult, BaseVGAAdapter
from adapters.buildcores_adapter import BuildCoresAdapter
from adapters.mega_adapter import MegaAdapter
from adapters.philong_adapter import PhilongAdapter
from adapters.phongvu_adapter import PhongVuAdapter
from pipeline.enricher import VGAEnricher
from schemas.vga_schema import DeadLetterRecord, NormalizedVGASchema, SourceSite


@dataclass
class PipelineRunSummary:
    """Consolidated output from a multi-source crawl pipeline execution."""

    records: List[NormalizedVGASchema] = field(default_factory=list)
    dead_letters: List[DeadLetterRecord] = field(default_factory=list)
    by_source_stats: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    comparison_groups: List[Dict[str, Any]] = field(default_factory=list)


class CrawlPipelineOrchestrator:
    """
    Registry and runner for all source adapters following the Adapter Pattern.
    """

    def __init__(self, timeout: float = 20.0) -> None:
        self.adapters: Dict[SourceSite, BaseVGAAdapter] = {
            SourceSite.PHILONG: PhilongAdapter(timeout=timeout),
            SourceSite.MEGA: MegaAdapter(timeout=timeout),
            SourceSite.PHONGVU: PhongVuAdapter(timeout=timeout),
            SourceSite.BUILDCORES: BuildCoresAdapter(timeout=timeout),
        }

    def get_adapter(self, source: SourceSite | str) -> BaseVGAAdapter:
        site = SourceSite(source) if isinstance(source, str) else source
        return self.adapters[site]

    def run_from_payloads(
        self,
        payloads_by_source: Dict[SourceSite | str, Any],
        enable_enrichment: bool = True,
    ) -> PipelineRunSummary:
        """
        Execute Schema-First scraping across pre-fetched or fixture payloads for each site.
        """
        summary = PipelineRunSummary()
        for src_key, raw_payload in payloads_by_source.items():
            adapter = self.get_adapter(src_key)
            batch_result = adapter.process_payload(raw_payload)
            self._merge_batch(summary, batch_result)

        if enable_enrichment:
            VGAEnricher.enrich_records(summary.records)

        summary.comparison_groups = VGAEnricher.build_price_comparison_report(
            summary.records
        )
        return summary

    async def run_live(
        self,
        sources: Optional[List[SourceSite | str]] = None,
        max_pages: int = 1,
        enable_enrichment: bool = True,
    ) -> PipelineRunSummary:
        """
        Execute live asynchronous crawling across selected sources concurrently.
        """
        target_sites = (
            [SourceSite(s) if isinstance(s, str) else s for s in sources]
            if sources
            else list(self.adapters.keys())
        )
        summary = PipelineRunSummary()

        tasks = [
            self.adapters[site].crawl_live(max_pages=max_pages) for site in target_sites
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for site, res in zip(target_sites, results):
            if isinstance(res, Exception):
                summary.by_source_stats[site.value] = {
                    "valid_count": 0,
                    "rejected_count": 0,
                    "success_rate": 0.0,
                    "error": str(res),
                }
            else:
                self._merge_batch(summary, res)

        if enable_enrichment:
            VGAEnricher.enrich_records(summary.records)

        summary.comparison_groups = VGAEnricher.build_price_comparison_report(
            summary.records
        )
        return summary

    @staticmethod
    def _merge_batch(
        summary: PipelineRunSummary, batch: AdapterBatchResult
    ) -> None:
        summary.records.extend(batch.valid_records)
        summary.dead_letters.extend(batch.dead_letters)
        summary.by_source_stats[batch.source.value] = {
            "valid_count": len(batch.valid_records),
            "rejected_count": len(batch.dead_letters),
            "total_processed": batch.total_processed,
            "success_rate": batch.success_rate,
        }
