from datetime import datetime
import time
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from utils import get_driver, save_data_to_files

def get_all_product_links(driver, url):
    print(f"Đang truy cập trang danh mục: {url}")
    driver.get(url)
    time.sleep(5)

    click_count = 0
    max_clicks = 60

    while click_count < max_clicks:
        try:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight - 500);")
            time.sleep(1.5)

            xpath_btn = "//div[contains(text(), 'Xem thêm sản phẩm')] | //*[contains(text(), 'Xem thêm sản phẩm')]"
            btn = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, xpath_btn))
            )

            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", btn)

            click_count += 1
            print(f" -> Đã bấm 'Xem thêm sản phẩm' lần thứ {click_count}")
            time.sleep(2.5)
        except TimeoutException:
            print(" -> Đã tải hết danh sách sản phẩm (không còn nút Xem thêm).")
            break
        except Exception as e:
            print(f" -> Dừng click do: {e}")
            break

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    product_links = set()

    for a in soup.find_all('a', href=True):
        href = a['href']
        href_lower = href.lower()
        if ('vga' in href_lower or 'card-man-hinh' in href_lower) and ('help.phongvu.vn' not in href_lower) and (
                '/cong-nghe/' not in href_lower):
            full_url = href if href.startswith('http') else "https://phongvu.vn" + href
            if "phongvu.vn" in full_url:
                product_links.add(full_url)

    print(f"==> Tổng số link sản phẩm thu thập được: {len(product_links)}\n")
    return list(product_links)

def scrape_product_detail(driver, url):
    driver.get(url)
    time.sleep(3)

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

        # 1. Tên
        h1 = soup_init.find('h1')
        if h1:
            product_data['Tên sản phẩm'] = h1.get_text(strip=True)

        # 2. Giá khuyến mãi
        price_current = soup_init.find('div', class_=lambda x: x and 'css-8a82ns' in x)
        if price_current:
            product_data['Giá hiện tại'] = price_current.get_text(strip=True)

        # 3. Giá gốc
        price_old = soup_init.find('div', class_=lambda x: x and 'css-1lr8xjg' in x)
        if price_old:
            product_data['Giá gốc'] = price_old.get_text(strip=True)

        if "Hết hàng" in soup_init.get_text():
            product_data['Tình trạng'] = "Hết hàng"

        # 4. TÌM VÀ CLICK NÚT "XEM THÊM"
        try:
            xpath_spec_btn = "//div[contains(@class, 'button-text') and contains(text(), 'Xem thêm')]"

            show_specs_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, xpath_spec_btn))
            )
            print("    -> Đã tìm thấy nút 'Xem thêm' cấu hình. Tiến hành click...")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", show_specs_btn)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", show_specs_btn)

            time.sleep(2)
        except TimeoutException:
            print("    -> [Thông báo] Không tìm thấy nút 'Xem thêm' hoặc bảng đã mở sẵn.")
            pass

        # 5. Đọc chi tiết thông số
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        specs_container = soup.find('div', class_=lambda x: x and 'css-ciimlz' in x)

        if specs_container:
            rows = specs_container.find_all('div', class_=lambda x: x and 'css-9zbh2u' in x)
            for row in rows:
                label_tag = row.find('div', class_=lambda x: x and 'css-1kkiml9' in x)
                value_tag = row.find('div', class_=lambda x: x and 'css-prnj7r' in x)

                if label_tag and value_tag:
                    key = label_tag.get_text(strip=True)
                    val = value_tag.get_text(separator='\n', strip=True)
                    product_data[key] = val

    except Exception as e:
        print(f"Lỗi khi cào sản phẩm {url}: {e}")

    return product_data

def crawl():
    category_url = "https://phongvu.vn/c/vga-card-man-hinh"
    print("Đang khởi động trình duyệt Chrome (Headless) cho Phong Vũ...")
    driver = get_driver(headless=True)
    all_products_data = []

    SAVE_INTERVAL = 10

    try:
        product_urls = get_all_product_links(driver, category_url)

        if not product_urls:
            print("Không tìm thấy link sản phẩm nào. Vui lòng kiểm tra lại mạng!")
            return []

        print("\n" + "="*50)
        print("BẮT ĐẦU TRÍCH XUẤT CHI TIẾT SẢN PHẨM PHONG VŨ...")
        print("="*50 + "\n")

        for idx, url in enumerate(product_urls, 1):
            print(f"[{idx}/{len(product_urls)}] Đang cào: {url}")
            data = scrape_product_detail(driver, url)
            all_products_data.append(data)

            if idx % SAVE_INTERVAL == 0:
                save_data_to_files(all_products_data, "phongvu_full")

            time.sleep(1.5)

    except KeyboardInterrupt:
        print("\nNgười dùng chủ động dừng chương trình!")
    except Exception as e:
        print(f"\nCó lỗi bất ngờ xảy ra: {e}")
    finally:
        print("\nĐang đóng trình duyệt...")
        driver.quit()

        if all_products_data:
            print("\nĐang lưu dữ liệu lần cuối...")
            save_data_to_files(all_products_data, "phongvu_full")
            print(f"HOÀN TẤT! Tổng cộng {len(all_products_data)} sản phẩm đã được lưu.")
        else:
            print("Không có dữ liệu nào được thu thập.")
            
    return all_products_data