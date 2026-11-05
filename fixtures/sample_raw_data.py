"""
Realistic raw HTML & JSON payloads modeled after actual DOM/API structures of:
  1. Phi Long Technology (`philong.com.vn` - Hurasoft HTML)
  2. MEGA Technology (`mega.com.vn` - Hurasoft HTML + SEO slugs)
  3. Phong Vũ (`phongvu.vn` - Teko Discovery JSON)
  4. BuildCores (`buildcores.com` / `buildcores-open-db` - OpenDB GPU JSON)

Includes intentional dirty/non-VGA records (e.g. VGA Holder, Riser Cable, missing GPU model)
to demonstrate Schema-First filtering & Dead-Letter Queue isolation at the source.
"""

from __future__ import annotations

from typing import Any, Dict

from schemas.vga_schema import SourceSite

# 1. PHI LONG TECHNOLOGY (HTML Payload)
PHILONG_SAMPLE_HTML = """
<div class="product-list">
  <!-- Item 1: ASUS Dual RTX 4060 OC 8GB -->
  <div class="p-item" data-id="PL-27415">
    <a class="p-img" href="/card-man-hinh-asus-dual-geforce-rtx-4060-oc-edition-8gb-gddr6.html">
      <img src="/media/product/250-27415-asus-dual-rtx4060-o8g-v2.jpg" alt="ASUS Dual RTX 4060" />
    </a>
    <span class="p-sku">Mã SP: 27415</span>
    <h3 class="p-name">
      <a href="/card-man-hinh-asus-dual-geforce-rtx-4060-oc-edition-8gb-gddr6.html">
        Card màn hình ASUS Dual GeForce RTX 4060 OC Edition 8GB GDDR6 (DUAL-RTX4060-O8G-V2)
      </a>
    </h3>
    <span class="p-price">8.390.000đ</span>
    <span class="p-old-price">8.990.000đ</span>
    <span class="p-status">Còn hàng</span>
    <div class="p-summary">
      - Chipset: NVIDIA GeForce RTX 4060 | - Dung lượng bộ nhớ: 8GB GDDR6 | - Bảo hành: 36 tháng
    </div>
  </div>

  <!-- Item 2: MSI RTX 4070 SUPER 12G VENTUS 2X OC -->
  <div class="p-item" data-id="PL-29102">
    <a class="p-img" href="/vga-msi-geforce-rtx-4070-super-12g-ventus-2x-oc.html">
      <img src="/media/product/250-29102-msi-rtx4070-super-ventus-2x.jpg" alt="MSI RTX 4070 SUPER" />
    </a>
    <span class="p-sku">Mã SP: 29102</span>
    <h3 class="p-name">
      <a href="/vga-msi-geforce-rtx-4070-super-12g-ventus-2x-oc.html">
        VGA MSI GeForce RTX 4070 SUPER 12G VENTUS 2X OC (12GB GDDR6X, 192-bit, HDMI+DP)
      </a>
    </h3>
    <span class="p-price">16.790.000đ</span>
    <span class="p-old-price">17.990.000đ</span>
    <span class="p-status">Sẵn hàng</span>
    <div class="p-summary">
      - Xung nhịp: 2505 MHz | - Kích thước: 242 x 125 x 43 mm | - Bảo hành: 36 tháng
    </div>
  </div>

  <!-- Item 3: Gigabyte Radeon RX 7800 XT Gaming OC 16G -->
  <div class="p-item" data-id="PL-28850">
    <a class="p-img" href="/card-do-hoa-gigabyte-radeon-rx-7800-xt-gaming-oc-16g.html">
      <img src="/media/product/250-28850-giga-rx7800xt-gaming-oc.jpg" alt="Gigabyte RX 7800 XT" />
    </a>
    <h3 class="p-name">
      <a href="/card-do-hoa-gigabyte-radeon-rx-7800-xt-gaming-oc-16g.html">
        Card đồ họa Gigabyte Radeon RX 7800 XT Gaming OC 16G (GV-R78XTGAMING-OC-16GD)
      </a>
    </h3>
    <span class="p-price">14.290.000đ</span>
    <span class="p-old-price">15.490.000đ</span>
    <span class="p-status">Còn hàng</span>
    <div class="p-summary">
      - Tản nhiệt: Windforce 3 Fans | - Bảo hành: 3 năm
    </div>
  </div>

  <!-- Item 4: Colorful iGame RTX 5080 Ultra W OC 16GB GDDR7 -->
  <div class="p-item" data-id="PL-31500">
    <a class="p-img" href="/vga-colorful-igame-geforce-rtx-5080-ultra-w-oc-16gb-v-gddr7.html">
      <img src="/media/product/250-31500-colorful-rtx5080-ultra-w.jpg" alt="Colorful RTX 5080" />
    </a>
    <h3 class="p-name">
      <a href="/vga-colorful-igame-geforce-rtx-5080-ultra-w-oc-16gb-v-gddr7.html">
        VGA Colorful iGame GeForce RTX 5080 Ultra W OC 16GB-V GDDR7
      </a>
    </h3>
    <span class="p-price">33.990.000đ</span>
    <span class="p-old-price">35.990.000đ</span>
    <span class="p-status">Đặt hàng</span>
    <div class="p-summary">
      - Bộ nhớ: 16GB GDDR7 | - Đầu nguồn: 1x 16-pin | - Bảo hành: 36 tháng
    </div>
  </div>

  <!-- Item 5 (DIRTY / NON-VGA ACCESSORY): Giá đỡ VGA mixed in category -->
  <div class="p-item" data-id="PL-99001">
    <a class="p-img" href="/gia-do-vga-cooler-master-elv8-argb.html">
      <img src="/media/product/250-99001-gia-do-vga.jpg" />
    </a>
    <h3 class="p-name">
      <a href="/gia-do-vga-cooler-master-elv8-argb.html">
        Giá đỡ VGA Cooler Master ELV8 ARGB chống xệ card màn hình
      </a>
    </h3>
    <span class="p-price">590.000đ</span>
    <span class="p-status">Còn hàng</span>
  </div>
</div>
"""

# 2. MEGA TECHNOLOGY (HTML Payload)
MEGA_SAMPLE_HTML = """
<div class="product-grid">
  <!-- Item 1: ASUS Dual RTX 4060 OC 8GB (Matches PL-27415, PV-230701234, BC-ASUS4060) -->
  <div class="p-item" data-id="24810">
    <a href="https://mega.com.vn/vga-asus-dual-geforce-rtx-4060-oc-8gb-gddr6-dual-rtx4060-o8g-v2.html">
      <img data-src="https://mega.com.vn/media/product/24810_asus_dual_rtx_4060.jpg" />
    </a>
    <span class="p-code">Mã SP: MEGA24810</span>
    <h3 class="p-name">
      <a href="https://mega.com.vn/vga-asus-dual-geforce-rtx-4060-oc-8gb-gddr6-dual-rtx4060-o8g-v2.html">
        VGA Asus Dual GeForce RTX 4060 OC Edition 8GB GDDR6
      </a>
    </h3>
    <span class="p-price">8.190.000 ₫</span>
    <span class="p-unprice">8.890.000 ₫</span>
    <span class="p-qty">Còn hàng</span>
    <span class="p-warranty">36 Tháng</span>
    <div class="p-summary">Chip đồ họa: GeForce RTX 4060 | Chuẩn bộ nhớ: 8GB GDDR6 | Số quạt: 2 quạt</div>
  </div>

  <!-- Item 2: MSI RTX 4070 SUPER 12G VENTUS 2X OC (Matches PL-29102, PV-240105678, BC-MSI4070S) -->
  <div class="p-item" data-id="26109">
    <a href="https://mega.com.vn/vga-msi-geforce-rtx-4070-super-12g-ventus-2x-oc.html">
      <img data-src="https://mega.com.vn/media/product/26109_msi_rtx4070s_ventus2x.jpg" />
    </a>
    <span class="p-code">Mã SP: MEGA26109</span>
    <h3 class="p-name">
      <a href="https://mega.com.vn/vga-msi-geforce-rtx-4070-super-12g-ventus-2x-oc.html">
        VGA MSI GeForce RTX 4070 SUPER 12G VENTUS 2X OC GDDR6X
      </a>
    </h3>
    <span class="p-price">16.590.000 ₫</span>
    <span class="p-unprice">17.890.000 ₫</span>
    <span class="p-qty">Còn hàng</span>
    <span class="p-warranty">36 Tháng</span>
  </div>

  <!-- Item 3: Gigabyte RX 7800 XT Gaming OC 16GB (Matches PL-28850, PV-231109876, BC-GIGA7800XT) -->
  <div class="p-item" data-id="25904">
    <a href="https://mega.com.vn/vga-gigabyte-radeon-rx-7800-xt-gaming-oc-16gb-gv-r78xtgaming-oc-16gd.html">
      <img data-src="https://mega.com.vn/media/product/25904_giga_rx7800xt.jpg" />
    </a>
    <span class="p-code">Mã SP: MEGA25904</span>
    <h3 class="p-name">
      <a href="https://mega.com.vn/vga-gigabyte-radeon-rx-7800-xt-gaming-oc-16gb-gv-r78xtgaming-oc-16gd.html">
        VGA Gigabyte Radeon RX 7800 XT Gaming OC 16GB GDDR6
      </a>
    </h3>
    <span class="p-price">13.990.000 ₫</span>
    <span class="p-unprice">15.290.000 ₫</span>
    <span class="p-qty">Còn hàng</span>
    <span class="p-warranty">36 Tháng</span>
  </div>

  <!-- Item 4: ASRock Intel Arc B580 Steel Legend 12GB OC -->
  <div class="p-item" data-id="29400">
    <a href="https://mega.com.vn/vga-asrock-intel-arc-b580-steel-legend-12gb-gddr6-oc.html">
      <img data-src="https://mega.com.vn/media/product/29400_asrock_arc_b580.jpg" />
    </a>
    <span class="p-code">Mã SP: MEGA29400</span>
    <h3 class="p-name">
      <a href="https://mega.com.vn/vga-asrock-intel-arc-b580-steel-legend-12gb-gddr6-oc.html">
        VGA ASRock Intel Arc B580 Steel Legend 12GB OC GDDR6 (3 Fans)
      </a>
    </h3>
    <span class="p-price">7.690.000 ₫</span>
    <span class="p-unprice">8.190.000 ₫</span>
    <span class="p-qty">Còn hàng</span>
    <span class="p-warranty">36 Tháng</span>
  </div>

  <!-- Item 5 (DIRTY / NON-VGA ACCESSORY): Dây Riser PCIe -->
  <div class="p-item" data-id="99002">
    <a href="https://mega.com.vn/day-riser-pcie-4-0-x16-cooler-master.html">
      <img data-src="https://mega.com.vn/media/product/99002_riser.jpg" />
    </a>
    <h3 class="p-name">
      <a href="https://mega.com.vn/day-riser-pcie-4-0-x16-cooler-master.html">
        Dây Riser PCIe 4.0 x16 Cooler Master 200mm cho VGA
      </a>
    </h3>
    <span class="p-price">1.150.000 ₫</span>
  </div>
</div>
"""

# 3. PHONG VŨ (Teko Discovery API JSON Payload)
PHONGVU_SAMPLE_JSON: Dict[str, Any] = {
    "code": "SUCCESS",
    "result": {
        "products": [
            {
                "productInfo": {
                    "sku": "230701234",
                    "mpn": "DUAL-RTX4060-O8G-V2",
                    "name": "Card màn hình ASUS Dual GeForce RTX 4060 OC Edition 8GB GDDR6 (DUAL-RTX4060-O8G-V2)",
                    "canonical": "card-man-hinh-asus-dual-geforce-rtx-4060-oc-8gb-gddr6--s230701234",
                    "brand": {"code": "asus", "name": "ASUS"},
                    "imageUrl": "https://lh3.googleusercontent.com/phongvu-asus-dual-rtx4060.webp",
                    "warranty": "36 tháng",
                    "shortDescription": "Chip đồ họa GeForce RTX 4060, 8GB GDDR6, 2 quạt tản nhiệt Axial-tech",
                },
                "prices": {
                    "latestPrice": 8290000,
                    "supplierRetailPrice": 8990000,
                },
                "totalAvailable": 18,
                "attributes": [
                    {"code": "gpu_chipset", "value": "GeForce RTX 4060"},
                    {"code": "vram_gb", "value": 8},
                    {"code": "vram_type", "value": "GDDR6"},
                ],
            },
            {
                "productInfo": {
                    "sku": "240105678",
                    "mpn": "RTX-4070-SUPER-12G-VENTUS-2X-OC",
                    "name": "Card màn hình MSI GeForce RTX 4070 SUPER 12G VENTUS 2X OC 12GB GDDR6X",
                    "canonical": "card-man-hinh-msi-geforce-rtx-4070-super-12g-ventus-2x-oc--s240105678",
                    "brand": {"code": "msi", "name": "MSI"},
                    "imageUrl": "https://lh3.googleusercontent.com/phongvu-msi-rtx4070s-ventus2x.webp",
                    "warranty": "36 tháng",
                },
                "prices": {
                    "latestPrice": 16490000,
                    "supplierRetailPrice": 17990000,
                },
                "totalAvailable": 7,
                "attributes": [
                    {"code": "gpu_chipset", "value": "RTX 4070 SUPER"},
                    {"code": "vram_gb", "value": 12},
                    {"code": "vram_type", "value": "GDDR6X"},
                ],
            },
            {
                "productInfo": {
                    "sku": "231109876",
                    "mpn": "GV-R78XTGAMING-OC-16GD",
                    "name": "Card màn hình GIGABYTE Radeon RX 7800 XT Gaming OC 16GB GDDR6 (GV-R78XTGAMING-OC-16GD)",
                    "canonical": "card-man-hinh-gigabyte-radeon-rx-7800-xt-gaming-oc-16gb--s231109876",
                    "brand": {"code": "gigabyte", "name": "GIGABYTE"},
                    "imageUrl": "https://lh3.googleusercontent.com/phongvu-giga-rx7800xt.webp",
                    "warranty": "36 tháng",
                },
                "prices": {
                    "latestPrice": 14190000,
                    "supplierRetailPrice": 15490000,
                },
                "totalAvailable": 4,
            },
            {
                "productInfo": {
                    "sku": "240208888",
                    "mpn": "ROG-STRIX-RTX4070TIS-O16G-GAMING",
                    "name": "Card màn hình ASUS ROG Strix GeForce RTX 4070 Ti SUPER 16GB GDDR6X OC Edition",
                    "canonical": "card-man-hinh-asus-rog-strix-rtx-4070-ti-super-16gb-oc--s240208888",
                    "brand": {"code": "asus", "name": "ASUS"},
                    "imageUrl": "https://lh3.googleusercontent.com/phongvu-rog-strix-4070tis.webp",
                    "warranty": "36 tháng",
                },
                "prices": {
                    "latestPrice": 26990000,
                    "supplierRetailPrice": 28990000,
                },
                "totalAvailable": 3,
            },
            # Intentional broken/dirty item without valid GPU model to test SchemaValidationError DLQ
            {
                "productInfo": {
                    "sku": "999999999",
                    "name": "Linh kiện máy tính chưa phân loại Model XYZ",
                    "canonical": "linh-kien-chua-phan-loai--s999999999",
                    "brand": {"code": "other", "name": "OTHER"},
                },
                "prices": {"latestPrice": 950000},
                "totalAvailable": 1,
            },
        ]
    },
}

# 4. BUILDCORES (`buildcores-open-db` GPU JSON Payload)
BUILDCORES_SAMPLE_JSON = [
    {
        "opendb_id": "4060dual-bc01-42f2-8b3c-420daad48f11",
        "chipset_manufacturer": "NVIDIA",
        "chipset": "GeForce RTX 4060",
        "core_base_clock": 1830,
        "core_boost_clock": 2535,
        "memory": 8,
        "memory_type": "GDDR6",
        "effective_memory_clock": 17000,
        "memory_bus": 128,
        "tdp": 115,
        "interface": "PCIe 4.0 x8",
        "color": ["BLACK"],
        "length": 227,
        "total_slot_width": 2.5,
        "cooling": "2 Fans",
        "power_connectors": {
            "pcie_6_pin": 0,
            "pcie_8_pin": 1,
            "pcie_12VHPWR": 0,
            "pcie_12V_2x6": 0,
        },
        "metadata": {
            "name": "ASUS Dual GeForce RTX 4060 OC Edition 8GB GDDR6",
            "manufacturer": "ASUS",
            "part_numbers": ["DUAL-RTX4060-O8G-V2", "90YV0JC7-M0NA00"],
            "series": "Dual",
            "variant": "OC Edition",
        },
        "general_product_information": {"msrp_usd": 309.99},
    },
    {
        "opendb_id": "4070sven-bc02-49a1-9c12-98123456abcd",
        "chipset_manufacturer": "NVIDIA",
        "chipset": "GeForce RTX 4070 SUPER",
        "core_base_clock": 1980,
        "core_boost_clock": 2505,
        "memory": 12,
        "memory_type": "GDDR6X",
        "effective_memory_clock": 21000,
        "memory_bus": 192,
        "tdp": 220,
        "interface": "PCIe 4.0 x16",
        "color": ["BLACK", "SILVER"],
        "length": 242,
        "total_slot_width": 2.1,
        "cooling": "2 Fans",
        "power_connectors": {
            "pcie_6_pin": 0,
            "pcie_8_pin": 0,
            "pcie_12VHPWR": 1,
            "pcie_12V_2x6": 0,
        },
        "metadata": {
            "name": "MSI GeForce RTX 4070 SUPER 12G VENTUS 2X OC",
            "manufacturer": "MSI",
            "part_numbers": ["RTX-4070-SUPER-12G-VENTUS-2X-OC", "912-V513-641"],
            "series": "Ventus 2X",
            "variant": "OC",
        },
        "general_product_information": {"msrp_usd": 599.99},
    },
    {
        "opendb_id": "7800xtgm-bc03-48e0-a211-556677889900",
        "chipset_manufacturer": "AMD",
        "chipset": "Radeon RX 7800 XT",
        "core_base_clock": 2124,
        "core_boost_clock": 2565,
        "memory": 16,
        "memory_type": "GDDR6",
        "effective_memory_clock": 19500,
        "memory_bus": 256,
        "tdp": 263,
        "interface": "PCIe 4.0 x16",
        "color": ["BLACK"],
        "length": 302,
        "total_slot_width": 2.8,
        "cooling": "3 Fans",
        "power_connectors": {
            "pcie_6_pin": 0,
            "pcie_8_pin": 2,
            "pcie_12VHPWR": 0,
            "pcie_12V_2x6": 0,
        },
        "metadata": {
            "name": "GIGABYTE Radeon RX 7800 XT Gaming OC 16G",
            "manufacturer": "GIGABYTE",
            "part_numbers": ["GV-R78XTGAMING-OC-16GD"],
            "series": "Gaming OC",
            "variant": "OC",
        },
        "general_product_information": {"msrp_usd": 499.99},
    },
    {
        "opendb_id": "4070tisr-bc04-41c9-b321-112233445566",
        "chipset_manufacturer": "NVIDIA",
        "chipset": "GeForce RTX 4070 Ti SUPER",
        "core_base_clock": 2340,
        "core_boost_clock": 2670,
        "memory": 16,
        "memory_type": "GDDR6X",
        "effective_memory_clock": 21000,
        "memory_bus": 256,
        "tdp": 285,
        "interface": "PCIe 4.0 x16",
        "color": ["BLACK"],
        "length": 336,
        "total_slot_width": 3.15,
        "cooling": "3 Fans",
        "power_connectors": {
            "pcie_6_pin": 0,
            "pcie_8_pin": 0,
            "pcie_12VHPWR": 0,
            "pcie_12V_2x6": 1,
        },
        "metadata": {
            "name": "ASUS ROG Strix GeForce RTX 4070 Ti SUPER 16GB GDDR6X OC Edition",
            "manufacturer": "ASUS",
            "part_numbers": ["ROG-STRIX-RTX4070TIS-O16G-GAMING"],
            "series": "ROG Strix",
            "variant": "OC",
        },
        "general_product_information": {"msrp_usd": 849.99},
    },
    {
        "opendb_id": "b580stlg-bc05-44d8-c456-77889900aabb",
        "chipset_manufacturer": "Intel",
        "chipset": "Arc B580",
        "core_base_clock": 2670,
        "core_boost_clock": 2800,
        "memory": 12,
        "memory_type": "GDDR6",
        "effective_memory_clock": 19000,
        "memory_bus": 192,
        "tdp": 190,
        "interface": "PCIe 4.0 x8",
        "color": ["WHITE"],
        "length": 298,
        "total_slot_width": 2.6,
        "cooling": "3 Fans",
        "power_connectors": {
            "pcie_6_pin": 0,
            "pcie_8_pin": 2,
            "pcie_12VHPWR": 0,
            "pcie_12V_2x6": 0,
        },
        "metadata": {
            "name": "ASRock Intel Arc B580 Steel Legend 12GB OC",
            "manufacturer": "ASRock",
            "part_numbers": ["B580-SL-12GO"],
            "series": "Steel Legend",
            "variant": "OC",
        },
        "general_product_information": {"msrp_usd": 269.99},
    },
]


def get_all_sample_payloads() -> Dict[SourceSite, Any]:
    return {
        SourceSite.PHILONG: PHILONG_SAMPLE_HTML,
        SourceSite.MEGA: MEGA_SAMPLE_HTML,
        SourceSite.PHONGVU: PHONGVU_SAMPLE_JSON,
        SourceSite.BUILDCORES: BUILDCORES_SAMPLE_JSON,
    }
