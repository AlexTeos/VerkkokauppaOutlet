import sqlite3
from pathlib import Path


class DB:
    def __init__(self, logger):
        self.logger = logger
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
                            'item_id INTEGER PRIMARY KEY, '
                            'user_id INTEGER, '
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

    def insert_user(self, user_id):
        req = f'INSERT INTO users (id) VALUES(\'{user_id}\')'
        self._execute(req)

    def mark_as_sold(self, item_id):
        req = f'UPDATE items SET sold = 1, last_check = CURRENT_TIMESTAMP WHERE id = {item_id}'
        self._execute(req)

    def user_exist(self, id):
        return len(self.cursor.execute(f'SELECT * FROM users WHERE users.id = {id}').fetchall()) != 0

    def insert_item(self, user_id, vk_id, caption, price):
        if not self.user_exist(user_id):
            self.insert_user(user_id)
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

    def get_users_per_item(self, item_id):
        return self.cursor.execute(f'SELECT * FROM users_to_items WHERE users_to_items.item_id = {item_id}').fetchall()
