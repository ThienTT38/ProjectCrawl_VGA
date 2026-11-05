"""
Unit and Integration Test Suite for the VGA Schema-First Scraping System.
Verifies:
  1. `VGANormalizer` regex extraction across messy Vietnamese & English product titles
  2. `NormalizedVGASchema` strict invariants & computed canonical keys
  3. All 4 Concrete Adapters (`PhilongAdapter`, `MegaAdapter`, `PhongVuAdapter`, `BuildCoresAdapter`)
  4. Non-VGA accessory & broken record isolation into `DeadLetterRecord`
  5. Cross-source spec enrichment (`VGAEnricher`) & SQLite/JSON/CSV persistence (`StorageManager`)
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from adapters.buildcores_adapter import BuildCoresAdapter
from adapters.mega_adapter import MegaAdapter
from adapters.philong_adapter import PhilongAdapter
from adapters.phongvu_adapter import PhongVuAdapter
from core.compat import ValidationError
from fixtures.sample_raw_data import (
    BUILDCORES_SAMPLE_JSON,
    MEGA_SAMPLE_HTML,
    PHILONG_SAMPLE_HTML,
    PHONGVU_SAMPLE_JSON,
    get_all_sample_payloads,
)
from normalizers.vga_normalizer import NonVGAAccessoryError, VGANormalizer
from pipeline.orchestrator import CrawlPipelineOrchestrator
from schemas.vga_schema import (
    AIBBrand,
    ChipManufacturer,
    NormalizedVGASchema,
    SourceSite,
    StockStatus,
    VRAMType,
)
from storage.exporter import StorageManager


class TestVGANormalizer(unittest.TestCase):
    """Test domain normalization rules in `VGANormalizer`."""

    def test_extract_gpu_chipset_variants(self) -> None:
        cases = [
            ("Card màn hình ASUS Dual GeForce RTX 4060 OC Edition 8GB", "RTX 4060"),
            ("VGA MSI GeForce RTX4060Ti GAMING X SLIM 16G", "RTX 4060 Ti"),
            ("Card màn hình ASUS ROG Strix RTX 4070 Ti SUPER 16GB GDDR6X", "RTX 4070 Ti SUPER"),
            ("VGA Colorful iGame GeForce RTX 5080 Ultra W OC 16GB GDDR7", "RTX 5080"),
            ("Card đồ họa Gigabyte Radeon RX 7800 XT Gaming OC 16G", "RX 7800 XT"),
            ("VGA PowerColor Hellhound AMD Radeon RX7900XTX 24GB", "RX 7900 XTX"),
            ("VGA ASRock Intel Arc B580 Steel Legend 12GB OC", "Arc B580"),
        ]
        for raw_title, expected in cases:
            with self.subTest(raw_title=raw_title):
                self.assertEqual(VGANormalizer.extract_gpu_chipset(raw_title), expected)

    def test_non_vga_accessory_guard(self) -> None:
        accessories = [
            "Giá đỡ VGA Cooler Master ELV8 ARGB",
            "Dây Riser PCIe 4.0 x16 Cooler Master cho VGA",
            "Chân đế đỡ VGA Jonsbo VC-20",
        ]
        for title in accessories:
            with self.subTest(title=title):
                with self.assertRaises(NonVGAAccessoryError):
                    VGANormalizer.assert_is_vga_product(title)

    def test_vram_extraction(self) -> None:
        gb, vtype = VGANormalizer.extract_vram(
            "VGA MSI GeForce RTX 4070 SUPER 12G VENTUS 2X OC GDDR6X",
            gpu_model="RTX 4070 SUPER",
        )
        self.assertEqual(gb, 12)
        self.assertEqual(vtype, VRAMType.GDDR6X)

    def test_price_and_warranty_normalization(self) -> None:
        self.assertEqual(VGANormalizer.normalize_price_vnd("8.390.000đ"), 8390000)
        self.assertEqual(VGANormalizer.normalize_price_vnd("16,590,000 ₫"), 16590000)
        self.assertIsNone(VGANormalizer.normalize_price_vnd("Liên hệ"))
        self.assertEqual(VGANormalizer.normalize_warranty_months("36 tháng"), 36)
        self.assertEqual(VGANormalizer.normalize_warranty_months("3 năm"), 36)


class TestAdaptersAndSchemaFirstValidation(unittest.TestCase):
    """Test each of the 4 adapters and verify Schema-First validation & DLQ isolation."""

    def test_philong_adapter_normalizes_and_blocks_accessories(self) -> None:
        adapter = PhilongAdapter()
        batch = adapter.process_payload(PHILONG_SAMPLE_HTML)

        # 4 valid VGAs + 1 rejected 'Giá đỡ VGA' accessory
        self.assertEqual(len(batch.valid_records), 4)
        self.assertEqual(len(batch.dead_letters), 1)
        self.assertIn("NonVGAAccessory", batch.dead_letters[0].reason)

        first = batch.valid_records[0]
        self.assertEqual(first.source, SourceSite.PHILONG)
        self.assertEqual(first.gpu_model, "RTX 4060")
        self.assertEqual(first.brand, AIBBrand.ASUS)
        self.assertEqual(first.series, "Dual")
        self.assertEqual(first.vram_gb, 8)
        self.assertEqual(first.vram_type, VRAMType.GDDR6)
        self.assertEqual(first.mpn, "DUAL-RTX4060-O8G-V2")
        self.assertEqual(first.price_vnd, 8390000)
        self.assertEqual(first.canonical_key, "asus_rtx-4060_8gb_dual")

    def test_mega_adapter_normalizes_and_extracts_slug_mpn(self) -> None:
        adapter = MegaAdapter()
        batch = adapter.process_payload(MEGA_SAMPLE_HTML)

        # 4 valid VGAs + 1 rejected 'Dây Riser PCIe' accessory
        self.assertEqual(len(batch.valid_records), 4)
        self.assertEqual(len(batch.dead_letters), 1)

        first = batch.valid_records[0]
        self.assertEqual(first.source, SourceSite.MEGA)
        self.assertEqual(first.gpu_model, "RTX 4060")
        self.assertEqual(first.mpn, "DUAL-RTX4060-O8G-V2")
        self.assertEqual(first.price_vnd, 8190000)
        self.assertEqual(first.canonical_key, "asus_rtx-4060_8gb_dual")

        # Verify Intel Arc B580 normalization
        arc_rec = batch.valid_records[3]
        self.assertEqual(arc_rec.chip_manufacturer, ChipManufacturer.INTEL)
        self.assertEqual(arc_rec.gpu_model, "Arc B580")
        self.assertEqual(arc_rec.brand, AIBBrand.ASROCK)
        self.assertEqual(arc_rec.series, "Steel Legend")
        self.assertEqual(arc_rec.vram_gb, 12)

    def test_phongvu_adapter_normalizes_and_rejects_missing_gpu(self) -> None:
        adapter = PhongVuAdapter()
        batch = adapter.process_payload(PHONGVU_SAMPLE_JSON)

        # 4 valid VGAs + 1 rejected item missing GPU chipset
        self.assertEqual(len(batch.valid_records), 4)
        self.assertEqual(len(batch.dead_letters), 1)
        self.assertIn("SchemaValidationError", batch.dead_letters[0].reason)

        first = batch.valid_records[0]
        self.assertEqual(first.source, SourceSite.PHONGVU)
        self.assertEqual(first.sku, "PV-230701234")
        self.assertEqual(first.price_vnd, 8290000)
        self.assertEqual(first.canonical_key, "asus_rtx-4060_8gb_dual")

    def test_buildcores_adapter_normalizes_hardware_specs(self) -> None:
        adapter = BuildCoresAdapter()
        batch = adapter.process_payload(BUILDCORES_SAMPLE_JSON)

        self.assertEqual(len(batch.valid_records), 5)
        self.assertEqual(len(batch.dead_letters), 0)

        first = batch.valid_records[0]
        self.assertEqual(first.source, SourceSite.BUILDCORES)
        self.assertEqual(first.gpu_model, "RTX 4060")
        self.assertEqual(first.tdp_watts, 115)
        self.assertEqual(first.length_mm, 227)
        self.assertEqual(first.boost_clock_mhz, 2535)
        self.assertEqual(first.power_connectors, "1x 8-pin")
        self.assertEqual(first.price_usd, 309.99)
        self.assertEqual(first.canonical_key, "asus_rtx-4060_8gb_dual")

    def test_full_pipeline_enrichment_and_storage(self) -> None:
        orchestrator = CrawlPipelineOrchestrator()
        summary = orchestrator.run_from_payloads(
            get_all_sample_payloads(), enable_enrichment=True
        )

        # Total valid = 4 (Philong) + 4 (Mega) + 4 (PhongVu) + 5 (BuildCores) = 17
        self.assertEqual(len(summary.records), 17)
        # Total rejected = 1 (Philong) + 1 (Mega) + 1 (PhongVu) = 3
        self.assertEqual(len(summary.dead_letters), 3)

        # Verify that Philong/Mega/PhongVu ASUS Dual RTX 4060 received TDP=115W & Length=227mm from BuildCores
        philong_4060 = next(
            r
            for r in summary.records
            if r.source == SourceSite.PHILONG and r.gpu_model == "RTX 4060"
        )
        self.assertEqual(philong_4060.tdp_watts, 115)
        self.assertEqual(philong_4060.length_mm, 227)
        self.assertEqual(philong_4060.power_connectors, "1x 8-pin")
        self.assertTrue((philong_4060.spec_enriched_from or "").startswith("buildcores:"))

        # Verify SQLite, JSON, and CSV persistence
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = StorageManager(output_dir=tmpdir)
            paths = storage.save_all(
                records=summary.records,
                dead_letters=summary.dead_letters,
                comparison_groups=summary.comparison_groups,
            )
            for p in paths.values():
                self.assertTrue(Path(p).exists())

            rows = storage.query_sqlite(gpu_model="RTX 4060")
            # 4 sources have ASUS Dual RTX 4060
            self.assertEqual(len(rows), 4)
            # Lowest VND price should be Mega (8,190,000 VND)
            self.assertEqual(rows[0]["source"], "mega")
            self.assertEqual(rows[0]["price_vnd"], 8190000)

    def test_detail_html_parsers_from_legacy_selectors(self) -> None:
        """
        Verify that the exact detail-page DOM selectors from the legacy Selenium scripts
        (`data-part-details-spec-row`, `table-spec`, `div#modal table`, `css-ciimlz`)
        are parsed and normalized into `NormalizedVGASchema` at the source.
        """
        # 1. BuildCores detail HTML (`data-part-details-spec-row='true'`)
        bc_html = """
        <div>
          <h1>ASUS ROG Strix GeForce RTX 4070 Ti SUPER 16GB GDDR6X OC</h1>
          <p data-testid="part-details-best-price-value">$849.99</p>
          <div data-testid="part-details-specs">
            <div data-part-details-spec-row="true">
              <div class="text-sm font-medium">Chipset</div>
              <div class="text-sm wrap-break-word">GeForce RTX 4070 Ti SUPER</div>
            </div>
            <div data-part-details-spec-row="true">
              <div class="text-sm font-medium">Memory</div>
              <div class="text-sm wrap-break-word">16 GB</div>
            </div>
            <div data-part-details-spec-row="true">
              <div class="text-sm font-medium">Memory Type</div>
              <div class="text-sm wrap-break-word">GDDR6X</div>
            </div>
            <div data-part-details-spec-row="true">
              <div class="text-sm font-medium">TDP</div>
              <div class="text-sm wrap-break-word">285 W</div>
            </div>
            <div data-part-details-spec-row="true">
              <div class="text-sm font-medium">Length</div>
              <div class="text-sm wrap-break-word">336 mm</div>
            </div>
          </div>
        </div>
        """
        bc_adapter = BuildCoresAdapter()
        bc_batch = bc_adapter.process_payload(bc_html)
        self.assertEqual(len(bc_batch.valid_records), 1)
        bc_rec = bc_batch.valid_records[0]
        self.assertEqual(bc_rec.gpu_model, "RTX 4070 Ti SUPER")
        self.assertEqual(bc_rec.price_usd, 849.99)
        self.assertEqual(bc_rec.tdp_watts, 285)
        self.assertEqual(bc_rec.length_mm, 336)

        # 2. Mega detail HTML (`table.table-spec`)
        mega_html = """
        <div>
          <h1>VGA MSI GeForce RTX 4060 VENTUS 2X BLACK 8G OC</h1>
          <span class="p-price">7.890.000 đ</span>
          <table class="table table-spec">
            <tr><td>Chip đồ họa</td><td>NVIDIA GeForce RTX 4060</td></tr>
            <tr><td>Dung lượng bộ nhớ</td><td>8GB GDDR6</td></tr>
            <tr><td>Nguồn đề xuất</td><td>550W</td></tr>
            <tr><td>Đầu cấp nguồn</td><td>1x 8-pin</td></tr>
            <tr><td>Kích thước</td><td>199 x 120 x 41 mm</td></tr>
          </table>
        </div>
        """
        mega_adapter = MegaAdapter()
        mega_batch = mega_adapter.process_payload(mega_html)
        self.assertEqual(len(mega_batch.valid_records), 1)
        mega_rec = mega_batch.valid_records[0]
        self.assertEqual(mega_rec.gpu_model, "RTX 4060")
        self.assertEqual(mega_rec.series, "Ventus 2X")
        self.assertEqual(mega_rec.price_vnd, 7890000)
        self.assertEqual(mega_rec.recommended_psu_watts, 550)
        self.assertEqual(mega_rec.length_mm, 199)

        # 3. Phi Long detail HTML (`div#modal table`)
        pl_html = """
        <div>
          <h1>Card màn hình Gigabyte GeForce RTX 4060 Windforce OC 8G</h1>
          <span class="p-price"><span>7.990.000đ</span></span>
          <div id="modal">
            <table>
              <tr><td>Engine đồ họa</td><td>GeForce RTX 4060</td></tr>
              <tr><td>Bộ nhớ</td><td>8GB GDDR6</td></tr>
              <tr><td>Xung nhịp</td><td>2475 MHz</td></tr>
              <tr><td>Công suất nguồn yêu cầu</td><td>450W</td></tr>
            </table>
          </div>
        </div>
        """
        pl_adapter = PhilongAdapter()
        pl_batch = pl_adapter.process_payload(pl_html)
        self.assertEqual(len(pl_batch.valid_records), 1)
        pl_rec = pl_batch.valid_records[0]
        self.assertEqual(pl_rec.gpu_model, "RTX 4060")
        self.assertEqual(pl_rec.brand, AIBBrand.GIGABYTE)
        self.assertEqual(pl_rec.boost_clock_mhz, 2475)
        self.assertEqual(pl_rec.recommended_psu_watts, 450)

        # 4. Phong Vũ detail HTML (`css-8a82ns`, `css-1lr8xjg`, `css-ciimlz` -> `css-9zbh2u`)
        pv_html = """
        <div>
          <h1>Card màn hình ASUS TUF Gaming GeForce RTX 4070 SUPER 12GB GDDR6X OC</h1>
          <div class="css-8a82ns">18.490.000₫</div>
          <div class="css-1lr8xjg">19.990.000₫</div>
          <div class="css-ciimlz">
            <div class="css-9zbh2u">
              <div class="css-1kkiml9">Chip đồ họa</div>
              <div class="css-prnj7r">GeForce RTX 4070 SUPER</div>
            </div>
            <div class="css-9zbh2u">
              <div class="css-1kkiml9">Bộ nhớ</div>
              <div class="css-prnj7r">12GB GDDR6X</div>
            </div>
            <div class="css-9zbh2u">
              <div class="css-1kkiml9">Nguồn đề xuất</div>
              <div class="css-prnj7r">750W</div>
            </div>
          </div>
        </div>
        """
        pv_adapter = PhongVuAdapter()
        pv_batch = pv_adapter.process_payload(pv_html)
        self.assertEqual(len(pv_batch.valid_records), 1)
        pv_rec = pv_batch.valid_records[0]
        self.assertEqual(pv_rec.gpu_model, "RTX 4070 SUPER")
        self.assertEqual(pv_rec.series, "TUF Gaming")
        self.assertEqual(pv_rec.price_vnd, 18490000)
        self.assertEqual(pv_rec.original_price_vnd, 19990000)
        self.assertEqual(pv_rec.recommended_psu_watts, 750)


if __name__ == "__main__":
    unittest.main()
