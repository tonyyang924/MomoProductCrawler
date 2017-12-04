import os
import re
import time
import json
import urllib.request
from pymongo import MongoClient
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
    with open('catchimg3.json', encoding='utf8') as data_file:
        data = json.load(data_file)
    bigkey = data['bigkey']

    arr = []
    for vendor in bigkey:
        arr.append(vendor['keyword'])
    return arr


def crawler_vendor(vendor):
    create_directory(vendor_directory + '/' + vendor)
    trigger_click_page(vendor)


def trigger_click_page(vendor):
    try:
        next_page(vendor, 1)
    except WebDriverException:
        print('『' + vendor + '』找不到下一頁的按鈕。')


def next_page(vendor, page):
    global vendor_max_page

    if page > 1 and page > vendor_max_page:
        print(vendor + '沒有下一頁了')
        return

    driver.get('https://www.momoshop.com.tw/search/searchShop.jsp?keyword=' + vendor + '&curPage=' + str(page))
    time.sleep(2.5)

    if page == 1:
        elements = driver.find_elements_by_xpath("//div[@class='pageArea']/ul/li/a")
        vendor_max_page = int(elements[-1].get_attribute('pageidx'))
        print("﹝%s﹞總共有 %d 頁" % (vendor, vendor_max_page))

    print('=====' + vendor + '==========開始爬第' + str(page) + '頁==========')

    directory = vendor_directory + '/' + vendor

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    list_area = soup.find('div', {'class': 'listArea'}).find('ul')
    for item_li in list_area.select('li'):
        item = item_li.select_one('a.goodsUrl')
        # 產品編號
        the_id = item_li['gcode']
        # 產品網址
        # url = momo_url + item['href']
        # 產品大圖網址，置換小的圖片網址為大的
        little_image_url = item.find('img')['src']
        image_url = little_image_url.replace('L.jpg', 'B.jpg')
        # 產品名稱
        name = item.find('p', {'class': 'prdName'}).text
        # 產品Slogan
        # slogan = item.find('p', {'class': 'sloganTitle'}).text
        # 產品價格
        money_text = item.find('p', {'class': 'money'}).text
        # money = get_number(money_text)
        # print(url, image_url, name, slogan, money)

        filename = vendor + '_' + re.sub(pattern, "", name) + '_' + the_id + '.jpg'
        filepath = directory + '/' + filename
        try:
            urllib.request.urlretrieve(image_url, filepath)
            print(filename, image_url)
        except (urllib.request.HTTPError, urllib.request.URLError, urllib.request.ContentTooShortError, ValueError):
            try:
                urllib.request.urlretrieve(little_image_url, filepath)
                print(filename, little_image_url)
            except (urllib.request.HTTPError, urllib.request.URLError, urllib.request.ContentTooShortError, ValueError):
                image.save(filepath, "PNG")
                print(filename, 'empty image')

        # save db
        table_vendor.insert_one({
            "vendor": vendor,
            "img_id": the_id,
            "ch_name": name,
        })

    next_page(vendor, page + 1)


# MonGo DB
client = MongoClient()
db = client.surpass
table_vendor = db.vendor

driver = webdriver.Chrome()
momo_url = 'https://www.momoshop.com.tw'
pattern = "[-`~!@#$^&*()=|{}':;',\\[\\].<>/?~！@#￥……&*（）&;|{}【】‘；：”“'。，、？+ ]"
image = Image.new('RGB', (1, 1), (255, 255, 255))

result_directory = 'result'
create_directory(result_directory)
vendor_directory = result_directory + '/vendor'
create_directory(vendor_directory)

vendor_max_page = 0

vendors = load_vendors()
for vendor in vendors:
    crawler_vendor(vendor)

driver.quit()
