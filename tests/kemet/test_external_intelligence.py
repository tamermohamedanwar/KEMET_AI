import pytest

from app.core.federation.external_intelligence import ExternalIntelligence


def test_catalog_covers_global_source_channels_without_credentials():
    catalog = {item["source_id"]: item for item in ExternalIntelligence().catalog()}
    assert {"web", "twitter", "reddit", "youtube", "github", "bilibili", "xiaohongshu", "douyin", "wechat", "linkedin", "bosszhipin", "rss"} <= set(catalog)
    assert catalog["web"]["auth_required"] is False
    assert catalog["twitter"]["auth_required"] is True


def test_private_or_local_urls_are_blocked():
    service = ExternalIntelligence()
    assert service._public_url("http://127.0.0.1:8000") is False
    assert service._public_url("http://localhost:8000") is False


def test_invalid_source_fails_closed():
    with pytest.raises(ValueError, match="source_not_implemented"):
        ExternalIntelligence().read("linkedin", query="Kemet AI")
