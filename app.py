import os
from app import create_app

app = create_app()

if __name__ == "__main__":
    production = (
        os.getenv("FLASK_ENV", "development").strip().lower() == "production"
        or os.getenv("KEMET_PRODUCTION", "").strip().lower() in {"1", "true", "yes", "on"}
    )
    debug = bool(app.config.get("DEBUG", False)) and not production
    app.run(host="0.0.0.0", port=5000, debug=debug)
