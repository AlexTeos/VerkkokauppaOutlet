import logging
import asyncio
from time import sleep
from telegram import Update, Bot, InputMediaPhoto, InputMediaVideo
from telegram.error import (TimedOut, TelegramError, Forbidden, NetworkError)
from telegram.ext import (Application, CommandHandler, ContextTypes, filters,
                          MessageHandler, ApplicationBuilder, Updater)


async def timeout_retry(attempts, func, *args, **kwargs):
    for i in range(attempts):
        try:
            result = await func(*args, **kwargs)
        except TimedOut as err:
            exception = err
        except Exception as err:
            raise err
        else:
            return result
    raise exception


class TelegramTools:
    FILE_SIZE_LIMIT = 48 * 1024 * 1024

    def __init__(self, bot_token, admin_id):
        self.logger = logging.getLogger('vk')
        self.admin_id = admin_id
        self.logger.info('Sign in to telegram bot: id - {0}'.format(bot_token))

        self.bot = Bot(bot_token)

        try:
            self.update_id = asyncio.run(self.bot.get_updates())[0].update_id
        except IndexError:
            self.update_id = None

    def get_update(self):

        update = self.get_updates()
        if update:
            self.update_id += 1

            if update.message and update.message.text:
                return (update.message.from_user.id, update.message.text)
                #self.logger.info("Found message %s!", update.message.text)
                #await update.message.reply_text(update.message.text)


        return (None, None)

    def get_updates(self):
        print(f'get_updates with update_id: {self.update_id}')
        try:
            updates = asyncio.run(self.bot.get_updates(offset=self.update_id, timeout=10, allowed_updates=Update.ALL_TYPES))
            print(f'get_updates returned {len(updates)} updates')
            if updates:
                return updates[0]
        except NetworkError as err:
            print(f'get_updates network error')
            sleep(1)
        except Forbidden:
            self.update_id += 1

        return None
