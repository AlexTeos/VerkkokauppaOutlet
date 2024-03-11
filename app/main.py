from selenium import webdriver
import math
from bs4 import BeautifulSoup
from db import DB
import configparser
from pathlib import Path
from time import sleep
import logging
from logging.handlers import RotatingFileHandler
from telegramtools import TelegramTools

class myClass:
    def setup_logger(self):
        log_file = '/ext/vk.log'
        log_formatter = logging.Formatter('%(asctime)s [%(process)s] {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s')

        is_rotating_handler = RotatingFileHandler(log_file, maxBytes=64 * 1024 * 1024, mode='a', backupCount=1)
        is_rotating_handler.setFormatter(log_formatter)
        is_rotating_handler.setLevel(logging.INFO)

        root_rotating_handler = RotatingFileHandler(log_file, maxBytes=64 * 1024 * 1024, mode='a', backupCount=1)
        root_rotating_handler.setFormatter(log_formatter)
        root_rotating_handler.setLevel(logging.WARNING)

        logging.getLogger('root').setLevel(logging.WARNING)
        logging.getLogger('root').addHandler(root_rotating_handler)

        logging.getLogger('vk').setLevel(logging.INFO)
        logging.getLogger('vk').addHandler(is_rotating_handler)


    def __init__(self):
        self.setup_logger()
        logger = logging.getLogger("vk")

        self.driver = webdriver.Chrome()

        self.db = DB()

        try:
            config_file = Path('/ext/vk.ini')
            if not config_file.is_file():
                config = configparser.ConfigParser()
                config['telegram'] = {'token': '', 'admin': ''}
                with open(config_file, 'w+') as configfile:
                    config.write(configfile)

                logger.info('Config file created:', config_file)
            else:
                config = configparser.ConfigParser()
                config.read(config_file)
                if 'telegram' in config and 'token' in config['telegram'] and 'admin' in config['telegram'] and config['telegram']['token'] != '' and config['telegram']['admin'] != '':
                    logger.info('Start bot with arguments: TGToken - {0} TGAdmin - {1} '.format(config['telegram']['token'], config['telegram']['admin']))
                    tg_tools = TelegramTools(config['telegram']['token'], config['telegram']['admin'])
                    while True:
                        print('new while loop')
                        user_id, item_id = tg_tools.get_update()
                        if item_id:
                            print(item_id)
                            sold, price, _, _ = self.get_item_data(item_id)
                            if not sold:
                                self.db.insert_item(user_id, item_id, str(item_id), price)
                        self.upd()
                        sleep(5)
                else:
                    logger.warning('Config file is incorrect:' + config_file.name)
        except Exception as e:
            logger.critical("Unhandled exception occurred: " + str(e))
            raise

    def get_price(self, soup, tag):
        prices = soup.find_all('data', {'data-price': tag})
        price = prices[-1]['value']
        price = math.ceil(float(price))
        return price

    def get_caption(self):
        pass

    def get_item_data(self, id):
        self.driver.get(f'https://www.verkkokauppa.com/fi/outlet/yksittaiskappaleet/{id}')
        html = self.driver.page_source
        soup = BeautifulSoup(html, 'html.parser')

        current_price = None
        percent = None
        full_price = None
        sold = soup.find_all('div', string='Tämä tuote ei ole enää saatavilla.')
        if sold:
            self.db.mark_as_sold(id)
        else:
            current_price = self.get_price(soup, 'current')

            percents = soup.find_all('span', {'data-discount-percentage': True})
            percent = percents[0]['data-discount-percentage']

            full_price = self.get_price(soup, 'previous')

        return sold, current_price, percent, full_price
    def upd(self, time_offset=2*60*60):
        for id, _, last_price, _, _, _ in self.db.get_unsold_items(time_offset):
            print(f'https://www.verkkokauppa.com/fi/outlet/yksittaiskappaleet/{id}')
            sold, current_price, percent, full_price = self.get_item_data(id)
            if sold:
                self.db.mark_as_sold(id)
            else:
                if current_price != last_price:
                    self.db.insert_event(id, percent, current_price, full_price)
                else:
                    self.db.item_checked(id)


if __name__ == '__main__':
    myClass()