from datetime import datetime
import time
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from utils import get_driver, save_data_to_files

def get_all_product_links(driver, url):
    print(f"\n[BƯỚC 1] ĐANG QUÉT LINK TỪ DANH MỤC: {url}")
    driver.get(url)
    time.sleep(3)

    product_links = set()
    page_count = 1

    while True:
        print(f" -> Đang quét link sản phẩm ở Trang {page_count}...")

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        links_in_page = 0

        product_items = soup.find_all('div', class_='p-item')

        for item in product_items:
            a_tag = item.find('a', href=True)

            if a_tag:
                href = a_tag['href']
                full_url = href if href.startswith('http') else "https://philong.com.vn" + href

                if "philong.com.vn" in full_url:
                    product_links.add(full_url)
                    links_in_page += 1

        print(f"    + Thu thập được {links_in_page} link sản phẩm CHUẨN ở trang {page_count}.")

        try:
            xpath_next_btn = "//div[@class='paging']//a[contains(translate(text(), 'NEXT', 'next'), 'next')]"
            next_btn = driver.find_element(By.XPATH, xpath_next_btn)

            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_btn)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", next_btn)

            page_count += 1
            time.sleep(3)

        except NoSuchElementException:
            print(" -> Không tìm thấy nút 'Next'. Đã duyệt đến trang cuối cùng!")
            break
        except Exception as e:
            print(f" -> [Cảnh báo] Dừng chuyển trang do lỗi: {e}")
            break

    print(f"==> KẾT QUẢ BƯỚC 1: Lọc được tổng cộng {len(product_links)} link sản phẩm duy nhất.\n")
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

        h1 = soup_init.find('h1')
        if h1:
            product_data['Tên sản phẩm'] = h1.get_text(strip=True)

        price_container = soup_init.find('span', class_=lambda x: x and 'p-price' in x)
        if price_container:
            actual_price_span = price_container.find('span')
            if actual_price_span: 
                product_data['Giá hiện tại'] = actual_price_span.get_text(strip=True)
            else: 
                product_data['Giá hiện tại'] = price_container.get_text(strip=True)

        if "Liên hệ" in soup_init.get_text() or "Hết hàng" in soup_init.get_text():
            product_data['Tình trạng'] = "Có thể hết hàng (Liên hệ)"

        try:
            driver.execute_script("window.scrollBy(0, 1000);")
            time.sleep(1.5)

            xpath_spec_btn = "//a[contains(@class, 'show-m') and contains(text(), 'XEM ĐẦY ĐỦ THÔNG SỐ')]"

            show_specs_btn = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, xpath_spec_btn))
            )

            print(f"    -> Đã tìm thấy nút Popup. Đang click...")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", show_specs_btn)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", show_specs_btn)

            time.sleep(2)  
        except TimeoutException:
            print("    -> [Thông báo] Sản phẩm này không có nút mở bảng thông số chi tiết.")
            pass

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        modal_container = soup.find('div', id='modal')

        if modal_container:
            table = modal_container.find('table')
            if table:
                rows = table.find_all('tr')
                for row in rows:
                    cols = row.find_all('td')

                    if len(cols) >= 2:
                        key = cols[0].get_text(strip=True)
                        val = cols[1].get_text(separator='\n', strip=True)

                        if key and key != ":" and val:
                            product_data[key] = val

    except Exception as e:
        print(f"Lỗi khi cào sản phẩm {url}: {e}")

    return product_data

def crawl():
    category_url = "https://philong.com.vn/card-do-hoa.html"
    print("Đang khởi động trình duyệt Chrome (Headless) cho Phi Long...")
    driver = get_driver(headless=True)
    all_products_data = []

    SAVE_INTERVAL = 10

    try:
        product_urls = get_all_product_links(driver, category_url)

        if not product_urls:
            print("Không tìm thấy link sản phẩm nào. Vui lòng kiểm tra lại mạng hoặc URL!")
            return []

        print("\n" + "="*50)
        print(f"[BƯỚC 2] BẮT ĐẦU VÀO TỪNG TRANG ĐỂ CÀO CHI TIẾT ({len(product_urls)} SP)")
        print("="*50 + "\n")

        for idx, url in enumerate(product_urls, 1):
            print(f"[{idx}/{len(product_urls)}] Đang cào: {url}")
            data = scrape_product_detail(driver, url)
            all_products_data.append(data)

            if idx % SAVE_INTERVAL == 0:
                save_data_to_files(all_products_data, "philong_final")

            time.sleep(1.5)

    except KeyboardInterrupt:
        print("\n[!] Người dùng chủ động dừng chương trình (Ctrl + C)!")
    except Exception as e:
        print(f"\n[!] Có lỗi bất ngờ xảy ra: {e}")
    finally:
        print("\nĐang đóng trình duyệt...")
        driver.quit()

        if all_products_data:
            print("\nĐang lưu lại dữ liệu lần cuối...")
            save_data_to_files(all_products_data, "philong_final")
            print(f"🎉 HOÀN TẤT DỰ ÁN! Tổng cộng {len(all_products_data)} sản phẩm đã được trích xuất thành công.")
        else:
            print("Chưa có dữ liệu nào được thu thập.")
            
    return all_products_data