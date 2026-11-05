"""
Storage & Multi-Format Exporter (`StorageManager`).
Persists `NormalizedVGASchema` records and `DeadLetterRecord` items into:
  1. SQLite relational database (`vga_catalog.db`) with upserts and indexes
  2. Normalized JSON (`vga_normalized.json`) & Cross-site Price Comparison JSON (`vga_price_comparison.json`)
  3. Excel-friendly UTF-8-SIG CSV (`vga_normalized.csv`)
"""

from __future__ import annotations

import csv
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any, Dict, List, Optional

from schemas.vga_schema import DeadLetterRecord, NormalizedVGASchema


CSV_COLUMNS = [
    "source",
    "sku",
    "mpn",
    "normalized_name",
    "raw_name",
    "chip_manufacturer",
    "gpu_model",
    "brand",
    "series",
    "is_oc",
    "vram_gb",
    "vram_type",
    "fan_count",
    "price_vnd",
    "original_price_vnd",
    "discount_percent",
    "price_usd",
    "stock_status",
    "warranty_months",
    "boost_clock_mhz",
    "tdp_watts",
    "recommended_psu_watts",
    "length_mm",
    "slot_width",
    "power_connectors",
    "canonical_key",
    "spec_enriched_from",
    "url",
    "image_url",
    "crawled_at",
]


class StorageManager:
    """Handles SQLite persistence, JSON exports, and CSV exports."""

    def __init__(self, output_dir: str | Path = "output") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.output_dir / "vga_catalog.db"
        self._init_sqlite()

    def _init_sqlite(self) -> None:
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS vga_products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    sku TEXT NOT NULL,
                    mpn TEXT,
                    raw_name TEXT NOT NULL,
                    normalized_name TEXT NOT NULL,
                    url TEXT NOT NULL,
                    image_url TEXT,
                    price_vnd INTEGER,
                    original_price_vnd INTEGER,
                    price_usd REAL,
                    discount_percent REAL,
                    stock_status TEXT NOT NULL,
                    warranty_months INTEGER,
                    chip_manufacturer TEXT NOT NULL,
                    gpu_model TEXT NOT NULL,
                    brand TEXT NOT NULL,
                    series TEXT,
                    is_oc INTEGER NOT NULL DEFAULT 0,
                    vram_gb INTEGER NOT NULL,
                    vram_type TEXT NOT NULL,
                    fan_count INTEGER,
                    boost_clock_mhz INTEGER,
                    tdp_watts INTEGER,
                    length_mm INTEGER,
                    slot_width REAL,
                    power_connectors TEXT,
                    canonical_key TEXT NOT NULL,
                    model_match_key TEXT NOT NULL,
                    spec_enriched_from TEXT,
                    crawled_at TEXT NOT NULL,
                    UNIQUE(source, sku)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_vga_canonical ON vga_products(canonical_key)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_vga_gpu_model ON vga_products(gpu_model)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_vga_brand ON vga_products(brand)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_vga_price ON vga_products(price_vnd)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dead_letter_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    raw_identifier TEXT NOT NULL,
                    raw_title TEXT,
                    reason TEXT NOT NULL,
                    raw_payload_json TEXT NOT NULL,
                    rejected_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def save_all(
        self,
        records: List[NormalizedVGASchema],
        dead_letters: Optional[List[DeadLetterRecord]] = None,
        comparison_groups: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Path]:
        """Persist everything to SQLite, JSON, and CSV and return generated file paths."""
        dead_letters = dead_letters or []
        comparison_groups = comparison_groups or []

        self.save_to_sqlite(records, dead_letters)
        json_path = self.export_json(records, "vga_normalized.json")
        csv_path = self.export_csv(records, "vga_normalized.csv")
        dlq_path = self.export_dead_letters_json(dead_letters, "vga_dead_letters.json")
        comp_path = self.export_comparison_json(
            comparison_groups, "vga_price_comparison.json"
        )

        return {
            "sqlite_db": self.db_path,
            "normalized_json": json_path,
            "normalized_csv": csv_path,
            "dead_letters_json": dlq_path,
            "price_comparison_json": comp_path,
        }

    def save_to_sqlite(
        self,
        records: List[NormalizedVGASchema],
        dead_letters: Optional[List[DeadLetterRecord]] = None,
    ) -> None:
        with closing(sqlite3.connect(self.db_path)) as conn:
            for rec in records:
                d = rec.model_dump(mode="json")
                conn.execute(
                    """
                    INSERT INTO vga_products (
                        source, sku, mpn, raw_name, normalized_name, url, image_url,
                        price_vnd, original_price_vnd, price_usd, discount_percent,
                        stock_status, warranty_months, chip_manufacturer, gpu_model,
                        brand, series, is_oc, vram_gb, vram_type, fan_count,
                        boost_clock_mhz, tdp_watts, length_mm, slot_width,
                        power_connectors, canonical_key, model_match_key,
                        spec_enriched_from, crawled_at
                    ) VALUES (
                        :source, :sku, :mpn, :raw_name, :normalized_name, :url, :image_url,
                        :price_vnd, :original_price_vnd, :price_usd, :discount_percent,
                        :stock_status, :warranty_months, :chip_manufacturer, :gpu_model,
                        :brand, :series, :is_oc, :vram_gb, :vram_type, :fan_count,
                        :boost_clock_mhz, :tdp_watts, :length_mm, :slot_width,
                        :power_connectors, :canonical_key, :model_match_key,
                        :spec_enriched_from, :crawled_at
                    )
                    ON CONFLICT(source, sku) DO UPDATE SET
                        mpn = excluded.mpn,
                        raw_name = excluded.raw_name,
                        normalized_name = excluded.normalized_name,
                        url = excluded.url,
                        image_url = excluded.image_url,
                        price_vnd = excluded.price_vnd,
                        original_price_vnd = excluded.original_price_vnd,
                        price_usd = excluded.price_usd,
                        discount_percent = excluded.discount_percent,
                        stock_status = excluded.stock_status,
                        warranty_months = excluded.warranty_months,
                        chip_manufacturer = excluded.chip_manufacturer,
                        gpu_model = excluded.gpu_model,
                        brand = excluded.brand,
                        series = excluded.series,
                        is_oc = excluded.is_oc,
                        vram_gb = excluded.vram_gb,
                        vram_type = excluded.vram_type,
                        fan_count = excluded.fan_count,
                        boost_clock_mhz = excluded.boost_clock_mhz,
                        tdp_watts = excluded.tdp_watts,
                        length_mm = excluded.length_mm,
                        slot_width = excluded.slot_width,
                        power_connectors = excluded.power_connectors,
                        canonical_key = excluded.canonical_key,
                        model_match_key = excluded.model_match_key,
                        spec_enriched_from = excluded.spec_enriched_from,
                        crawled_at = excluded.crawled_at
                    """,
                    {**d, "is_oc": 1 if d.get("is_oc") else 0},
                )

            if dead_letters:
                for dl in dead_letters:
                    dl_dict = dl.model_dump(mode="json")
                    conn.execute(
                        """
                        INSERT INTO dead_letter_queue (
                            source, raw_identifier, raw_title, reason, raw_payload_json, rejected_at
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            dl_dict["source"],
                            dl_dict["raw_identifier"],
                            dl_dict["raw_title"],
                            dl_dict["reason"],
                            json.dumps(dl_dict["raw_payload"], ensure_ascii=False),
                            dl_dict["rejected_at"],
                        ),
                    )
            conn.commit()

    def export_json(
        self, records: List[NormalizedVGASchema], filename: str = "vga_normalized.json"
    ) -> Path:
        path = self.output_dir / filename
        payload = [r.model_dump(mode="json") for r in records]
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return path

    def export_dead_letters_json(
        self,
        dead_letters: List[DeadLetterRecord],
        filename: str = "vga_dead_letters.json",
    ) -> Path:
        path = self.output_dir / filename
        payload = [d.model_dump(mode="json") for d in dead_letters]
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return path

    def export_comparison_json(
        self,
        comparison_groups: List[Dict[str, Any]],
        filename: str = "vga_price_comparison.json",
    ) -> Path:
        path = self.output_dir / filename
        path.write_text(
            json.dumps(comparison_groups, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    def export_csv(
        self, records: List[NormalizedVGASchema], filename: str = "vga_normalized.csv"
    ) -> Path:
        path = self.output_dir / filename
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
            writer.writeheader()
            for r in records:
                writer.writerow(r.model_dump(mode="json"))
        return path

    def query_sqlite(
        self,
        gpu_model: Optional[str] = None,
        brand: Optional[str] = None,
        source: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Query normalized records from SQLite with optional filters."""
        clauses: List[str] = []
        params: List[Any] = []
        if gpu_model:
            clauses.append("UPPER(gpu_model) = UPPER(?)")
            params.append(gpu_model)
        if brand:
            clauses.append("UPPER(brand) = UPPER(?)")
            params.append(brand)
        if source:
            clauses.append("LOWER(source) = LOWER(?)")
            params.append(source)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"""
            SELECT source, sku, mpn, normalized_name, gpu_model, brand, series,
                   vram_gb, vram_type, fan_count, price_vnd, discount_percent,
                   stock_status, tdp_watts, length_mm, power_connectors,
                   canonical_key, spec_enriched_from, url
            FROM vga_products
            {where_sql}
            ORDER BY gpu_model ASC, COALESCE(price_vnd, 999999999) ASC
        """
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()
            return [dict(row) for row in rows]
