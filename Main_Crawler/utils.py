import os
import time
import pandas as pd
from selenium import webdriver

def get_driver(headless=True):
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(options=options)
    time.sleep(2)
    return driver

def save_data_to_files(data_list, site_name, folder="dataset"):
    # Tự động tạo thư mục dataset nếu chưa tồn tại
    os.makedirs(folder, exist_ok=True)
    
    df = pd.DataFrame(data_list)
    excel_file = os.path.join(folder, f"vga_{site_name}_data.xlsx")
    csv_file = os.path.join(folder, f"vga_{site_name}_data.csv")
    
    df.to_excel(excel_file, index=False)
    df.to_csv(csv_file, index=False, encoding="utf-8-sig")
    print(f"   [Auto-Save] Đã lưu {len(data_list)} sản phẩm của {site_name} vào thư mục '{folder}/'.")