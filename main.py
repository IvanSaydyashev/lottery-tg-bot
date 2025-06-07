from bot.bot import Bot
from dotenv import load_dotenv
import os
import logging

from telegram import Update
from telegram.ext import Application, DictPersistence

from services.firebase import FirebaseClient

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def main() -> None:
    load_dotenv()
    firebase = FirebaseClient(os.getenv("FIREBASE_URL"), os.getenv("FIREBASE_SECRET"))
    app = Application.builder().token(os.getenv("TOKEN")).persistence(DictPersistence()).build()
    Bot(app, firebase)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
