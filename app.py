#!/usr/bin/env python3
import argparse
import json
import logging
import os
import re
import shlex
import subprocess
import time
import urllib.request

import pymongo.errors
from PIL import Image
from bs4 import BeautifulSoup
from pymongo import MongoClient
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains


class DatabaseNotFoundError(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return repr(self.msg)


def get_driver():
    options = webdriver.ChromeOptions()
    options.binary_location = '/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary'
    options.add_argument('headless')
    options.add_argument("disable-gpu")
    options.add_experimental_option(
        "prefs", {'profile.default_content_settings.images': 2})
    return webdriver.Chrome(chrome_options=options)


def create_directory(path):
    if not os.path.exists(path):
        os.makedirs(path)


def get_number(text):
    arr = re.findall('[0-9]+', text)
    number_str = ''
    for char in arr:
        number_str += char
    if len(number_str) > 0:
        return int(number_str)
    return 0


def load_vendors(json_file):
    with open(json_file, encoding='utf8') as data_file:
        data = json.load(data_file)
    big_key = data['bigkey']
    arr = []
    for vendor in big_key:
        arr.append(vendor['keyword'])
    return arr


class MonGoDb:

    def __init__(self, db_path):
        print('使用MongoDB儲存資料')
        create_directory(db_path)
        # noinspection SpellCheckingInspection
        self.mongod = subprocess.Popen(
            shlex.split(
                "mongod --dbpath {0}".format(os.path.expanduser(db_path)))
        )
        self.client = MongoClient()
        # noinspection SpellCheckingInspection
        self.db_mongo = self.client.surpass
        self.table_vendor = self.db_mongo.vendor

    def write(self, filter_condition, update):
        try:
            self.table_vendor.find_one_and_update(
                filter_condition, update, upsert=True)
        except pymongo.errors.ServerSelectionTimeoutError:
            print('ServerSelectionTimeoutError')

    def terminate(self):
        self.mongod.terminate()


class Crawler:
    delay_second = 5
    # noinspection SpellCheckingInspection
    momo_host = 'https://www.momoshop.com.tw'
    pattern = "[-`~!@#$^&*()=|{}':;',\\[\\].<>/?~！@#￥……&*（）&;|{}【】‘；：”“'。，、？+ ]"
    image = Image.new('RGB', (1, 1), (255, 255, 255))

    def __init__(self, result_directory, db_type, db_path):
        self.db_type = db_type
        self.db_path = db_path
        self.driver = None
        self.db = None
        self.vendor_max_page = 0
        self.is_click_precision_brand = False
        self.result_directory = result_directory
        self.vendor_directory = result_directory + '/vendor'
        self.vendors = None
        create_directory(self.result_directory)
        create_directory(self.vendor_directory)

    def get_database(self):
        # noinspection SpellCheckingInspection
        dbtype_objects = {'mongo': MonGoDb}
        if self.db_type is not None and self.db_path is not None:
            return dbtype_objects[self.db_type](self.db_path)
        else:
            raise DatabaseNotFoundError("db_type:{0}, db_path:{1}".format(self.db_type, self.db_path))

    def init_logger(self):
        log_filename = "{}/{}.txt".format(self.result_directory, time.time())
        logging.basicConfig(filename=log_filename, level=logging.DEBUG)
        global logger
        logger = logging.getLogger(__name__)

    def start(self):
        self.db = self.get_database()
        self.driver = get_driver()
        self.vendors = load_vendors('catchimg3.json')
        for vendor in self.vendors:
            self.crawler_vendor(vendor)
        self.driver.quit()
        self.db.terminate()

    def crawler_vendor(self, vendor):
        self.vendor_max_page = 0
        self.is_click_precision_brand = False
        create_directory(self.vendor_directory + '/' + vendor)
        self.next_page(vendor, 1)

    def get_vendor_max_page(self, vendor, page):
        if not self.is_click_precision_brand:
            return
        elements = self.driver.find_elements_by_xpath(
            "//div[@class='pageArea']/ul/li/a")
        try:
            self.vendor_max_page = int(elements[-1].get_attribute('pageidx'))
            print("﹝%s﹞總共有 %d 頁" % (vendor, self.vendor_max_page))
        except IndexError:
            print("「{}」找不到頁數標籤，準備重整頁面並等待10秒...".format(vendor))
            self.driver.refresh()
            time.sleep(10)
            self.get_vendor_max_page(vendor, page)

    def next_page(self, vendor, page):
        if page > 1 and page > self.vendor_max_page:
            print(vendor + '沒有下一頁了')
            return
        self.redirect_to_page(vendor, page)
        self.next_page(vendor, page + 1)

    def redirect_to_page(self, vendor, page):
        self.driver.get(
            'https://www.momoshop.com.tw/search/searchShop.jsp?keyword=' + vendor + '&curPage=' + str(page))
        time.sleep(self.delay_second)

        if page == 1:
            self.click_precision_brand(self.driver.page_source)
            self.get_vendor_max_page(vendor, page)

        print('=====' + vendor + '==========開始爬第' + str(page) + '頁==========')
        directory = self.vendor_directory + '/' + vendor
        soup = self.get_soup(self.driver.page_source)
        items = self.get_each_item(soup)
        print("[" + vendor + "] 第 " + str(page) + " 頁共有 " + str(len(items)) + " 個")
        for item_li in items:
            item = item_li.select_one('a.goodsUrl')

            # 產品編號
            pro_id = item_li['gcode']

            # 產品網址
            pro_url = self.momo_host + item['href']

            # 產品大圖網址，置換小的圖片網址為大的
            pro_little_image_url = item.find('img')['src']
            pro_image_url = pro_little_image_url.replace('L.jpg', 'B.jpg')

            # 產品名稱
            pro_name = item.find('p', {'class': 'prdName'}).text
            file_name = vendor + '_' + re.sub(self.pattern, "", pro_name) + '_' + pro_id + '.jpg'
            file_path = directory + '/' + file_name

            # 先抓大圖再抓小圖，抓不到就存空圖
            try:
                urllib.request.urlretrieve(pro_image_url, file_path)
                print(file_name, pro_image_url)
            except (
                    urllib.request.HTTPError, urllib.request.URLError, urllib.request.ContentTooShortError,
                    ValueError):
                try:
                    urllib.request.urlretrieve(pro_little_image_url, file_path)
                    print(file_name, pro_little_image_url)
                except (
                        urllib.request.HTTPError, urllib.request.URLError, urllib.request.ContentTooShortError,
                        ValueError):
                    self.image.save(file_path, "PNG")
                    print(file_name, 'empty image')

            # 前往商品的詳細頁面
            self.go_detail_page(vendor, pro_id, pro_name, pro_url)

    def go_detail_page(self, vendor, pro_id, pro_name, pro_url):
        # save info to dictionary
        set_dict = {
            "pro_id": pro_id,
            "pro_vendor": vendor,
            "pro_name": pro_name
        }

        # enter to the detail page of this item
        self.driver.get(pro_url)
        time.sleep(self.delay_second)
        try:
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        except TypeError as err:
            print(err)
            return
        bt_category_title = soup.find('div', {'id': 'bt_category_title'})
        if bt_category_title is not None:
            pro_class = bt_category_title.text.strip()
            set_dict['pro_class'] = pro_class

        # save db
        self.db.write({"pro_id": pro_id}, {
            "$set": set_dict,
            "$currentDate": {
                "createtime": True
            }
        })

    def click_precision_brand(self, page_source):
        if self.is_click_precision_brand:
            return

        soup = self.get_soup(page_source)
        items = soup.find('ul', {'class': 'brandsList'}).select('li')
        index = 0
        max_num = 0
        max_num_index = 0
        for item_li in items:
            text = item_li.text
            num = int(re.findall('\d+', text)[0])
            if max_num < num:
                max_num = num
                max_num_index = index
            index = index + 1

        # 取得數量最多的品牌
        max_num_brand = \
            self.driver.find_elements_by_xpath("//tr[@class='goodsBrandTr']//div[@class='wrapDiv']//ul//li")[
                max_num_index]
        # 移動展開更多選擇按鈕
        element_to_hover_over = self.driver.find_element_by_class_name("multipleChoiceBtn")
        actions = ActionChains(self.driver).move_to_element(element_to_hover_over)
        actions.click(max_num_brand)
        actions.perform()
        time.sleep(5)
        self.is_click_precision_brand = True

    @staticmethod
    def get_soup(page_source):
        try:
            return BeautifulSoup(page_source, 'html.parser')
        except TypeError as err:
            print(err)
            return

    @staticmethod
    def get_each_item(soup):
        list_area = soup.find('div', {'class': 'listArea'}).find('ul')
        return list_area.select('li')


def main():
    parser = argparse.ArgumentParser(
        prog="MomoProductCrawler",
    )
    # noinspection SpellCheckingInspection
    parser.add_argument(
        "-r", metavar="result_directory", dest="result_directory",
        help="choice a directory to save momo images.",
    )
    parser.add_argument(
        "-d", metavar="database", dest="database",
        help="choice a database which you needs.",
    )
    # noinspection SpellCheckingInspection
    parser.add_argument(
        "-dbpath", metavar="database_path", dest="database_path",
        help="choice a database dbpath where you save."
    )
    args = parser.parse_args()
    result_directory = args.result_directory
    db_type = args.database
    db_path = args.database_path
    crawler = Crawler(result_directory, db_type, db_path)
    crawler.start()


if __name__ == "__main__":
    main()
