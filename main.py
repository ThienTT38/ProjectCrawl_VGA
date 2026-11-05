"""
Menu điều khiển chính (CLI) cho Hệ thống Crawl VGA theo kiến trúc Schema-First Scraping.
Nâng cấp từ file main.py cũ:
  - Giữ nguyên giao diện Menu tương tác chọn 1, 2, 3, 4, 5, 0
  - Bổ sung tùy chọn chạy Demo (dữ liệu mẫu không cần mở Chrome)
  - Tích hợp Cross-Enrichment (BuildCores -> Mega / Phi Long / Phong Vũ) khi cào tất cả
  - Hỗ trợ cờ dòng lệnh CLI (args) cho tự động hóa (CI/CD / Task Scheduler)
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any, Dict, List

# Đảm bảo UTF-8 và đường dẫn import
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fixtures.sample_raw_data import get_all_sample_payloads
from pipeline.enricher import VGAEnricher
from pipeline.orchestrator import CrawlPipelineOrchestrator
from schemas.vga_schema import NormalizedVGASchema, SourceSite
from sites import SITES
from storage.exporter import StorageManager


def format_vnd(val: Any) -> str:
    if val is None:
        return "Liên hệ"
    return f"{val:,.0f} đ".replace(",", ".")


def show_menu() -> None:
    print("\n" + "=" * 55)
    print("🖥️   HỆ THỐNG CRAWL DATA VGA CHUYÊN NGHIỆP (SCHEMA-FIRST) 🖥️")
    print("=" * 55)
    for key, (name, _) in SITES.items():
        print(f"  [{key}]. Cào dữ liệu {name}")
    print("  [5]. Cào TẤT CẢ các trang + Tự động làm giàu thông số & Đối chiếu giá")
    print("  [D]. Chạy thử nghiệm nhanh (Demo Mode - Không cần mở Chrome)")
    print("  [0]. Thoát")
    print("=" * 55)


def run_single_site(site_key: str, headless: bool = False, max_pages: int | None = None) -> List[NormalizedVGASchema]:
    if site_key not in SITES:
        print("Lựa chọn không hợp lệ!")
        return []
    name, crawl_func = SITES[site_key]
    print(f"\n🚀 Đang chạy script cho: {name}...")
    try:
        records = crawl_func(headless=headless, max_pages=max_pages)
        print(f"✅ Hoàn tất {name}: {len(records)} sản phẩm hợp lệ đã được chuẩn hóa.")
        return records
    except Exception as exc:
        print(f"❌ Lỗi khi chạy {name}: {exc}")
        return []


def run_all_sites(headless: bool = False, max_pages: int | None = None) -> List[NormalizedVGASchema]:
    print("\n🚀 KÍCH HOẠT CHẾ ĐỘ CÀO TẤT CẢ CÁC TRANG...")
    all_records: List[NormalizedVGASchema] = []

    # Chạy lần lượt từng trang
    for key, (name, crawl_func) in SITES.items():
        print(f"\n--- [BẮT ĐẦU] {name} ---")
        try:
            records = crawl_func(headless=headless, max_pages=max_pages)
            all_records.extend(records)
            print(f"  -> Đã thu thập {len(records)} sản phẩm từ {name}.")
        except Exception as exc:
            print(f"❌ Lỗi khi cào {name}: {exc}")

    if all_records:
        print("\n🔧 Đang tiến hành làm giàu thông số phần cứng chéo (BuildCores -> VN Retailers)...")
        VGAEnricher.enrich_records(all_records)

        print("📊 Đang tổng hợp bảng so sánh giá đa nguồn...")
        comparison = VGAEnricher.build_price_comparison_report(all_records)

        # Lưu trữ tổng hợp
        storage = StorageManager(output_dir="output")
        paths = storage.save_all(records=all_records, comparison_groups=comparison)

        print("\n" + "=" * 65)
        print("🎉 HOÀN TẤT CÀO TOÀN BỘ HỆ THỐNG!")
        print(f"  - Tổng sản phẩm chuẩn hóa: {len(all_records)}")
        print(f"  - SQLite DB                : {paths['sqlite_db']}")
        print(f"  - File CSV tổng hợp        : {paths['normalized_csv']}")
        print(f"  - File JSON tổng hợp       : {paths['normalized_json']}")
        print(f"  - File So sánh giá         : {paths['price_comparison_json']}")
        print("=" * 65)

    return all_records


def run_demo_mode() -> None:
    print("\n🧪 ĐANG CHẠY CHẾ ĐỘ DEMO (Sử dụng dữ liệu thực tế mẫu của cả 4 nguồn)...")
    orchestrator = CrawlPipelineOrchestrator()
    summary = orchestrator.run_from_payloads(get_all_sample_payloads(), enable_enrichment=True)

    storage = StorageManager(output_dir="output")
    paths = storage.save_all(
        records=summary.records,
        dead_letters=summary.dead_letters,
        comparison_groups=summary.comparison_groups,
    )

    print("\n✅ KẾT QUẢ KIỂM THỬ DEMO:")
    print(f"  - Tổng bản ghi hợp lệ : {len(summary.records)}")
    print(f"  - Bản ghi rác bị chặn : {len(summary.dead_letters)}")
    for dl in summary.dead_letters:
        print(f"    * Chặn: [{dl.source.upper()}] '{dl.raw_title}' -> {dl.reason}")
    print(f"  - Đã xuất file tại: {paths['normalized_csv']}")


def parse_cli_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Hệ thống Crawl VGA Schema-First")
    parser.add_argument("--site", choices=["1", "2", "3", "4"], help="Chạy lẻ 1 trang theo số (1: BuildCores, 2: Mega, 3: PhiLong, 4: PhongVu)")
    parser.add_argument("--all", action="store_true", help="Chạy cào tất cả các trang tự động")
    parser.add_argument("--demo", action="store_true", help="Chạy chế độ Demo nhanh không cần Selenium")
    parser.add_argument("--headless", action="store_true", help="Chạy Chrome ở chế độ ẩn (Headless)")
    parser.add_argument("--pages", type=int, default=None, help="Số trang tối đa mỗi site")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_cli_args()

    # Nếu có truyền cờ CLI thì chạy trực tiếp không cần mở menu
    if args.demo:
        run_demo_mode()
    elif args.all:
        run_all_sites(headless=args.headless, max_pages=args.pages)
    elif args.site:
        run_single_site(args.site, headless=args.headless, max_pages=args.pages)
    else:
        # Chế độ tương tác Menu chuẩn theo phong cách file main cũ
        while True:
            show_menu()
            choice = input("Nhập lựa chọn của bạn: ").strip().upper()

            if choice == "0":
                print("Đang thoát chương trình. Tạm biệt!")
                break
            elif choice == "5":
                run_all_sites()
                break
            elif choice == "D":
                run_demo_mode()
            elif choice in SITES:
                run_single_site(choice)
            else:
                print("⚠️ Lựa chọn không hợp lệ, vui lòng nhập lại!")
