import time
import random

from telegram.ext import ContextTypes
from services.firebase import FirebaseClient


class Randomiser:
    def __init__(self, firebase: FirebaseClient):
        self.firebase_db = firebase

    async def date_result(self, context: ContextTypes.DEFAULT_TYPE):
        data = context.job.data
        owner_id, lottery_id = data["owner_id"], data["lottery_id"]
        await self.get_result(context)
        await self.firebase_db.delete(f"lotteries/{owner_id}/{lottery_id}")

    async def check_lottery_count(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        data = context.job.data
        owner_id, lottery_id = data["owner_id"], data["lottery_id"]
        goal_participants = data["goal_participants"]

        participants = await self.firebase_db.read(
            f"lotteries/{owner_id}/{lottery_id}/participants") or []

        if len(participants) >= goal_participants:
            await self.get_result(context)
            context.job.schedule_removal()
            await self.firebase_db.delete(f"lotteries/{owner_id}/{lottery_id}")

    async def get_result(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        data = context.job.data
        owner_id, lottery_id = data["owner_id"], data["lottery_id"]
        publisher_chat_id = data["publisher_chat_id"]
        participants = await self.firebase_db.read(f"lotteries/{owner_id}/{lottery_id}/participants")
        if not participants:
            await context.bot.send_message(chat_id=publisher_chat_id, text="No one participated")
            return

        num_winners = data["num_winners"]
        random.seed(time.time())
        winners = random.choices(participants, k=num_winners) if num_winners < len(participants) else participants
        await context.bot.send_message(chat_id=publisher_chat_id,
                                       text=f"Победители розыгрыша:\n"
                                            f"{'\n'.join([f'@{winner}' for winner in winners.values()])}")