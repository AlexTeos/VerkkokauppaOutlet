from selenium import webdriver
import math
from bs4 import BeautifulSoup
from webdriver_manager.chrome import ChromeDriverManager
from time import sleep
from functools import wraps


class AccessDeniedError(Exception):
    def __init__(self, message):
        self.message = message


class ParsingError(Exception):
    def __init__(self, message):
        self.message = message


def retry_decorator(retry_attempts=3):
    def decorator(func):
        @wraps(func)
        def wrapped_func(*args, **kwargs):
            for i in range(retry_attempts):
                try:
                    result = func(*args, **kwargs)
                except AccessDeniedError:
                    raise
                except Exception as err:
                    exception = err
                else:
                    return result
            raise exception

        return wrapped_func

    return decorator


class chromeDriver():
    def __init__(self):
        self.opts = webdriver.ChromeOptions()
        self.opts.add_argument('--headless')
        self.opts.add_argument('--no-sandbox');
        self.opts.add_argument('--disable-dev-shm-usage');
        self._start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._stop()

    def _start(self):
        self._driver = webdriver.Chrome(ChromeDriverManager().install(), chrome_options=self.opts)

    def _stop(self):
        self._driver.quit()

    def restart(self):
        self._stop()
        self._start()

    def get(self, page):
        try:
            self._driver.get(page)
        except KeyError:
            self._driver_reset()
            raise
        sleep(1)
        return self.page_source

    @property
    def page_source(self):
        return self._driver.page_source


class ScrapeTools:
    def __init__(self, logger):
        self.logger = logger
        self.driver = chromeDriver()

    def _get_price(self, soup, tag):
        prices = soup.find_all('data', {'data-price': tag})
        try:
            price = prices[-1]['value']
        except IndexError:
            self.logger.error('Failed to extract price')
            raise ParsingError('Failed to extract price')
        price = math.ceil(float(price))
        return price

    @staticmethod
    def _get_caption(soup):
        return soup.find('h1', {'class': True}).string

    @retry_decorator()
    def get_item_data(self, id):
        html = self.driver.get(f'https://www.verkkokauppa.com/fi/outlet/yksittaiskappaleet/{id}')
        soup = BeautifulSoup(html, 'html.parser')

        if bool(soup.find('title', string='Access denied | www.verkkokauppa.com used Cloudflare to restrict access')):
            raise AccessDeniedError()

        sold = int(bool(soup.find_all('div', string='Tämä tuote ei ole enää saatavilla.')))
        if sold:
            return sold, None, None, None, None

        current_price = self._get_price(soup, 'current')
        full_price = self._get_price(soup, 'previous')
        percent = round(100 - current_price / full_price * 100)
        caption = self._get_caption(soup)
        return sold, current_price, percent, full_price, caption
