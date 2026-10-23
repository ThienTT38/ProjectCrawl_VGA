from datetime import datetime
import time
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from utils import get_driver, save_data_to_files

def get_all_product_links(driver, start_url):
    print(f"\n[BƯỚC 1] ĐANG QUÉT LINK TỪ DANH MỤC MEGA: {start_url}")

    driver.get(start_url)
    time.sleep(3)

    product_links = set()
    page_count = 1

    while True:
        print(f" -> Đang quét dữ liệu ở Trang {page_count}...")
        soup = BeautifulSoup(driver.page_source, 'html.parser')

        product_items = soup.find_all('div', class_='product-item')
        links_in_page = 0

        for item in product_items:
            a_tag = item.find('a', href=True)
            if a_tag:
                href = a_tag['href']
                full_url = href if href.startswith('http') else "https://mega.com.vn" + href

                if "mega.com.vn" in full_url:
                    product_links.add(full_url)
                    links_in_page += 1

        print(f"    + Thu thập được {links_in_page} link VGA ở trang {page_count}.")

        next_btn = soup.find('a', class_='page-link', string='»')

        if not next_btn:
            next_btn = soup.find('a', rel='next')

        if next_btn and 'href' in next_btn.attrs:
            next_url = next_btn['href']

            full_next_url = next_url if next_url.startswith('http') else "https://mega.com.vn" + next_url

            print(f"    -> Đang chuyển sang trang tiếp theo...")
            driver.get(full_next_url)
            page_count += 1
            time.sleep(3)  
        else:
            print(" -> [Hoàn tất] Không tìm thấy nút 'Next' (»). Đã duyệt đến trang cuối cùng!")
            break

    print(f"==> KẾT QUẢ BƯỚC 1: Lọc được tổng cộng {len(product_links)} link sản phẩm duy nhất.\n")
    return list(product_links)

def scrape_product_detail(driver, url):
    driver.get(url)
    time.sleep(2.5)

    product_data = {
        'Link sản phẩm': url,
        'Tên sản phẩm': '',
        'Giá hiện tại': '',
        'Giá gốc': '',
        'Tình trạng': 'Còn hàng',
        'Thời gian cào': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

    try:
        soup_init = BeautifulSoup(driver.page_source, 'html.parser')

        h1 = soup_init.find('h1')
        if h1:
            product_data['Tên sản phẩm'] = h1.get_text(strip=True)

        price_tag = soup_init.select_one('.price, .p-price, .box-price')
        if price_tag:
            product_data['Giá hiện tại'] = price_tag.get_text(strip=True)

        if "Liên hệ" in soup_init.get_text() or "Hết hàng" in soup_init.get_text():
            product_data['Tình trạng'] = "Có thể hết hàng (Liên hệ)"

        try:
            driver.execute_script("window.scrollBy(0, 700);")
            time.sleep(1.5)

            xpath_btn = "//button[contains(@class, 'btn-view-all') and contains(text(), 'Xem toàn bộ')]"

            show_specs_btn = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, xpath_btn))
            )

            print(f"    -> Đã tìm thấy nút 'Xem toàn bộ'. Đang mở bảng thông số...")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", show_specs_btn)
            time.sleep(0.5)

            driver.execute_script("arguments[0].click();", show_specs_btn)

            time.sleep(1.5) 
        except TimeoutException:
            print("    -> [Thông báo] Bảng thông số đã được mở sẵn hoặc sản phẩm không có nút.")
            pass

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        table = soup.find('table', class_=lambda x: x and 'table-spec' in x)

        if table:
            rows = table.find_all('tr')
            for row in rows:
                cols = row.find_all('td')

                if len(cols) == 2:
                    key = cols[0].get_text(strip=True)
                    val = cols[1].get_text(separator='\n', strip=True)

                    if key and key != ":" and val:
                        product_data[key] = val

    except Exception as e:
        print(f"Lỗi khi cào sản phẩm {url}: {e}")

    return product_data

def crawl():
    category_url = "https://mega.com.vn/card-do-hoa"
    print("Đang khởi động trình duyệt Chrome cho Mega...")
    driver = get_driver()
    all_products_data = []

    SAVE_INTERVAL = 10

    try:
        product_urls = get_all_product_links(driver, category_url)

        if not product_urls:
            print("Không tìm thấy link nào. Vui lòng kiểm tra lại URL hoặc kết nối mạng!")
            return []

        print("\n" + "="*50)
        print(f"[BƯỚC 2] BẮT ĐẦU VÀO TỪNG TRANG ĐỂ CÀO CHI TIẾT ({len(product_urls)} SP)")
        print("="*50 + "\n")

        for idx, url in enumerate(product_urls, 1):
            print(f"[{idx}/{len(product_urls)}] Đang cào: {url}")
            data = scrape_product_detail(driver, url)
            all_products_data.append(data)

            if idx % SAVE_INTERVAL == 0:
                save_data_to_files(all_products_data, "mega_final")

            time.sleep(1)  

    except KeyboardInterrupt:
        print("\n[!] Người dùng chủ động dừng chương trình (Ctrl + C)!")
    except Exception as e:
        print(f"\n[!] Có lỗi bất ngờ xảy ra: {e}")
    finally:
        print("\nĐang đóng trình duyệt...")
        driver.quit()

        if all_products_data:
            print("\nĐang lưu lại dữ liệu lần cuối...")
            save_data_to_files(all_products_data, "mega_final")
            print(f"🎉 HOÀN TẤT DỰ ÁN MEGA! Đã cào thành công {len(all_products_data)} sản phẩm.")
        else:
            print("Chưa có dữ liệu nào được thu thập.")
            
    return all_products_data