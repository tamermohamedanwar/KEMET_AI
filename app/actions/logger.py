from app.actions import register
from datetime import datetime

@register("log_message")
def log_message(**kwargs):
    print(
        f"[{datetime.utcnow().isoformat()}] "
        f"user={kwargs.get('user_id')} "
        f"message={kwargs.get('message')}"
    )
    return {"status": "success"}
