from enum import Enum

from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, ContextTypes, CommandHandler,
                          ChatMemberHandler, ConversationHandler, CallbackQueryHandler, )
from telegram.constants import ChatMemberStatus, ChatType


class Bot:
    class NewLotteryState(Enum):
        READY = 0
        TEXT = 1

    new_lottery = "Создать розыгрыш"

    def __init__(self, app: Application) -> None:
        # TODO: временное хранилище чисто для тестов надо заменить
        app.add_handler(CommandHandler("help", self.help_command))
        app.add_handler(ChatMemberHandler(self.invitation))
        app.add_handler(ConversationHandler(
            entry_points=[CommandHandler("start", self.start)],
            states={
                Bot.NewLotteryState.READY.value: [CallbackQueryHandler(self.button_handler)],
                Bot.NewLotteryState.TEXT.value: [],
            },
            fallbacks=[],
        ))
        # app.add_handler(CommandHandler("start", self.start))
        # app.add_handler()

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Send a message when the command /start is issued."""
        keyboard = [[Bot.new_lottery]]
        keyboard = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "Привет! Я помогу тебе создать розыгрыш в Telegram канале или чате! "
            "Нажимай на кнопки и следуй инструкциям:",
            reply_markup=keyboard
        )
        await self.create_channel_list_message(update, context)
        return Bot.NewLotteryState.READY.value

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send a message when the command /help is issued."""
        await update.message.reply_text("Help!")

    async def lottery_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        print("ready text")

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
                    chan = channels[channels.index({
                        "status": ChatMemberStatus.MEMBER,
                        "chat_id": chat.id,
                        "username": chat.mention_html()
                    })]
                    chan["status"] = ChatMemberStatus.ADMINISTRATOR
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
        if query.data == "ready":
            channels = context.bot_data[user.id]["channels"]
            if not all(map(lambda c: c["status"] == ChatMemberStatus.ADMINISTRATOR.value, channels)):
                await query.answer("Бот должен быть администратором во всех каналах, где он есть!",
                                   show_alert=True)
            else:
                return Bot.NewLotteryState.TEXT.value
