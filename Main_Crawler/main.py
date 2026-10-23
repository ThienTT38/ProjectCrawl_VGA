import os
import sys

# Đảm bảo có thể import các module bên trong
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sites import SITES

def show_menu():
    print("\n" + "="*40)
    print("🖥️  HỆ THỐNG CRAWL DATA VGA CHUYÊN NGHIỆP 🖥️")
    print("="*40)
    # Tự động in từ [1] đến [5] chuẩn xác theo từ điển SITES
    for key, (name, _) in SITES.items():
        print(f"  [{key}]. Cào dữ liệu {name}")
    print("  [6]. Cào TẤT CẢ các trang (Chạy tự động liên tục)")
    print("  [0]. Thoát")
    print("="*40)

if __name__ == "__main__":
    while True:
        show_menu()
        choice = input("Nhập lựa chọn của bạn: ").strip()

        if choice == '0':
            print("Đang thoát chương trình. Tạm biệt!")
            break
            
        elif choice == '6':  # Đổi thành '6' để đúng với menu Cào tất cả
            print("\n🚀 KÍCH HOẠT CHẾ ĐỘ CÀO TẤT CẢ...")
            all_sites_data = {}
            for key, (name, crawl_func) in SITES.items():
                print(f"\n--- Đang bắt đầu với {name} ---")
                try:
                    all_sites_data[name] = crawl_func()
                except Exception as e:
                    print(f"Lỗi khi chạy {name}: {e}")
            print("\n🎉 ĐÃ CÀO XONG TOÀN BỘ HỆ THỐNG!")
            break
            
        elif choice in SITES:  # Nhập 1, 2, 3, 4, 5 sẽ tự động chạy đúng trang tương ứng
            name, crawl_func = SITES[choice]
            print(f"\n🚀 Đang chạy script cho: {name}...")
            crawl_func()
            
        else:
            print("Lựa chọn không hợp lệ, vui lòng nhập lại!")