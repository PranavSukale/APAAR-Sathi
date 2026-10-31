import os

os.environ.setdefault("SERVERLESS", "1")

from backend.app.main import app  # noqa: E402

# Vercel's Python runtime serves this ASGI `app`.
