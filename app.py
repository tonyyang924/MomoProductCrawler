import os
import re
import time
import json
import urllib.request
from PIL import Image
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException
from bs4 import BeautifulSoup


def create_directory(path):
    if not os.path.exists(path):
        os.makedirs(path)


def get_number(text):
    arr = re.findall('[0-9]+', text)
    str = ''
    for char in arr:
        str += char
    if len(str) > 0:
        return int(str)
    return 0


def load_vendors():
    with open('catchimg3.json') as data_file:
        data = json.load(data_file)
    bigkey = data['bigkey']

    arr = []
    for vendor in bigkey:
        arr.append(vendor['keyword'])
    return arr


def crawler_vendor(vendor):
    create_directory(root_vendor_directory + '/' + vendor)
    driver.get('https://www.momoshop.com.tw/search/searchShop.jsp?keyword=' + vendor + '&p_lgrpCode=')
    trigger_click_page(vendor)


def trigger_click_page(vendor):
    try:
        next_page(vendor, 1)
    except WebDriverException:
        print('『' + vendor + '』找不到下一頁的按鈕。')


def next_page(vendor, page):
    if page != 1:
        delay = 5
        element = WebDriverWait(driver, delay).until(
            EC.element_to_be_clickable((By.XPATH, '//*[@id="BodyBase"]/div[2]/div[6]/dl/dd/a[text()="下一頁"]')))
        element.click()
        time.sleep(2.5)

    print('=====' + vendor + '==========開始爬第' + str(page) + '頁==========')

    directory = root_vendor_directory + '/' + vendor + '/' + str(page)
    create_directory(directory)

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    list_area = soup.find('div', {'class': 'listArea'}).find('ul')
    for item_li in list_area.select('li'):
        item = item_li.select_one('a.goodsUrl')
        # 產品編號
        the_id = item_li['gcode']
        # 產品網址
        url = momo_url + item['href']
        # 產品大圖網址，置換小的圖片網址為大的
        little_image_url = item.find('img')['src']
        image_url = little_image_url.replace('L.jpg', 'B.jpg')
        # 產品名稱
        name = item.find('p', {'class': 'prdName'}).text
        # 產品Slogan
        slogan = item.find('p', {'class': 'sloganTitle'}).text
        # 產品價格
        money_text = item.find('p', {'class': 'money'}).text
        money = get_number(money_text)
        # print(url, image_url, name, slogan, money)

        filename = vendor + '_' + re.sub(pattern, "", name) + '_' + the_id + '.jpg'
        filepath = directory + '/' + filename
        try:
            urllib.request.urlretrieve(image_url, filepath)
            print(filename, image_url)
        except (urllib.request.HTTPError, urllib.request.URLError, ValueError):
            try:
                urllib.request.urlretrieve(little_image_url, filepath)
                print(filename, little_image_url)
            except (urllib.request.HTTPError, urllib.request.URLError):
                image.save(filepath, "PNG")
                print(filename, 'empty image')
        except urllib.request.ContentTooShortError:
            try:
                urllib.request.urlretrieve(image_url, filepath)
                print(filename, image_url)
            except (urllib.request.HTTPError, urllib.request.URLError):
                try:
                    urllib.request.urlretrieve(little_image_url, filepath)
                    print(filename, little_image_url)
                except (urllib.request.HTTPError, urllib.request.URLError):
                    image.save(filepath, "PNG")
                    print(filename, 'empty image')

    next_page(vendor, page + 1)


driver = webdriver.Chrome()
momo_url = 'https://www.momoshop.com.tw'
pattern = "[-`~!@#$^&*()=|{}':;',\\[\\].<>/?~！@#￥……&*（）&;|{}【】‘；：”“'。，、？+ ]"
image = Image.new('RGB', (1, 1), (255, 255, 255))

# 建立主要的vendor資料夾
root_vendor_directory = 'vendor'
create_directory(root_vendor_directory)

vendors = load_vendors()
for vendor in vendors:
    crawler_vendor(vendor)

driver.quit()
