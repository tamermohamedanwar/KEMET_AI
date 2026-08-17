from app.automation.engine import engine

engine.register({
    "name": "New Chat Message",
    "event": "message_received",
    "action": "generate_ai_reply"
})

engine.register({
    "name": "Conversation Logger",
    "event": "message_received",
    "action": "save_to_database"
})

engine.register({
    "name": "Notification",
    "event": "message_received",
    "action": "send_notification"
})
