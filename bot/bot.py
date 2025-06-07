from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (Application, ContextTypes, CommandHandler,
                          ChatMemberHandler)
from telegram.constants import ChatMemberStatus, ChatType

from bot.lottery import Lottery
from services.firebase import FirebaseClient


class Bot:

    def __init__(self, app: Application, firebase: FirebaseClient) -> None:
        self.lottery = Lottery(firebase)
        self.firebase_db = firebase
        app.add_handler(self.lottery.get_handler())
        app.add_handler(ChatMemberHandler(self.invitation))
        app.add_handler(CommandHandler("start", self.start))

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send a message when the command /start is issued."""
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

