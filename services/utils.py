import base64
import json

def encode_payload(user_id: int, lottery_uuid: str) -> str:
    payload = {
        "user_id": user_id,
        "lottery_id": lottery_uuid
    }
    json_str = json.dumps(payload, separators=(',', ':'))  # компактнее
    encoded = base64.urlsafe_b64encode(json_str.encode()).decode().rstrip("=")
    return encoded


def decode_payload(encoded: str) -> dict:
    padded = encoded + '=' * ((4 - len(encoded) % 4) % 4)
    json_str = base64.urlsafe_b64decode(padded).decode()
    return json.loads(json_str)