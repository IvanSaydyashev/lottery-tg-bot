from datetime import datetime
from enum import Enum

from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.constants import ChatMemberStatus
from telegram.ext import ConversationHandler, CommandHandler, CallbackQueryHandler, MessageHandler, \
    filters, ContextTypes

import re


def get_publisher_channels_keyboard(update: Update,
                                    context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
    """
    Возвращает клавиатуру с каналами пользователя, которые могут быть выбраны в качестве публикатора.
    """
    channels = context.bot_data[update.effective_user.id]["channels"]
    keyboard = []
    for i, channel in enumerate(channels):
        match = re.search(r'>([^<]+)<', channel["username"])
        title = match.group(1) if match else "Канал"

        button = InlineKeyboardButton(text=title, callback_data=f"{channel['chat_id']}")
        keyboard.append([button])  # каждая кнопка в отдельной строке
    keyboard.append([InlineKeyboardButton("Назад", callback_data="back_data")])
    return InlineKeyboardMarkup(keyboard)

def parse_date(date_str: str) -> datetime | None:
    """
    Преобразует строку в datetime, если она соответствует формату 'dd.mm.yyyy hh:mm',
    иначе возвращает None.
    """
    try:
        return datetime.strptime(date_str, "%d.%m.%Y %H:%M")
    except ValueError:
        return None

class Lottery:
    class NewLotteryState(Enum):
        READY = 0
        TEXT = 1
        NUM_WINNERS = 2
        MODE = 3
        DATE = 4
        COUNT = 5
        PUBLISHER = 6


    def __init__(self):
        self.mode_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Закончить по дате", callback_data="mode_date")],
            [InlineKeyboardButton("Закончить по числу участников", callback_data="mode_count")],
            [InlineKeyboardButton("Назад", callback_data="back_data")]
        ])
        self.back_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("Назад", callback_data="back_data")]
            ])

        self.lottery_text_guide = "Отлично! Теперь отправьте полное описание розыгрыша вместе со вложениями при необходимости."
        self.lottery_num_winners_guide = "Определите количество победителей."
        self.lottery_mode_guide = "Теперь выберите режим окончания розыгрыша."
        self.lottery_date_guide = "Теперь выберите дату окончания розыгрыша. Например: 01.01.2023 00:00"
        self.lottery_count_guide = "Отлично! Теперь выберите количество участников, при достижении которого розыгрыш будет заканчиваться."
        self.lottery_publisher_guide = "Отлично! Выберите канал, который опубликует результаты розыгрыша."


    def get_handler(self):
        return ConversationHandler(
            entry_points=[
                CommandHandler("new_lot", self.new_lot),
                MessageHandler(filters.TEXT & filters.Regex("^🎉 Создать розыгрыш$"), self.new_lot),
            ],
            states={
                self.NewLotteryState.READY.value: [
                    CallbackQueryHandler(self.setup_lot)
                ],
                self.NewLotteryState.TEXT.value: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.lottery_text),
                ],
                self.NewLotteryState.NUM_WINNERS.value: [
                    CallbackQueryHandler(self.lottery_num_winners),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.lottery_num_winners),
                ],
                self.NewLotteryState.MODE.value: [
                    CallbackQueryHandler(self.lottery_mode)
                ],
                self.NewLotteryState.DATE.value: [
                    CallbackQueryHandler(self.lottery_date),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.lottery_date),
                ],
                self.NewLotteryState.COUNT.value: [
                    CallbackQueryHandler(self.lottery_count),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.lottery_count),
                ],
                self.NewLotteryState.PUBLISHER.value: [
                    CallbackQueryHandler(self.lottery_publisher),
                ]
            },
            fallbacks=[],
        )

    async def create_channel_list_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        keyboard = [
            [InlineKeyboardButton("Готово", callback_data="ready")],
        ]
        keyboard = InlineKeyboardMarkup(keyboard)
        context.bot_data.setdefault(update.effective_user.id, {"channels": []})
        channels = context.bot_data[update.effective_user.id]["channels"]
        message = await update.message.reply_text(
            "Для начала добавьте бота как администратора во все каналы, "
            "которые будут организаторами розыгрыша.\n\nВаши каналы, в которых есть бот:\n" +
            "\n".join(map(lambda x: f'{x["username"]} ({x["status"]})', sorted(channels, key=lambda x: x["username"]))),
            reply_markup=keyboard,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        context.bot_data[update.effective_user.id]["added_channels_message"] = message.id

    async def update_channel_list_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.my_chat_member.from_user
        channels = context.bot_data[user.id]["channels"]
        keyboard = [
            [InlineKeyboardButton("Начать", callback_data="ready")],
        ]
        keyboard = InlineKeyboardMarkup(keyboard)
        message_id = context.bot_data[user.id]["added_channels_message"]
        await context.bot.edit_message_text(
            chat_id=user.id,
            message_id=message_id,
            text="Для начала добавьте бота как администратора во все каналы, "
                 "которые будут организаторами розыгрыша.\n\nВаши каналы, в которых есть бот:\n" +
                 "\n".join(map(lambda x: f'{x["username"]} ({x["status"]})',
                               sorted(channels, key=lambda x: x["username"]))),
            parse_mode="HTML",
            reply_markup=keyboard,
            disable_web_page_preview=True
        )

    async def new_lot(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await self.create_channel_list_message(update, context)
        return self.NewLotteryState.READY.value

    async def setup_lot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        user = update.effective_user

        channels = context.bot_data[user.id]["channels"]
        if not channels:
            await query.answer("Добавьте бота как администратора хотя бы в один канал!", show_alert=True)
            return self.NewLotteryState.READY.value
        if not all(c["status"] == ChatMemberStatus.ADMINISTRATOR for c in channels):
            await query.answer("Бот должен быть администратором во всех каналах, где он есть!", show_alert=True)
            return self.NewLotteryState.READY.value

        await query.edit_message_text(self.lottery_text_guide)

        return self.NewLotteryState.TEXT.value


    async def lottery_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        description = update.message  # TODO: Сохранить описание в бд

        await update.message.reply_text(self.lottery_num_winners_guide,
                                        reply_markup=self.back_keyboard)
        return self.NewLotteryState.NUM_WINNERS.value


    async def lottery_num_winners(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        if update.callback_query:
            query = update.callback_query
            if query.data == "back_data":
                await query.edit_message_text(self.lottery_text_guide)
                return self.NewLotteryState.TEXT.value
            return self.NewLotteryState.NUM_WINNERS.value

        num_winners = update.message.text
        if num_winners.isdigit():  # TODO: Сохранить число в бд
            await update.message.reply_text(self.lottery_mode_guide, reply_markup=self.mode_keyboard)
            return self.NewLotteryState.MODE.value

        await update.message.reply_text("Неверный формат. Введите число победителей (целое число).",
                                        reply_markup=self.back_keyboard)
        return self.NewLotteryState.NUM_WINNERS.value


    async def lottery_mode(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query

        if query.data == "mode_date":
            await query.edit_message_text(self.lottery_date_guide, reply_markup=self.back_keyboard)
            return self.NewLotteryState.DATE.value
        elif query.data == "mode_count":
            await query.edit_message_text(self.lottery_count_guide,
                                          reply_markup=self.back_keyboard)
            return self.NewLotteryState.COUNT.value

        await query.edit_message_text(self.lottery_num_winners_guide,
                                      reply_markup=self.back_keyboard)
        return self.NewLotteryState.NUM_WINNERS.value


    async def lottery_count(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        if update.callback_query:
            query = update.callback_query
            if query.data == "back_data":
                await query.edit_message_text(self.lottery_mode_guide,
                                              reply_markup=self.mode_keyboard)
                return self.NewLotteryState.MODE.value
            return self.NewLotteryState.COUNT.value

        count_str = update.message.text
        publisher_keyboard = get_publisher_channels_keyboard(update, context)
        if count_str.isdigit():  # TODO: Сохранить число в бд
            await update.message.reply_text(self.lottery_publisher_guide,
                                            reply_markup=publisher_keyboard)
            return self.NewLotteryState.PUBLISHER.value

        await update.message.reply_text("Неверный формат. Введите максимальное число участников (целое число).",
                                        reply_markup=self.back_keyboard)
        return self.NewLotteryState.COUNT.value


    async def lottery_date(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        if update.callback_query:
            query = update.callback_query
            if query.data == "back_data":
                await query.edit_message_text(self.lottery_mode_guide,
                                              reply_markup=self.mode_keyboard)
                return self.NewLotteryState.MODE.value
            return self.NewLotteryState.DATE.value

        date_str = update.message.text
        date = parse_date(date_str)  # TODO: Сохранить дату в бд
        publisher_keyboard = get_publisher_channels_keyboard(update, context)
        if date:
            await update.message.reply_text(self.lottery_publisher_guide,
                                            reply_markup=publisher_keyboard)
            return self.NewLotteryState.PUBLISHER.value

        await update.message.reply_text(
            "Не удалось распознать дату." + self.lottery_date_guide, reply_markup=self.back_keyboard)
        return self.NewLotteryState.DATE.value


    async def lottery_publisher(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query

        if query.data == "back_data":
            await query.edit_message_text(self.lottery_mode_guide,
                                          reply_markup=self.mode_keyboard)
            return self.NewLotteryState.MODE.value
        # TODO: Сохранить канал в бд
        await context.bot.send_message(chat_id=query.from_user.id, text="Отлично! Розыгрыш создан!")
        return ConversationHandler.END


