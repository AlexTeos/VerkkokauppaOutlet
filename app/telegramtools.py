import html
import json
import traceback

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, Application, MessageHandler, filters

from scrapetools import ParsingError


class TelegramTools:
    FILE_SIZE_LIMIT = 48 * 1024 * 1024

    def __init__(self, bot_token, admin_id, db, st, logger):
        self.db = db
        self.st = st
        self.logger = logger
        self.admin_id = admin_id
        application = Application.builder().token(bot_token).build()
        job_queue = application.job_queue

        self.upd_job = job_queue.run_repeating(self.callback_minute, interval=10)

        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.newItem))

        application.add_error_handler(self.error_handler)

        application.run_polling()

    async def newItem(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        item_id = update.message.text
        sold = None
        price = None
        try:
            sold, price, _, _, caption = self.st.get_item_data(item_id)
        except ParsingError:
            await context.bot.send_message(chat_id=self.admin_id, text='Failed to add item! Please try again!')

        if not sold:
            self.db.insert_item(update.message.from_user.id, update.message.text, caption, price)
            await update.message.reply_text(f'Added "{caption}" to your watch list!\nThe currect price is {price}€')
        else:
            await update.message.reply_text('Item is sold!')

    async def callback_minute(self, context: ContextTypes.DEFAULT_TYPE):
        for item_id, _, last_price, _, _, _ in self.db.get_unsold_items(time_offset=10):
            try:
                sold, current_price, percent, full_price, _ = self.st.get_item_data(item_id)
            except ParsingError:
                continue
            if sold:
                self.db.mark_as_sold(item_id)
                for _, user_id in self.db.get_users_per_item(item_id):
                    await context.bot.send_message(chat_id=user_id, text=f'Item {item_id} is sold!')
            else:
                if current_price != last_price:
                    self.db.insert_event(item_id, percent, current_price, full_price)
                    for _, user_id in self.db.get_users_per_item(item_id):
                        await context.bot.send_message(chat_id=user_id, text=f'Item\'s {item_id} price changed! '
                                                                             f'{last_price} -> {current_price}')
                else:
                    self.db.item_checked(item_id)

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        self.logger.error(msg="Exception while handling an update:", exc_info=context.error)

        tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
        tb_string = "".join(tb_list)

        update_str = update.to_dict() if isinstance(update, Update) else str(update)
        message = (
            f"An exception was raised while handling an update\n"
            f"<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}"
            "</pre>\n\n"
            f"<pre>context.chat_data = {html.escape(str(context.chat_data))}</pre>\n\n"
            f"<pre>context.user_data = {html.escape(str(context.user_data))}</pre>\n\n"
            f"<pre>{html.escape(tb_string)}</pre>"
        )

        await context.bot.send_message(
            chat_id=self.admin_id, text=message, parse_mode=ParseMode.HTML
        )
