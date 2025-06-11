import firebase_admin
from firebase_admin import credentials, db


class FirebaseClient:
    def __init__(self, firebase_url: str, secret: str) -> None:
        """
        firebase_url: Firebase Runtime DB URL.
        secret: Firebase Runtime DB secret.
        """
        cred = credentials.Certificate(secret)
        firebase_admin.initialize_app(cred, {"databaseURL": firebase_url})
        self.db = db


    async def write(self, path: str, data: int|dict|str|object) -> None:
        self.db.reference(path).set(data)


    async def update(self, path: str, data: dict) -> None:
        self.db.reference(path).update(data)


    async def read(self, path: str) -> object|str|int|dict|None:
        return self.db.reference(path).get()


    async def delete(self, path: str) -> None:
        self.db.reference(path).delete()


    async def get_user_channels(self, user_id: int) -> list:
        data = await self.read(f"users/{user_id}/channels")
        return data if isinstance(data, list) else []

    async def set_user_channels(self, user_id: int, channels: list) -> None:
        if isinstance(channels, list):
            await self.write(f"users/{user_id}/channels", channels)
        else:
            raise TypeError("channels must be a list")
