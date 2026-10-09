from datetime import datetime
import pytz
from app.config import settings

def get_now() -> datetime:
    if settings.DEMO_NOW:
        return datetime.fromisoformat(settings.DEMO_NOW)
    return datetime.now(pytz.timezone('Asia/Kolkata')).replace(tzinfo=None)
