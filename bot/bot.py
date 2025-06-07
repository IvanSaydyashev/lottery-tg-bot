from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (Application, ContextTypes, CommandHandler,
                          ChatMemberHandler)
from telegram.constants import ChatMemberStatus, ChatType

from bot.lottery import Lottery


class Bot:

    def __init__(self, app: Application) -> None:
        self.lottery = Lottery()
        app.add_handler(self.lottery.get_handler())
        app.add_handler(CommandHandler("help", self.help_command))
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
                    await self.lottery.update_channel_list_message(update, context)
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
                    await self.lottery.update_channel_list_message(update, context)
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
                    await self.lottery.update_channel_list_message(update, context)
            case _:
                pass
