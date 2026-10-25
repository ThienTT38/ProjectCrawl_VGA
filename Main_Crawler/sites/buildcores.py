from datetime import datetime
import time
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from utils import get_driver, save_data_to_files

def get_all_product_links(driver, base_url):
    print(f"\n[BƯỚC 1] ĐANG QUÉT DANH SÁCH SẢN PHẨM: {base_url}")
    driver.get(base_url)
    time.sleep(4)  # Chờ Next.js hydrate DOM hoàn tất

    product_links = set()
    page_count = 1

    while True:
        print(f" -> Đang quét trang {page_count}...")
        
        # Chờ container các thẻ part-card hiển thị
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-testid='part-card']"))
            )
        except TimeoutException:
            print(" -> Hết thời gian chờ tải sản phẩm.")
            break

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        cards = soup.find_all('div', attrs={'data-testid': 'part-card'})
        
        new_links = 0
        for card in cards:
            part_id = card.get('data-part-buildcores-id')
            if part_id:
                full_url = f"https://www.buildcores.com/products/GPU/{part_id.strip()}"
                if full_url not in product_links:
                    product_links.add(full_url)
                    new_links += 1

        print(f"    + Thu thập được {new_links} sản phẩm ở trang {page_count}. (Tổng tích lũy: {len(product_links)})")

        # Kiểm tra nút chuyển trang (Next)
        try:
            next_btn = driver.find_element(By.CSS_SELECTOR, "button[data-testid='pagination-next']")
            
            # Kiểm tra nếu nút Next bị disabled (đã đến trang cuối)
            if next_btn.get_attribute("disabled"):
                print(" -> Nút 'Next' đã bị vô hiệu hóa. Đã đến trang cuối cùng!")
                break
                
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_btn)
            time.sleep(0.5)
            driver.execute_script("arguments[0].click();", next_btn)
            
            page_count += 1
            time.sleep(3)  # Chờ trang mới tải xong dữ liệu
            
        except NoSuchElementException:
            print(" -> Không tìm thấy nút Next. Dừng phân trang.")
            break
        except Exception as e:
            print(f" -> Lỗi khi bấm Next: {e}")
            break

    print(f"==> TỔNG CỘNG THU THẬP: {len(product_links)} link sản phẩm.\n")
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
        # Chờ container thông số tải ra
        try:
            WebDriverWait(driver, 8).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-testid='part-details-specs']"))
            )
        except TimeoutException:
            pass

        soup = BeautifulSoup(driver.page_source, 'html.parser')

        # 1. Tên sản phẩm (thẻ h1)
        h1 = soup.find('h1')
        if h1:
            product_data['Tên sản phẩm'] = h1.get_text(strip=True)

        # 2. Giá sản phẩm
        price_tag = soup.find('p', attrs={'data-testid': 'part-details-best-price-value'})
        if price_tag:
            product_data['Giá hiện tại'] = price_tag.get_text(strip=True)

        # 3. Trích xuất toàn bộ bảng thông số
        spec_rows = soup.find_all('div', attrs={'data-part-details-spec-row': 'true'})
        for row in spec_rows:
            label_div = row.find('div', class_=lambda x: x and 'font-medium' in x)
            val_div = row.find('div', class_=lambda x: x and 'wrap-break-word' in x)

            if label_div and val_div:
                key = label_div.get_text(strip=True)
                val = val_div.get_text(separator=' ', strip=True)
                
                # Bỏ qua nếu giá trị là 'Unknown'
                if key and val and val != "Unknown":
                    product_data[key] = val

    except Exception as e:
        print(f"Lỗi khi cào sản phẩm {url}: {e}")

    return product_data

def crawl():
    category_url = "https://www.buildcores.com/products/GPU"
    print("Đang khởi động trình duyệt Chrome (Headless) cho BuildCores...")
    driver = get_driver(headless=True)
    all_products_data = []
    SAVE_INTERVAL = 10

    try:
        product_urls = get_all_product_links(driver, category_url)
        
        if not product_urls:
            print("Không tìm thấy link sản phẩm nào. Kết thúc quá trình!")
            return []

        print("\n" + "=" * 50)
        print(f"BẮT ĐẦU TRÍCH XUẤT CHI TIẾT ({len(product_urls)} SẢN PHẨM)...")
        print("=" * 50 + "\n")

        for idx, url in enumerate(product_urls, 1):
            print(f"[{idx}/{len(product_urls)}] Đang cào: {url}")
            data = scrape_product_detail(driver, url)
            all_products_data.append(data)

            if idx % SAVE_INTERVAL == 0:
                save_data_to_files(all_products_data, "buildcores")

            time.sleep(1)

    except KeyboardInterrupt:
        print("\nNgười dùng chủ động dừng chương trình (Ctrl + C)!")
    except Exception as e:
        print(f"\nCó lỗi bất ngờ xảy ra: {e}")
    finally:
        print("\nĐang đóng trình duyệt...")
        driver.quit()

        if all_products_data:
            print("\nĐang lưu dữ liệu lần cuối...")
            save_data_to_files(all_products_data, "buildcores")
            print(f"HOÀN TẤT! Đã lưu tổng cộng {len(all_products_data)} sản phẩm.")
        else:
            print("Chưa có dữ liệu nào được thu thập.")

    return all_products_data

if __name__ == "__main__":
    crawl()