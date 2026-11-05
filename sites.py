"""
Module đăng ký danh sách các nguồn (SITES) cho hệ thống crawl VGA.
Ánh xạ từng lựa chọn menu sang hàm crawl của Adapter tương ứng.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Tuple

from crawl_buildcores import crawl as crawl_buildcores
from crawl_mega import crawl as crawl_mega
from crawl_philong import crawl as crawl_philong
from crawl_phongvu import crawl as crawl_phongvu
from schemas.vga_schema import NormalizedVGASchema

# Cấu trúc: { "Key": ("Tên hiển thị", Hàm_crawl) }
SITES: Dict[str, Tuple[str, Callable[..., List[NormalizedVGASchema]]]] = {
    "1": ("BuildCores (Cơ sở dữ liệu phần cứng)", crawl_buildcores),
    "2": ("MEGA Technology (mega.com.vn)", crawl_mega),
    "3": ("Phi Long Technology (philong.com.vn)", crawl_philong),
    "4": ("Phong Vũ (phongvu.vn)", crawl_phongvu),
}
