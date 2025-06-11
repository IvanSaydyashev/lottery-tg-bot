from telegram.ext import ContextTypes

from services.firebase import FirebaseClient


class Randomiser:
    def __init__(self, firebase: FirebaseClient):
        self.firebase_db = firebase

    async def generate_result(self, context: ContextTypes.DEFAULT_TYPE):
        job = context.job
        data = job.data
        owner_id, lottery_id = data["owner_id"], data["lottery_id"]
        self.get_result(context)
        await self.firebase_db.delete(f"lotteries/{owner_id}/{lottery_id}")

    async def check_lottery_count(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        job = context.job
        data = job.data
        owner_id, lottery_id = data["owner_id"], data["lottery_id"]
        goal_participants = data["goal_participants"]

        participants = await self.firebase_db.read(
            f"lotteries/{owner_id}/{lottery_id}/participants") or []

        if len(participants) >= goal_participants:
            context.job.schedule_removal()
            self.get_result(context)
            await self.firebase_db.delete(f"lotteries/{owner_id}/{lottery_id}")

    def get_result(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        pass
