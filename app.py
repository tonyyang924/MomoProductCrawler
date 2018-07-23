# -*- coding: utf-8 -*-
# !/usr/bin/python3
import os
import re
import time
import json
import urllib.request
import sys
import logging
import subprocess
import shlex
from pymongo import MongoClient
import pymongo.errors
from PIL import Image
from selenium import webdriver
from bs4 import BeautifulSoup
from enum import Enum
import argparse


class Crawler:

    class MongoDB():

        def __init__(self, dbpath):
            print('使用MongoDB儲存資料')
            Crawler.create_directory(self, dbpath)
            self.mongod = subprocess.Popen(
                shlex.split(
                    "mongod --dbpath {0}".format(os.path.expanduser(dbpath)))
            )
            self.client = MongoClient()
            self.db_mongo = self.client.surpass
            self.table_vendor = self.db_mongo.vendor

        def get_vendor_table(self):
            return self.table_vendor

        def write(self, filter, update):
            try:
                self.table_vendor.find_one_and_update(filter, update, upsert=True)
            except pymongo.errors.ServerSelectionTimeoutError:
                print('ServerSelectionTimeoutError')

        def terminate(self):
            self.mongod.terminate()

    def __init__(self, result_directory, dbtype, dbpath):
        self.result_directory = result_directory
        self.vendor_directory = result_directory + '/vendor'
        self.vendors = self.load_vendors()
        self.momo_host = 'https://www.momoshop.com.tw'
        self.pattern = "[-`~!@#$^&*()=|{}':;',\\[\\].<>/?~！@#￥……&*（）&;|{}【】‘；：”“'。，、？+ ]"
        self.image = Image.new('RGB', (1, 1), (255, 255, 255))
        # 先不使用logger，等確定要追蹤哪些資訊再埋
        # self.init_logger()
        self.init_directories
        self.init_database(dbtype, dbpath)

    def init_database(self, dbtype, dbpath):
        self.dbtype_objects = {'mongo': self.MongoDB}
        if dbtype is not None and dbpath is not None:
            self.db = self.dbtype_objects[dbtype](dbpath)

    def init_logger(self):
        log_filename = "{}/{}.txt".format(self.result_directory, time.time())
        logging.basicConfig(filename=log_filename, level=logging.DEBUG)
        global logger
        logger = logging.getLogger(__name__)

    def init_directories(self):
        self.create_directory(self.result_directory)
        self.create_directory(self.vendor_directory)

    def start(self):
        self.driver = webdriver.Chrome()
        self.delay_second = 5
        self.vendor_max_page = 0
        for vendor in self.vendors:
            self.crawler_vendor(vendor)
        self.driver.quit()
        self.db.terminate()

    def create_directory(self, path):
        if not os.path.exists(path):
            os.makedirs(path)

    @staticmethod
    def get_number(text):
        arr = re.findall('[0-9]+', text)
        str = ''
        for char in arr:
            str += char
        if len(str) > 0:
            return int(str)
        return 0

    @staticmethod
    def load_vendors():
        with open('catchimg3.json', encoding='utf8') as data_file:
            data = json.load(data_file)
        bigkey = data['bigkey']

        arr = []
        for vendor in bigkey:
            arr.append(vendor['keyword'])
        return arr

    def crawler_vendor(self, vendor):
        self.create_directory(self.vendor_directory + '/' + vendor)
        self.next_page(vendor, 1)

    def get_vendor_max_page(self, vendor, page):
        elements = self.driver.find_elements_by_xpath(
            "//div[@class='pageArea']/ul/li/a")
        try:
            self.vendor_max_page = int(elements[-1].get_attribute('pageidx'))
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
            self.get_vendor_max_page(vendor, page)
            print("﹝%s﹞總共有 %d 頁" % (vendor, self.vendor_max_page))

        print('=====' + vendor + '==========開始爬第' + str(page) + '頁==========')

        directory = self.vendor_directory + '/' + vendor

        try:
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        except TypeError as err:
            print(err)
            return

        items = self.get_each_item(soup)
        print("[" + vendor + "] 第 " + str(page) +
              " 頁共有 " + str(len(items)) + " 個")
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
            filename = vendor + '_' + \
                re.sub(self.pattern, "", pro_name) + '_' + pro_id + '.jpg'
            filepath = directory + '/' + filename

            # 先抓大圖再抓小圖，抓不到就存空圖
            try:
                urllib.request.urlretrieve(pro_image_url, filepath)
                print(filename, pro_image_url)
            except (
                    urllib.request.HTTPError, urllib.request.URLError, urllib.request.ContentTooShortError,
                    ValueError) as err:
                try:
                    urllib.request.urlretrieve(pro_little_image_url, filepath)
                    print(filename, pro_little_image_url)
                except (
                        urllib.request.HTTPError, urllib.request.URLError, urllib.request.ContentTooShortError,
                        ValueError) as err:
                    self.image.save(filepath, "PNG")
                    print(filename, 'empty image')

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

    def get_each_item(self, soup):
        list_area = soup.find('div', {'class': 'listArea'}).find('ul')
        return list_area.select('li')


def main():
    parser = argparse.ArgumentParser(
        prog="MomoProductCrawler",
    )
    parser.add_argument(
        "-r", metavar="result_directory", dest="result_directory",
        help="choice a directory to save momo images.",
    )
    parser.add_argument(
        "-d", metavar="database", dest="database",
        help="choice a database which you needs.",
    )
    parser.add_argument(
        "-dbpath", metavar="database_path", dest="database_path",
        help="choice a database dbpath where you save."
    )
    args = parser.parse_args()
    result_directory = args.result_directory
    dbtype = args.database
    dbpath = args.database_path
    crawler = Crawler(result_directory, dbtype, dbpath)
    crawler.start()


if __name__ == "__main__":
    main()
