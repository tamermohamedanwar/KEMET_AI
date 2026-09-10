KEMET AI — FINAL HANDOFF

PROJECT:
Kemet AI Business Operating System

APPLICATION:
Flask

PYTHON:
3.11.x

ACTIVE UI:
app/static/css/kemet-ui.css
app/static/js/kemet-ui.js

LEGACY UI:
archive/ui_legacy/

DATABASE:
instance/supportai.db
instance/rag.db

DEPLOYMENT:
Procfile
gunicorn.conf.py
run_production.sh

IMPORTANT:
Database migration is deferred.
Production deployment is deferred.
Final testing is performed separately at the final gate.

DO NOT DELETE:
instance/supportai.db
instance/rag.db

DO NOT RESTORE:
Legacy UI files into active static paths unless explicitly required.

ACTIVE UI ARCHITECTURE:
kemet-ui.css
kemet-ui.js
