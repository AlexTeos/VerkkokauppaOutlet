import html
import json
import traceback
import re

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, Application, MessageHandler, filters, CallbackQueryHandler, CommandHandler

from scrapetools import ParsingError
from db import UniqueError

DB_UPDATE_INTERVAL = 2 * 60 * 60
TG_UPDATE_INTERVAL = 10 * 60


class TelegramTools:
    FILE_SIZE_LIMIT = 48 * 1024 * 1024

    def __init__(self, bot_token, admin_id, db, st, logger):
        self.db = db
        self.st = st
        self.logger = logger
        self.admin_id = admin_id

        async def post_init(app: Application) -> None:
            await app.bot.set_my_commands(
                [BotCommand("search", "search among your items"), BotCommand("list", "list of all your items"),
                 BotCommand("favorites", "list of your favorite items")])

        application = Application.builder().token(bot_token).post_init(post_init).build()
        job_queue = application.job_queue

        self.upd_job = job_queue.run_repeating(self.callback_minute, interval=TG_UPDATE_INTERVAL)

        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.new_item_handler))
        application.add_handler(CallbackQueryHandler(self.markup_handler))
        application.add_handler(CommandHandler("search", self.search_handler))
        application.add_handler(CommandHandler("list", self.list_handler))
        application.add_handler(CommandHandler("favorites", self.favorite_handler))
        application.add_handler(CommandHandler("update", self.manual_update_handler))
        application.add_error_handler(self.error_handler)
        application.run_polling()

    @staticmethod
    def retrieve_item_id(text):
        item_id = re.search(r'\d\d\d\d\d\d\d', text)
        if item_id:
            return item_id.group(0)
        return None

    async def new_item_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        item_id = self.retrieve_item_id(update.message.text)
        if not item_id:
            await update.message.reply_text('Can\'t find the item!')
            return

        try:
            sold, price, percent, full_price, caption = self.st.get_item_data(item_id)
        except ParsingError:
            await context.bot.send_message(chat_id=self.admin_id, text='Failed to add item! Please try again!')
            return

        if not sold:
            try:
                self.db.add_new_item(update.message.from_user.id, item_id, caption, full_price, price, percent)
            except UniqueError as err:
                favorite = self.db.is_favorite(update.message.from_user.id, item_id)
                message = (
                    f'You are already subscribed to this item!\n'
                    f'<b>[{"*" if favorite else "#"}{item_id}]</b> <a href="https://www.verkkokauppa.com/fi/outlet/yksittaiskappaleet/{item_id}">{caption}</a>\n'
                    f'Full price: {full_price}€\n'
                    f'Current price: {price}€\n'
                    f'Current sale: {percent}%'
                )
                keyboard = [
                    [
                        InlineKeyboardButton('Unsubscribe',
                                             callback_data=f'unsubscribe;{item_id};{sold};{favorite}'),
                        InlineKeyboardButton(f'{"Remove from" if favorite else "Add to"} favorite',
                                             callback_data=f'{"un" if favorite else ""}favorite;{item_id};{sold};{favorite}'),
                        InlineKeyboardButton('Item History', callback_data=f'history;{item_id};{sold};{favorite}'),
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(text=message, reply_markup=reply_markup,
                                                parse_mode=ParseMode.HTML)
                return
            message = (
                f'<b>[#{item_id}]</b> <a href="https://www.verkkokauppa.com/fi/outlet/yksittaiskappaleet/{item_id}">{caption}</a>'
                f' was added to your watch list!\n'
                f'Full price: {full_price}€\n'
                f'Current price: {price}€\n'
                f'Current sale: {percent}%'
            )
            keyboard = [
                [
                    InlineKeyboardButton('Unsubscribe', callback_data=f'unsubscribe;{item_id};0;0'),
                    InlineKeyboardButton('Add to favorite', callback_data=f'favorite;{item_id};0;0'),
                    InlineKeyboardButton('Item History', callback_data=f'history;{item_id};0;0'),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(text=message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text('Item is sold!')

    async def callback_minute(self, context: ContextTypes.DEFAULT_TYPE, time_offset=DB_UPDATE_INTERVAL):
        for item_id, _, _, last_price, _, _, _ in self.db.get_unsold_items(time_offset):
            try:
                sold, current_price, percent, full_price, caption = self.st.get_item_data(item_id)
            except ParsingError:
                continue
            if sold:
                self.db.mark_as_sold(item_id)
                _, caption, _, last_price, _, _, _ = self.db.get_item(item_id)
                for user_id, favorite in self.db.get_users_per_item(item_id):
                    keyboard = [
                        [
                            InlineKeyboardButton('Item History', callback_data=f'history;{item_id};{sold};{favorite}'),
                        ]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    message = f'<b>[{"*" if favorite else "#"}{item_id}]</b> {caption} is sold! The last price was {last_price}€'
                    await context.bot.send_message(chat_id=user_id,
                                                   text=message, parse_mode=ParseMode.HTML,
                                                   reply_markup=reply_markup)
            else:
                if current_price != last_price:
                    self.db.insert_event(item_id, percent, current_price)
                    for user_id, favorite in self.db.get_users_per_item(item_id):
                        message = (
                            f'<b>[{"*" if favorite else "#"}{item_id}]</b> <a href="https://www.verkkokauppa.com/fi/outlet/yksittaiskappaleet/{item_id}">{caption}</a>'
                            f' price changed!\n'
                            f'Before: {last_price}€\n'
                            f'After: {current_price}€\n'
                            f'Sale: {percent}%'
                        )
                        keyboard = [
                            [
                                InlineKeyboardButton('Unsubscribe',
                                                     callback_data=f'unsubscribe;{item_id};{sold};{favorite}'),
                                InlineKeyboardButton(f'{"Remove from" if favorite else "Add to"} favorite',
                                                     callback_data=f'{"un" if favorite else ""}favorite;{item_id};{sold};{favorite}'),
                                InlineKeyboardButton('Item History',
                                                     callback_data=f'history;{item_id};{sold};{favorite}'),
                            ]
                        ]
                        reply_markup = InlineKeyboardMarkup(keyboard)

                        await context.bot.send_message(chat_id=user_id, text=message, parse_mode=ParseMode.HTML,
                                                       reply_markup=reply_markup)
                else:
                    self.db.item_checked(item_id)

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        self.logger.error(msg='Exception while handling an update:', exc_info=context.error)

        tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
        tb_string = ''.join(tb_list)

        update_str = update.to_dict() if isinstance(update, Update) else str(update)
        message_list = [
            f'An exception was raised while handling an update\n',
            f'<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}',
            '</pre>\n\n',
            f'<pre>context.chat_data = {html.escape(str(context.chat_data))}</pre>\n\n',
            f'<pre>context.user_data = {html.escape(str(context.user_data))}</pre>\n\n',
            f'<pre>{html.escape(tb_string)}</pre>',
        ]

        await self.send_list(context, self.admin_id, message_list)

    async def markup_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        user_id = query.from_user.id
        await query.answer()

        query_data = query.data.split(";")
        command = query_data[0]
        item_id = query_data[1]
        sold = query_data[2]
        favorite = query_data[3]

        _, caption, full_price, _, last_check, _, _ = self.db.get_item(item_id)

        if command == 'subscribe':
            try:
                self.db.insert_user_to_item(user_id, item_id)
            except UniqueError as err:
                pass
            await context.bot.send_message(chat_id=user_id,
                                           text=f'You subscribed to <b>[#{item_id}]</b> <a href="https://www.verkkokauppa.com/fi/outlet/yksittaiskappaleet/{item_id}">{caption}</a>',
                                           parse_mode=ParseMode.HTML)
            favorite = 0
            command = 'main'

        if command == 'favorite':
            self.db.set_favorite(user_id, item_id, True)
            await context.bot.send_message(chat_id=user_id,
                                           text=f'You added <b>[#{item_id}]</b> <a href="https://www.verkkokauppa.com/fi/outlet/yksittaiskappaleet/{item_id}">{caption}</a> to favorites',
                                           parse_mode=ParseMode.HTML)
            favorite = 1
            command = 'main'

        if command == 'unfavorite':
            self.db.set_favorite(user_id, item_id, False)
            await context.bot.send_message(chat_id=user_id,
                                           text=f'You removed <b>[#{item_id}]</b> <a href="https://www.verkkokauppa.com/fi/outlet/yksittaiskappaleet/{item_id}">{caption}</a> from favorites',
                                           parse_mode=ParseMode.HTML)
            favorite = 0
            command = 'main'

        if command == 'unsubscribe':
            self.db.unsubscribe(user_id, item_id)
            await context.bot.send_message(chat_id=user_id,
                                           text=f'You unsubscribed from <b>[#{item_id}]</b> <a href="https://www.verkkokauppa.com/fi/outlet/yksittaiskappaleet/{item_id}">{caption}</a>',
                                           parse_mode=ParseMode.HTML)
            keyboard = [
                [InlineKeyboardButton('Subscribe', callback_data=f'subscribe;{item_id};{sold};{favorite}'), ],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_reply_markup(reply_markup=reply_markup)

        if command == 'main':
            keyboard = [
                [
                    InlineKeyboardButton('Unsubscribe', callback_data=f'unsubscribe;{item_id};{sold};{favorite}'),
                    InlineKeyboardButton(f'{"Remove from" if favorite else "Add to"} favorite',
                                         callback_data=f'{"un" if favorite else ""}favorite;{item_id};{sold};{favorite}'),
                    InlineKeyboardButton('Item History', callback_data=f'history;{item_id};{sold};{favorite}'),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_reply_markup(reply_markup=reply_markup)

        if command == 'history':
            item_caption = caption if sold else f'<a href="https://www.verkkokauppa.com/fi/outlet/yksittaiskappaleet/{item_id}">{caption}</a>'
            history = f'<b>[#{item_id}]</b> {item_caption} <s>{full_price}€</s> history:\n\n'
            events_count = 0
            for _, _, ts, percent, price in self.db.get_events(item_id):
                events_count += 1
                history += f'[{ts.split()[0]}]: {percent}% {price}€\n'
            if not events_count:
                history = f'<b>[#{item_id}]</b> {item_caption} <s>{full_price}€</s> doesn\'t have any history!\n'
            history += f'\nLast check: {last_check}'
            await context.bot.send_message(chat_id=user_id, text=history, parse_mode=ParseMode.HTML)

    async def search_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        search_request = update.message.text[len('/search '):]
        items_list = [f'Search for "{search_request}":']
        for item_id, caption, full_price, last_price, _, _, _, favorite in self.db.get_user_items(
                update.message.from_user.id,
                search_request):
            items_list.append(
                f'<b>[{"*" if favorite else "#"}{item_id}]</b> <s>{full_price}€</s> {last_price}€ <a href="https://www.verkkokauppa.com/fi/outlet/yksittaiskappaleet/{item_id}">{caption}</a>')
        if len(items_list) > 1:
            await self.send_list(context, update.message.from_user.id, items_list)
            return

        await update.message.reply_text(text=f'No item was found for "{search_request}"!\n', parse_mode=ParseMode.HTML)

    async def list_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        items_list = [f'List of all your unsold items:']
        for item_id, caption, full_price, last_price, _, _, _, favorite in self.db.get_user_items(
                update.message.from_user.id):
            items_list.append(
                f'<b>[{"*" if favorite else "#"}{item_id}]</b> <s>{full_price}€</s> {last_price}€ <a href="https://www.verkkokauppa.com/fi/outlet/yksittaiskappaleet/{item_id}">{caption}</a>')
        if len(items_list) > 1:
            await self.send_list(context, update.message.from_user.id, items_list)
            return

        await update.message.reply_text(text=f'You don\'t have any items!\n')

    async def favorite_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        items_list = [f'List of your favorite unsold items:']
        for item_id, caption, full_price, last_price, _, _, _, _ in self.db.get_user_items(update.message.from_user.id,
                                                                                           favorites=True):
            items_list.append(
                f'<b>[#{item_id}]</b> <s>{full_price}€</s> {last_price}€ <a href="https://www.verkkokauppa.com/fi/outlet/yksittaiskappaleet/{item_id}">{caption}</a>')
        if len(items_list) > 1:
            await self.send_list(context, update.message.from_user.id, items_list)
            return

        await update.message.reply_text(text=f'You don\'t have any favorite items!\n')

    async def manual_update_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if str(update.message.from_user.id) != self.admin_id:
            await update.message.reply_text(text=f'You aren\'t allowed to use this command!')
            return
        await update.message.reply_text(text=f'Starting manual update!')
        await self.callback_minute(context, 0)
        await update.message.reply_text(text=f'Manual update has finished!')

    @staticmethod
    async def send_list(context, chat_id, lines):
        message = ''
        for line in lines:
            if len(line) >= 4000:
                continue
            if len(message) + len(line) >= 4000:
                await context.bot.send_message(chat_id=chat_id, text=message, parse_mode=ParseMode.HTML)
                message = ''
            message += line + '\n'
        await context.bot.send_message(chat_id=chat_id, text=message, parse_mode=ParseMode.HTML)
