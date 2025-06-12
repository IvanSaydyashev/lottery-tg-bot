from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (Application, ContextTypes, CommandHandler,
                          ChatMemberHandler)
from telegram.constants import ChatMemberStatus, ChatType

from bot.lottery import Lottery
from bot.randomiser import Randomiser
from services.firebase import FirebaseClient
from services.utils import decode_payload

class Bot:
    def __init__(self, app: Application, firebase: FirebaseClient) -> None:
        self.randomiser = Randomiser(firebase)
        self.lottery = Lottery(firebase, self.randomiser)
        self.firebase_db = firebase
        app.add_handler(self.lottery.get_handler())
        app.add_handler(ChatMemberHandler(self.invitation))
        app.add_handler(CommandHandler("start", self.start))

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send a message when the command /start is issued."""
        if context.args:
            await self.join_lot(update, context)
        keyboard = ReplyKeyboardMarkup(
            [[KeyboardButton("🎉 Создать розыгрыш")]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        await update.message.reply_text(
            "Привет! Я помогу тебе создать розыгрыш в Telegram канале или чате! "
            "Нажимай на кнопки и следуй инструкциям",
            reply_markup=keyboard
        )

    async def invitation(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        match ChatMemberStatus(update.my_chat_member.new_chat_member.status):
            case ChatMemberStatus.MEMBER | ChatMemberStatus.ADMINISTRATOR as status:
                user = update.my_chat_member.from_user
                chat = update.my_chat_member.chat
                if chat.type != ChatType.PRIVATE:
                    channels = await self.firebase_db.get_user_channels(user.id)
                    entry = {
                        "chat_id": chat.id,
                        "username": chat.mention_html()
                    }

                    updated = False
                    for ch in channels:
                        if ch["chat_id"] == chat.id:
                            ch["status"] = status
                            updated = True
                            break

                    if not updated:
                        entry["status"] = status
                        channels.append(entry)

                    await self.firebase_db.set_user_channels(user.id, channels)
                    await self.lottery.update_channel_list_message(update, context)

            case ChatMemberStatus.LEFT | ChatMemberStatus.BANNED:
                user = update.my_chat_member.from_user
                chat = update.my_chat_member.chat
                if chat.type != ChatType.PRIVATE:
                    channels = await self.firebase_db.get_user_channels(user.id)
                    del_channels = [ch for ch in range(len(channels)) if channels[ch]["chat_id"] == chat.id]
                    for ch in del_channels:
                        await self.firebase_db.delete(f"users/{user.id}/channels/{ch}")
                    await self.lottery.update_channel_list_message(update, context)
            case _:
                pass

    async def join_lot(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        data = decode_payload(context.args[0])
        owner_id = data["user_id"]
        lottery_id = data["lottery_id"]
        this_lottery = await self.firebase_db.read(f"lotteries/{owner_id}/{lottery_id}") or []
        publisher_chat_id = this_lottery["publisher_chat_id"]
        member = await context.bot.get_chat_member(chat_id=publisher_chat_id, user_id=user_id)
        if member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR]:
            if not this_lottery:
                await context.bot.send_message(chat_id=update.effective_chat.id,
                                               text="Розыгрыш не существует или уже завершен!")
            await update.message.reply_text(f"Вы присоединились к розыгрышу с ID {lottery_id}!")
            await self.firebase_db.update(f"lotteries/{owner_id}/{lottery_id}/participants/",
                                          {update.effective_user.id: update.effective_user.username})
            return

        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text="Для участия в розыгрыше необходимо быть участником канала:")