from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RevenueChannel:
    channel_id: str
    name: str
    category: str
    monetization: tuple[str, ...]
    payout_provider: str
    currency: str = "EGP"


class RevenueCollectionService:
    VERSION = "1.1"

    CHANNELS = (
        RevenueChannel("youtube", "YouTube", "video", ("ads", "premium", "shopping"), "AdSense for YouTube"),
        RevenueChannel("tiktok", "TikTok", "video", ("creator", "commerce", "affiliate"), "TikTok payout"),
        RevenueChannel("instagram", "Instagram", "social", ("creator", "subscriptions", "commerce"), "Meta payout"),
        RevenueChannel("facebook", "Facebook", "social", ("content", "reels", "commerce"), "Meta payout"),
        RevenueChannel("affiliate", "Affiliate", "commerce", ("commission",), "Affiliate network"),
        RevenueChannel("marketplace", "Kemet Marketplace", "commerce", ("sales", "fees", "commission"), "Kemet payment provider"),
    )

    @classmethod
    def snapshot(cls, organization_id: int | None, youtube_evidence: dict[str, Any] | None = None) -> dict[str, Any]:
        channels = []
        yt = youtube_evidence if youtube_evidence and youtube_evidence.get("verified") else None
        yt_revenue = None
        if yt:
            evidence = yt.get("evidence") or {}
            headers = evidence.get("headers") or []
            rows = evidence.get("rows") or []
            if headers and rows:
                names = [h.get("name") for h in headers]
                row = rows[0]
                if "estimatedRevenue" in names:
                    yt_revenue = row[names.index("estimatedRevenue")]
        for channel in cls.CHANNELS:
            connected = channel.channel_id == "youtube" and yt is not None
            channels.append({
                "channel_id": channel.channel_id,
                "name": channel.name,
                "category": channel.category,
                "monetization": list(channel.monetization),
                "payout_provider": channel.payout_provider,
                "currency": channel.currency,
                "connection_status": "connected" if connected else "not_configured",
                "monetization_status": "measured" if connected else "unknown",
                "balance": None,
                "pending_payout": None,
                "next_payout": None,
                "payout_destination": "not_configured",
                "last_sync": (evidence.get("timestamp") if yt else None),
                "evidence_digest": yt.get("evidence_digest") if connected else None,
                "action": "Measured from verified YouTube Analytics" if connected else "Connect account and verify monetization eligibility",
            })
        return {
            "version": cls.VERSION,
            "organization_id": organization_id,
            "currency": "EGP",
            "total_balance": None,
            "pending_payout": None,
            "verified_revenue": yt_revenue if yt else None,
            "status": "live" if yt else "setup_required",
            "channels": channels,
            "evidence": {
                "source": yt.get("source") if yt else None,
                "verified": bool(yt),
                "digest": yt.get("evidence_digest") if yt else None,
            },
            "governance": {
                "read_only": True,
                "tenant_scoped": True,
                "no_payout_execution": True,
                "no_credentials_exposed": True,
                "no_balance_fabrication": True,
            },
        }


revenue_collection_service = RevenueCollectionService()
