from datetime import datetime
import time
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from utils import get_driver, save_data_to_files

def get_all_product_links(driver, start_url):
    print(f"\n[BƯỚC 1] ĐANG QUÉT LINK TỪ DANH MỤC SP-ONE: {start_url}")

    driver.get(start_url)
    time.sleep(3)

    product_links = set()
    page_count = 1

    while True:
        print(f" -> Đang quét dữ liệu ở Trang {page_count}...")
        soup = BeautifulSoup(driver.page_source, 'html.parser')

        product_items = soup.find_all('li', class_=lambda x: x and 'product' in x)
        links_in_page = 0

        for item in product_items:
            a_tag = item.find('a', class_='woocommerce-LoopProduct-link')
            if a_tag and 'href' in a_tag.attrs:
                href = a_tag['href']

                if "sp-one.vn" in href:
                    product_links.add(href)
                    links_in_page += 1

        print(f"    + Thu thập được {links_in_page} link sản phẩm ở trang {page_count}.")

        next_btn = soup.find('a', class_='next')

        if next_btn and 'href' in next_btn.attrs:
            next_url = next_btn['href']
            print(f"    -> Đang lật sang trang tiếp theo...")
            driver.get(next_url)
            page_count += 1
            time.sleep(3) 
        else:
            print(" -> [Hoàn tất] Đã mất nút 'Next'. Đã duyệt đến trang cuối cùng!")
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

        h1 = soup_init.find('h1', class_='product_title') or soup_init.find('h1')
        if h1:
            product_data['Tên sản phẩm'] = h1.get_text(strip=True)

        price_tag = soup_init.select_one('.summary .price, .product-info .price')
        if not price_tag:
            price_tag = soup_init.find('span', class_='price')

        if price_tag:
            product_data['Giá hiện tại'] = price_tag.get_text(separator=' - ', strip=True)

        if "Liên hệ" in soup_init.get_text() or "Hết hàng" in soup_init.get_text() or "Out of stock" in soup_init.get_text():
            product_data['Tình trạng'] = "Có thể hết hàng (Liên hệ)"

        try:
            driver.execute_script("window.scrollBy(0, 600);")
            time.sleep(1)

            xpath_btn = "//button[@data-target='#product-tskt']"

            show_specs_btn = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, xpath_btn))
            )

            print(f"    -> Đã tìm thấy nút 'Xem thêm'. Đang mở bảng thông số...")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", show_specs_btn)
            time.sleep(0.5)

            driver.execute_script("arguments[0].click();", show_specs_btn)
            time.sleep(1.5)  

        except TimeoutException:
            print("    -> [Thông báo] Bảng đã mở sẵn hoặc sản phẩm không có nút Xem thêm.")
            pass

        soup = BeautifulSoup(driver.page_source, 'html.parser')

        specs_container = soup.find(id='product-tskt') or soup.find('div', class_='woocommerce-product-attributes-item')

        if specs_container:
            tables = specs_container.find_all('table')

            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    th = row.find('th')
                    tds = row.find_all('td')

                    if th and len(tds) >= 1:
                        key = th.get_text(strip=True)
                        val = tds[0].get_text(separator='\n', strip=True)
                    elif len(tds) >= 2:
                        key = tds[0].get_text(strip=True)
                        val = tds[1].get_text(separator='\n', strip=True)
                    else:
                        continue  

                    if key and val:
                        product_data[key] = val

    except Exception as e:
        print(f"Lỗi khi cào sản phẩm {url}: {e}")

    return product_data

def crawl():
    category_url = "https://sp-one.vn/vga-card-man-hinh/"

    print("Đang khởi động trình duyệt Chrome cho SP-One...")
    driver = get_driver()
    all_products_data = []

    SAVE_INTERVAL = 10  

    try:
        product_urls = get_all_product_links(driver, category_url)

        if not product_urls:
            print("Không tìm thấy link nào. Vui lòng kiểm tra lại mạng hoặc URL!")
            return []

        print("\n" + "="*50)
        print(f"[BƯỚC 2] BẮT ĐẦU VÀO TỪNG TRANG ĐỂ CÀO CHI TIẾT ({len(product_urls)} SP)")
        print("="*50 + "\n")

        for idx, url in enumerate(product_urls, 1):
            print(f"[{idx}/{len(product_urls)}] Đang cào: {url}")
            data = scrape_product_detail(driver, url)
            all_products_data.append(data)

            if idx % SAVE_INTERVAL == 0:
                save_data_to_files(all_products_data, "sp_one_final")

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
            save_data_to_files(all_products_data, "sp_one_final")
            print(f"🎉 HOÀN TẤT DỰ ÁN SP-ONE! Đã cào thành công {len(all_products_data)} sản phẩm.")
        else:
            print("Chưa có dữ liệu nào được thu thập.")
            
    return all_products_data