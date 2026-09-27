# Kemet AI

Kemet AI is a governed business/AI application. This README documents the minimum local setup and safe development workflow.

## 1. Environment

Copy `.env.example` to `.env` and replace placeholders locally. Never commit or package `.env`. In production, inject secrets through the deployment/runtime secret store.

## 2. Install runtime dependencies

```bash
python -m pip install -r requirements.txt
```

## 3. Install development/test dependencies

```bash
python -m pip install -r requirements-dev.txt
```

## 4. Run tests

```bash
pytest -q
```

For coverage:

```bash
pytest --cov=app --cov-report=term-missing
```

## 5. Run locally

```bash
python app.py
```

The application reads `FLASK_ENV`, `DEBUG`, and `KEMET_PRODUCTION`; production mode always disables Flask debug. For production deployment, use the existing `wsgi.py`/WSGI server path rather than the development server.

## 6. Clean review package

Run `bash ops/build_review_package.sh` (or execute the script directly on a standard Linux host). It excludes real environment files, virtual environments, databases, caches, logs, generated uploads/media, model binaries, and known backup artifacts.
