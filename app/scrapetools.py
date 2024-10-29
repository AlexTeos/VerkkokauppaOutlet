import requests
import json


class AccessDeniedError(Exception):
    def __init__(self, message):
        self.message = message


class ParsingError(Exception):
    def __init__(self, message):
        self.message = message


class ScrapeTools:
    def __init__(self, logger):
        self.logger = logger

    def get_item_data(self, id):
        url = f'https://web-api.service.verkkokauppa.com/outlet/{id}'
        response = requests.get(url)
        sold = response.status_code == 404
        if sold:
            return True, None, None, None, None

        data = json.loads(response.text)
        current_price = data['customerReturnsInfo']['price_with_tax']
        full_price = data['price']['original']
        percent = round(100 - current_price / full_price * 100)
        caption = data['customerReturnsInfo']['product_name']
        return False, current_price, percent, full_price, caption
