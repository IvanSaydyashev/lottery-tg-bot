import uuid
from datetime import datetime
from enum import Enum
from zoneinfo import ZoneInfo

from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.constants import ChatMemberStatus
from telegram.ext import ConversationHandler, CommandHandler, CallbackQueryHandler, MessageHandler, \
    filters, ContextTypes

import re

from bot.randomiser import Randomiser
from services.utils import encode_payload
from services.firebase import FirebaseClient



def parse_date(date_str: str) -> datetime | None:
    """
    Преобразует строку в datetime, если она соответствует формату 'dd.mm.yyyy hh:mm',
    иначе возвращает None.
    """
    try:
        date = datetime.strptime(date_str, "%d.%m.%Y %H:%M")
        moscow_time = date.replace(tzinfo=ZoneInfo("Europe/Moscow"))
        return moscow_time.astimezone(ZoneInfo("UTC"))
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


    def __init__(self, firebase: FirebaseClient, randomiser: Randomiser):
        self.firebase_db = firebase
        self.randomise_job = randomiser
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
        self.lottery_date_guide = "Теперь выберите дату окончания розыгрыша по МСК. Например: 01.01.2023 00:00"
        self.lottery_count_guide = "Отлично! Теперь выберите количество участников, при достижении которого розыгрыш будет заканчиваться."
        self.lottery_publisher_guide = "Отлично! Выберите канал, который опубликует результаты розыгрыша."

    async def get_publisher_channels_keyboard(self, update: Update,
                                        context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
        """
        Возвращает клавиатуру с каналами пользователя, которые могут быть выбраны в качестве публикатора.
        """
        channels = await self.firebase_db.get_user_channels(update.effective_user.id)
        keyboard = []
        for i, channel in enumerate(channels):
            match = re.search(r'>([^<]+)<', channel["username"])
            title = match.group(1) if match else "Канал"
            button = InlineKeyboardButton(text=title, callback_data=f"{channel['chat_id']}")
            keyboard.append([button])
        keyboard.append([InlineKeyboardButton("Назад", callback_data="back_data")])
        return InlineKeyboardMarkup(keyboard)

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
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Готово", callback_data="ready")]])
        user_id = update.effective_user.id
        channels = await self.firebase_db.get_user_channels(user_id)
        message = await update.message.reply_text(
            "Для начала добавьте бота как администратора во все каналы, "
            "которые будут организаторами розыгрыша.\n\nВаши каналы, в которых есть бот:\n" +
            "\n".join(f'{c["username"]} ({c["status"]})' for c in sorted(channels, key=lambda x: x["username"])),
            reply_markup=keyboard,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        await self.firebase_db.update(f"users/{user_id}", {"added_channels_message": message.message_id})

    async def update_channel_list_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.my_chat_member.from_user
        user_id = user.id
        channels = await self.firebase_db.get_user_channels(user_id)
        added_msg_id = (await self.firebase_db.read(f"users/{user_id}/added_channels_message")) or 0
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Начать", callback_data="ready")]])
        await context.bot.edit_message_text(
            chat_id=user_id,
            message_id=added_msg_id,
            text="Для начала добавьте бота как администратора во все каналы, "
                 "которые будут организаторами розыгрыша.\n\nВаши каналы, в которых есть бот:\n" +
                 "\n".join(f'{c["username"]} ({c["status"]})' for c in sorted(channels, key=lambda x: x["username"])),
            parse_mode="HTML",
            reply_markup=keyboard,
            disable_web_page_preview=True
        )

    async def new_lot(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        context.user_data["lottery_id"] = str(uuid.uuid4())[:8]
        await self.create_channel_list_message(update, context)
        return self.NewLotteryState.READY.value

    async def setup_lot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        user_id = update.effective_user.id
        channels = await self.firebase_db.get_user_channels(user_id)

        if not channels:
            await query.answer("Добавьте бота как администратора хотя бы в один канал!", show_alert=True)
            return self.NewLotteryState.READY.value
        if not all(c["status"] == ChatMemberStatus.ADMINISTRATOR for c in channels):
            await query.answer("Бот должен быть администратором во всех каналах, где он есть!", show_alert=True)
            return self.NewLotteryState.READY.value

        await query.edit_message_text(self.lottery_text_guide)
        return self.NewLotteryState.TEXT.value

    async def lottery_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        description = update.message
        await self.firebase_db.write(f"lotteries/{update.effective_user.id}/{context.user_data['lottery_id']}", {
            "description": description.text
        })
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
        if num_winners.isdigit():
            await self.firebase_db.update(f"lotteries/{update.effective_user.id}/{context.user_data['lottery_id']}", {
                "num_winners": int(num_winners)
            })
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
        publisher_keyboard = await self.get_publisher_channels_keyboard(update, context)
        if count_str.isdigit():
            await self.firebase_db.update(f"lotteries/{update.effective_user.id}/{context.user_data['lottery_id']}", {
                "max_count": int(count_str),
            })
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
        utc_time = parse_date(date_str)


        await self.firebase_db.update(f"lotteries/{update.effective_user.id}/{context.user_data['lottery_id']}", {
            "until_date": utc_time.isoformat()
        })

        publisher_keyboard = await self.get_publisher_channels_keyboard(update, context)
        if utc_time:
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

        await self.firebase_db.update(f"lotteries/{update.effective_user.id}/{context.user_data['lottery_id']}", {
            "publisher_chat_id": int(query.data)
        })
        await self.publish_lottery(update, context)
        return ConversationHandler.END

    async def publish_lottery(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        lottery_id = context.user_data["lottery_id"]
        description = await self.firebase_db.read(
            f"lotteries/{update.effective_user.id}/{lottery_id}/description")
        chat_id = await self.firebase_db.read(
            f"lotteries/{update.effective_user.id}/{lottery_id}/publisher_chat_id")
        num_winners = await self.firebase_db.read(
            f"lotteries/{update.effective_user.id}/{lottery_id}/num_winners"
        )
        date = await self.firebase_db.read(
            f"lotteries/{update.effective_user.id}/{lottery_id}/until_date")
        if date:
            date = datetime.fromisoformat(date)
            context.job_queue.run_once(self.randomise_job.date_result, when=date, data=
            {
                "owner_id": update.effective_user.id,
                "lottery_id": lottery_id,
                "publisher_chat_id": chat_id,
                "num_winners": num_winners
            })
            return
        max_count = await self.firebase_db.read(
            f"lotteries/{update.effective_user.id}/{lottery_id}/max_count"
        )
        interval_seconds = 60 * 10
        context.job_queue.run_repeating(self.randomise_job.check_lottery_count, interval=interval_seconds, first=0, data=
        {
            "owner_id": update.effective_user.id,
            "lottery_id": lottery_id,
            "goal_participants": max_count,
            "publisher_chat_id": chat_id,
            "num_winners": num_winners
        })
        lottery_url = await self.generate_invite_link(update, context)
        await context.bot.send_message(chat_id=update.effective_user.id,
                                       text=f"Розыгрыш успешно опубликован!\n")
        await context.bot.send_message(
            chat_id=chat_id, text=f'{description}\nДля участия перейдите по <a href="{lottery_url}">ссылке</a>',
            parse_mode="HTML"
        )

    async def generate_invite_link(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
        bot_username = "t_ad_manager_bot"

        lottery_id = context.user_data["lottery_id"]
        user_id = update.effective_user.id
        encoded_payload = encode_payload(user_id, lottery_id)

        url = f"https://t.me/{bot_username}?start={encoded_payload}"
        return url