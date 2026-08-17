from pathlib import Path

env_file = Path(".env")

if env_file.exists():
    print("Configuration already exists")
else:
    env_file.write_text(
"""SECRET_KEY=change_this_secret_key
AI_PROVIDER=openrouter
OPENROUTER_API_KEY=
DATABASE_URL=sqlite:///supportai.db
DEBUG=False
"""
    )
    print("Configuration file created")
