from selenium import webdriver
import math
from bs4 import BeautifulSoup
from webdriver_manager.chrome import ChromeDriverManager
from time import sleep


class AccessDeniedError(Exception):
    def __init__(self, message):
        self.message = message


class ParsingError(Exception):
    def __init__(self, message):
        self.message = message


def retry_decorator(retry_attempts=3):
    def decorator(func):
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

    @retry_decorator()
    def get_item_data(self, id):
        self.driver.get(f'https://www.verkkokauppa.com/fi/outlet/yksittaiskappaleet/{id}')
        sleep(1)
        html = self.driver.page_source
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
