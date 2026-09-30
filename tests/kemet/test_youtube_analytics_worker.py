import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKER = ROOT / "ops" / "youtube_worker" / "analytics.mjs"
AUTHORIZE = ROOT / "ops" / "youtube_worker" / "authorize.mjs"


def test_youtube_analytics_worker_simulation_is_read_only():
    result = subprocess.run(
        ["node", str(WORKER), "--simulate", "--start", "2026-09-01", "--end", "2026-09-14"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout.strip())
    assert payload["mode"] == "simulate"
    assert payload["read_only"] is True


def test_youtube_authorization_requests_analytics_scopes():
    text = AUTHORIZE.read_text(encoding="utf-8")
    assert "youtube.readonly" in text
    assert "yt-analytics.readonly" in text
    assert "yt-analytics-monetary.readonly" in text


def test_youtube_analytics_worker_uses_egp_and_verified_source_contract():
    text = WORKER.read_text(encoding="utf-8")
    assert 'currency: "EGP"' in text
    assert 'verified_source: true' in text
    assert 'read_only: true' in text


def test_youtube_analytics_worker_does_not_publish():
    text = WORKER.read_text(encoding="utf-8")
    assert "videos.insert" not in text
    assert "youtube_publish" not in text
