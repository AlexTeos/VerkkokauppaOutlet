import sqlite3
from pathlib import Path


class UniqueError(Exception):
    pass


class DB:
    def __init__(self, logger):
        self.logger = logger
        db_file = Path('/ext/vk.sqlite')
        db_exist = db_file.exists()
        self.connection = sqlite3.connect('/ext/vk.sqlite')
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
                            'full_price INTEGER, '
                            'last_price INTEGER, '
                            'last_check TIMESTAMP DEFAULT CURRENT_TIMESTAMP, '
                            'last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP, '
                            'sold BOOLEAN DEFAULT FALSE'
                            ')')

        self.cursor.execute('CREATE TABLE users_to_items('
                            'item_id INTEGER, '
                            'user_id INTEGER, '
                            'favorite BOOLEAN DEFAULT FALSE, '
                            'PRIMARY KEY (item_id, user_id), '
                            'FOREIGN KEY(user_id) REFERENCES users(id), '
                            'FOREIGN KEY(item_id) REFERENCES items(id)'
                            ')')

        self.cursor.execute('CREATE TABLE events('
                            'id INTEGER PRIMARY KEY, '
                            'item_id INTEGER, '
                            'ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP, '
                            'percent INTEGER, '
                            'price INTEGER, '
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

    def insert_item(self, user_id, vk_id, caption, full_price, price):
        if not self.user_exist(user_id):
            self.insert_user(user_id)
        req = f'INSERT INTO items (id, caption, full_price, last_price) VALUES({vk_id}, \'{caption}\', {full_price}, {price})'
        try:
            self._execute(req)
        except sqlite3.IntegrityError as err:
            if 'UNIQUE' not in str(err):
                raise
        self.insert_user_to_item(user_id, vk_id)

    def insert_user_to_item(self, user_id, vk_id):
        req = f'INSERT INTO users_to_items (user_id, item_id) VALUES({user_id}, {vk_id})'
        try:
            self._execute(req)
        except sqlite3.IntegrityError as err:
            if 'UNIQUE' not in str(err):
                raise
            raise UniqueError(f'User {user_id} already subscribed to {vk_id}')

    def set_favorite(self, user_id, vk_id, value):
        req = f'UPDATE users_to_items SET favorite = {value} WHERE user_id = {user_id} AND item_id = {vk_id}'
        self._execute(req)

    def insert_event(self, item_id, percent, price):
        ins_req = f'INSERT INTO events (item_id, percent, price) VALUES({item_id}, ' \
                  f'{percent}, {price})'
        self._execute(ins_req)
        upd_req = (f'UPDATE items SET last_price = {price}, last_check = CURRENT_TIMESTAMP, '
                   f'last_update = CURRENT_TIMESTAMP WHERE id = {item_id}')
        self._execute(upd_req)

    def _execute(self, request):
        self.logger.debug(f'Execute {request}')
        self.cursor.execute(request)
        self.connection.commit()

    def get_items(self, caption=None):
        request = 'SELECT * FROM items'
        if caption:
            request += f' WHERE items.caption LIKE \'%{caption}%\''
        return self.cursor.execute(request).fetchall()

    def get_user_items(self, user_id, caption=None, favorites=False):
        request = f'SELECT items.*, users_to_items.favorite FROM users_to_items INNER JOIN items ON users_to_items.item_id = items.id WHERE items.sold = 0 AND user_id = {user_id}'
        if caption:
            request += f' AND items.caption LIKE \'%{caption}%\''
        if favorites:
            request += f' AND users_to_items.favorite = 1'
        return self.cursor.execute(request).fetchall()

    def get_unsold_items(self, time_offset):
        days_offset = time_offset / 86400.0
        return self.cursor.execute(f'SELECT * FROM items WHERE items.sold = 0 AND '
                                   f'JULIANDAY(CURRENT_TIMESTAMP) - JULIANDAY(items.last_check) > {days_offset}').fetchall()

    def item_checked(self, item_id):
        req = f'UPDATE items SET last_check = CURRENT_TIMESTAMP WHERE id = {item_id}'
        self._execute(req)

    def get_users_per_item(self, item_id):
        return self.cursor.execute(
            f'SELECT users_to_items.user_id, users_to_items.favorite FROM users_to_items WHERE users_to_items.item_id = {item_id}').fetchall()

    def get_item(self, item_id):
        return self.cursor.execute(f'SELECT * FROM items WHERE items.id = {item_id}').fetchall()[0]

    def unsubscribe(self, user_id, vk_id):
        req = f'DELETE FROM users_to_items WHERE users_to_items.user_id = {user_id} AND item_id = {vk_id}'
        self._execute(req)

    def get_events(self, vk_id):
        req = f'SELECT * FROM events WHERE events.item_id = {vk_id}'
        return self.cursor.execute(req)
