from datetime import datetime
from enum import Enum
import re
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, ContextTypes, CommandHandler,
                          ChatMemberHandler, ConversationHandler, CallbackQueryHandler, MessageHandler, filters)
from telegram.constants import ChatMemberStatus, ChatType

class Bot:
    class NewLotteryState(Enum):
        READY = 0
        TEXT = 1
        NUM_WINNERS = 2
        MODE = 3
        DATE = 4
        COUNT = 5
        PUBLISHER = 6

    # new_lottery = "Создать розыгрыш"

    def __init__(self, app: Application) -> None:
        self.mode_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Закончить по дате", callback_data="mode_date")],
            [InlineKeyboardButton("Закончить по числу участников", callback_data="mode_count")],
            [InlineKeyboardButton("Назад", callback_data="back_data")]
        ])
        self.back_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("Назад", callback_data="back_data")]
            ])

        # TODO: временное хранилище чисто для тестов надо заменить
        app.add_handler(CommandHandler("help", self.help_command))
        app.add_handler(ChatMemberHandler(self.invitation))
        app.add_handler(ConversationHandler(
            entry_points=[CommandHandler("start", self.start)],
            states={
                Bot.NewLotteryState.READY.value: [
                    CallbackQueryHandler(self.button_handler)
                ],
                Bot.NewLotteryState.TEXT.value: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.lottery_text),
                ],
                Bot.NewLotteryState.NUM_WINNERS.value: [
                    CallbackQueryHandler(self.lottery_num_winners),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.lottery_num_winners),
                ],
                Bot.NewLotteryState.MODE.value: [
                    CallbackQueryHandler(self.lottery_mode)
                ],
                Bot.NewLotteryState.DATE.value: [
                    CallbackQueryHandler(self.lottery_date),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.lottery_date),
                ],
                Bot.NewLotteryState.COUNT.value: [
                    CallbackQueryHandler(self.lottery_count),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.lottery_count),
                ],
                Bot.NewLotteryState.PUBLISHER.value: [
                    CallbackQueryHandler(self.lottery_publisher),
                ]
            },
            fallbacks=[],
        ))
        # app.add_handler(CommandHandler("start", self.start))
        # app.add_handler()

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Send a message when the command /start is issued."""
        # keyboard = [[Bot.new_lottery]]
        # keyboard = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "Привет! Я помогу тебе создать розыгрыш в Telegram канале или чате! "
            "Нажимай на кнопки и следуй инструкциям:",
            reply_markup=None
        )
        await self.create_channel_list_message(update, context)
        return Bot.NewLotteryState.READY.value

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send a message when the command /help is issued."""
        await update.message.reply_text("Help!")

    async def invitation(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        match ChatMemberStatus(update.my_chat_member.new_chat_member.status):
            case ChatMemberStatus.MEMBER:
                user = update.my_chat_member.from_user
                chat = update.my_chat_member.chat
                if chat.type != ChatType.PRIVATE:
                    channels = context.bot_data[user.id]["channels"]
                    try:
                        idx = channels.index({
                            "status": ChatMemberStatus.ADMINISTRATOR,
                            "chat_id": chat.id,
                            "username": chat.mention_html()
                        })
                        channels[idx]["status"] = ChatMemberStatus.MEMBER
                    except ValueError:
                        channels.append({
                            "status": ChatMemberStatus.MEMBER,
                            "chat_id": chat.id,
                            "username": chat.mention_html()
                        })
                    await self.update_channel_list_message(update, context)
            case ChatMemberStatus.ADMINISTRATOR:
                user = update.my_chat_member.from_user
                chat = update.my_chat_member.chat
                if chat.type != ChatType.PRIVATE:
                    channels = context.bot_data[user.id]["channels"]
                    try:
                        chan = channels[channels.index({
                            "status": ChatMemberStatus.MEMBER,
                            "chat_id": chat.id,
                            "username": chat.mention_html()
                        })]
                        chan["status"] = ChatMemberStatus.ADMINISTRATOR
                    except ValueError:
                        channels.append({
                            "status": ChatMemberStatus.ADMINISTRATOR,
                            "chat_id": chat.id,
                            "username": chat.mention_html()
                        })
                    await self.update_channel_list_message(update, context)
            case ChatMemberStatus.LEFT | ChatMemberStatus.BANNED:
                user = update.my_chat_member.from_user
                chat = update.my_chat_member.chat
                if chat.type != ChatType.PRIVATE:
                    channels = context.bot_data[user.id]["channels"]
                    try:
                        idx = channels.index({
                            "status": ChatMemberStatus.MEMBER,
                            "chat_id": chat.id,
                            "username": chat.mention_html()
                        })
                    except ValueError:
                        try:
                            idx = channels.index({
                                "status": ChatMemberStatus.ADMINISTRATOR,
                                "chat_id": chat.id,
                                "username": chat.mention_html()
                            })
                        except ValueError:
                            return
                    del channels[idx]
                    await self.update_channel_list_message(update, context)
            case _:
                pass

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
            [InlineKeyboardButton("Готово", callback_data="ready")],
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

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        user = update.effective_user

        channels = context.bot_data[user.id]["channels"]
        if not channels:
            await query.answer("Добавьте бота как администратора хотя бы в один канал!", show_alert=True)
            return Bot.NewLotteryState.READY.value
        if not all(c["status"] == ChatMemberStatus.ADMINISTRATOR for c in channels):
            await query.answer("Бот должен быть администратором во всех каналах, где он есть!", show_alert=True)
            return Bot.NewLotteryState.READY.value

        await query.edit_message_text("Отлично! Теперь отправьте описание розыгрыша.")

        return Bot.NewLotteryState.TEXT.value

    async def lottery_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        description = update.message.text # TODO: Сохранить описание в бд

        await update.message.reply_text("Отлично! Теперь отправьте количество победителей числом.",
                                        reply_markup=self.back_keyboard)
        return Bot.NewLotteryState.NUM_WINNERS.value

    async def lottery_num_winners(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        if update.callback_query:
            query = update.callback_query
            if query.data == "back_data":
                await query.edit_message_text("Отлично! Теперь отправьте описание розыгрыша.")
                return Bot.NewLotteryState.TEXT.value
            return Bot.NewLotteryState.NUM_WINNERS.value

        num_winners = update.message.text
        if num_winners.isdigit(): # TODO: Сохранить число в бд
            await update.message.reply_text("Как будет определяться конец розыгрыша?", reply_markup=self.mode_keyboard)
            return Bot.NewLotteryState.MODE.value

        await update.message.reply_text("Неверный формат. Введите число победителей (целое число).",
                                        reply_markup=self.back_keyboard)
        return Bot.NewLotteryState.NUM_WINNERS.value

    async def lottery_mode(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query

        if query.data == "mode_date":
            await query.edit_message_text("Отправьте дату окончания розыгрыша в формате дд.мм.гггг чч:мм, "
                                          "например, 01.01.2024 12:00.", reply_markup=self.back_keyboard)
            return Bot.NewLotteryState.DATE.value
        elif query.data == "mode_count":
            await query.edit_message_text("Отправьте максимальное количество участников (числом).", reply_markup=self.back_keyboard)
            return Bot.NewLotteryState.COUNT.value

        await query.edit_message_text("Отлично! Теперь отправьте количество победителей числом.",
                                      reply_markup=self.back_keyboard)
        return Bot.NewLotteryState.NUM_WINNERS.value

    async def lottery_count(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        if update.callback_query:
            query = update.callback_query
            if query.data == "back_data":
                await query.edit_message_text("Как будет определяться конец розыгрыша?",
                                              reply_markup=self.mode_keyboard)
                return Bot.NewLotteryState.MODE.value
            return Bot.NewLotteryState.COUNT.value

        count_str = update.message.text
        publisher_keyboard = self.get_publisher_channels_keyboard(update, context)
        if count_str.isdigit(): # TODO: Сохранить число в бд
            await update.message.reply_text("Отлично! Укажите канал, который опубликует результаты розыгрыша!",
                                            reply_markup=publisher_keyboard)
            return Bot.NewLotteryState.PUBLISHER.value

        await update.message.reply_text("Неверный формат. Введите максимальное число участников (целое число).",
                                        reply_markup=self.back_keyboard)
        return Bot.NewLotteryState.COUNT.value

    async def lottery_date(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        if update.callback_query:
            query = update.callback_query
            if query.data == "back_data":
                await query.edit_message_text("Как будет определяться конец розыгрыша?",
                                              reply_markup=self.mode_keyboard)
                return Bot.NewLotteryState.MODE.value
            return Bot.NewLotteryState.DATE.value

        date_str = update.message.text
        date = self.parse_date(date_str) # TODO: Сохранить дату в бд
        publisher_keyboard = self.get_publisher_channels_keyboard(update, context)
        if date:
            await update.message.reply_text("Отлично! Укажите канал, который опубликует результаты розыгрыша!",
                                            reply_markup=publisher_keyboard)
            return Bot.NewLotteryState.PUBLISHER.value

        await update.message.reply_text(
            "Не удалось распознать дату. Пожалуйста, отправьте в формате дд.мм.гггг чч:мм, "
            "например, 01.01.2024 12:00.", reply_markup=self.back_keyboard)
        return Bot.NewLotteryState.DATE.value

    def parse_date(self, date_str: str) -> datetime | None:
        """
        Преобразует строку в datetime, если она соответствует формату 'dd.mm.yyyy hh:mm',
        иначе возвращает None.
        """
        try:
            return datetime.strptime(date_str, "%d.%m.%Y %H:%M")
        except ValueError:
            return None

    async def lottery_publisher(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query

        if query.data == "back_data":
            await query.edit_message_text("Как будет определяться конец розыгрыша?",
                                          reply_markup=self.mode_keyboard)
            return Bot.NewLotteryState.MODE.value
        # TODO: Сохранить канал в бд
        await context.bot.send_message(chat_id=query.from_user.id, text="Отлично! Розыгрыш создан!")
        return ConversationHandler.END

    def get_publisher_channels_keyboard(self, update: Update,
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

        return InlineKeyboardMarkup(keyboard)