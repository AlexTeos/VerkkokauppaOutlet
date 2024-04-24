from selenium import webdriver
import math
from bs4 import BeautifulSoup
from webdriver_manager.chrome import ChromeDriverManager


class ParsingError(Exception):
    def __init__(self, message):
        self.message = message


class ScrapeTools:
    def __init__(self, logger):
        self.logger = logger
        opts = webdriver.ChromeOptions()
        opts.add_argument('--headless')
        opts.add_argument('--no-sandbox');
        opts.add_argument('--disable-dev-shm-usage');
        self.driver = webdriver.Chrome(ChromeDriverManager().install(), chrome_options=opts)

    def _get_price(self, soup, tag):
        prices = soup.find_all('data', {'data-price': tag})
        try:
            price = prices[-1]['value']
        except IndexError:
            self.logger.error('Failed to extract price')
            raise ParsingError('Failed to extract price')
        price = math.ceil(float(price))
        return price

    def _get_caption(self, soup):
        return soup.find('h1', {'class': True}).string

    def _get_percent(self, soup):
        percents = soup.find_all('span', {'data-discount-percentage': True})
        try:
            percent = percents[0]['data-discount-percentage']
        except IndexError:
            self.logger.error('Failed to extract percent')
            raise ParsingError('Failed to extract percent')
        return percent

    def get_item_data(self, id):
        self.driver.get(f'https://www.verkkokauppa.com/fi/outlet/yksittaiskappaleet/{id}')
        html = self.driver.page_source
        soup = BeautifulSoup(html, 'html.parser')

        sold = int(bool(soup.find_all('div', string='Tämä tuote ei ole enää saatavilla.')))
        if sold:
            return sold, None, None, None, None

        current_price = self._get_price(soup, 'current')
        full_price = self._get_price(soup, 'previous')
        percent = self._get_percent(soup)
        caption = self._get_caption(soup)
        return sold, current_price, percent, full_price, caption
