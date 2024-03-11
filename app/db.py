import sqlite3
from pathlib import Path

class DB:
    def __init__(self):
        db_file = Path('vk.sqlite')
        db_exist = db_file.exists()
        self.connection = sqlite3.connect('vk.sqlite')
        self.cursor = self.connection.cursor()
        if not db_exist:
            self._init_db()

    def _init_db(self):
        self.cursor.execute('CREATE TABLE users('
                            'id INTEGER PRIMARY KEY, '
                            'disabled BOOLEAN DEFAULT FALSE'
                            ')')

        self.cursor.execute('CREATE TABLE items('
                            'id INTEGER PRIMARY KEY, '
                            'caption, '
                            'last_price INTEGER, '
                            'last_check TIMESTAMP DEFAULT CURRENT_TIMESTAMP, '
                            'last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP, '
                            'sold BOOLEAN DEFAULT FALSE'
                            ')')

        self.cursor.execute('CREATE TABLE users_to_items('
                            'id INTEGER PRIMARY KEY, '
                            'user_id INTEGER, '
                            'item_id INTEGER, '
                            'FOREIGN KEY(user_id) REFERENCES users(id), '
                            'FOREIGN KEY(item_id) REFERENCES items(id)'
                            ')')

        self.cursor.execute('CREATE TABLE events('
                            'id INTEGER PRIMARY KEY, '
                            'item_id INTEGER, '
                            'ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP, '
                            'percent INTEGER, '
                            'sale_price INTEGER, '
                            'full_price INTEGER, '
                            'FOREIGN KEY(item_id) REFERENCES items(id)'
                            ')')

        self._test_data()

    def insert_user(self, user_id):
        req = f'INSERT INTO users (id) VALUES(\'{user_id}\')'
        self._execute(req)

    def mark_as_sold(self, item_id):
        req = f'UPDATE items SET sold = 1, last_check = CURRENT_TIMESTAMP WHERE id = {item_id}'
        self._execute(req)

    def insert_item(self, user_id, vk_id, caption, price):
        req = f'INSERT INTO items (id, caption, last_price) VALUES({vk_id}, \'{caption}\', {price})'
        self._execute(req)
        self._insert_user_to_item(user_id, vk_id)

    def _insert_user_to_item(self, user_id, vk_id):
        req = f'INSERT INTO users_to_items (user_id, item_id) VALUES({user_id}, {vk_id})'
        self._execute(req)

    def insert_event(self, item_id, percent, sale_price, full_price):
        ins_req = f'INSERT INTO events (item_id, percent, sale_price, full_price) VALUES({item_id}, ' \
              f'{percent}, {sale_price}, {full_price})'
        self._execute(ins_req)
        upd_req = (f'UPDATE items SET last_price = {sale_price}, last_check = CURRENT_TIMESTAMP, '
                   f'last_update = CURRENT_TIMESTAMP WHERE id = {item_id}')
        self._execute(upd_req)

    def _test_data(self):
        self.insert_user(345345)
        self.insert_item(345345, 1212745, 'AirPatrol Nordic V2', 92)
        self.insert_event(1212745, 54, 92, 199)
        self.insert_event(1212745, 56, 68, 199)
        self.insert_event(1212745, 58, 80, 199)
        self.insert_user(5674)
        self.insert_item(5674, 1212340, 'Ortofon 2M-78 MM', 46)
        self.insert_event(1212340, 69, 46, 149)
        self.insert_event(1212340, 72, 40, 149)
        self.insert_item(5674, 1216730, 'Sold item', 46)
        self.insert_event(1216730, 69, 46, 149)
        self.insert_event(1216730, 72, 40, 149)
    def _execute(self, request):
        print(request)
        self.cursor.execute(request)
        self.connection.commit()

    def get_items(self):
        return self.cursor.execute('SELECT * FROM items').fetchall()

    def get_unsold_items(self, time_offset):
        days_offset = time_offset / 86400.0
        return self.cursor.execute(f'SELECT * FROM items WHERE items.sold = 0 AND '
                                   f'JULIANDAY(CURRENT_TIMESTAMP) - JULIANDAY(items.last_check) > {days_offset}').fetchall()

    def item_checked(self, item_id):
        req = f'UPDATE items SET last_check = CURRENT_TIMESTAMP WHERE id = {item_id}'
        self._execute(req)
