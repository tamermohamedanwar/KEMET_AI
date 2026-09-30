from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WorldChannel:
    channel_id: str
    name: str
    kind: str
    monetization_paths: tuple[str, ...]


class KemetWorldsIntelligenceService:
    VERSION = "1.1"
    CHANNELS = (
        WorldChannel("youtube", "YouTube", "video", ("ads", "premium", "shopping")),
        WorldChannel("tiktok", "TikTok", "short_video", ("creator", "commerce", "affiliate")),
        WorldChannel("instagram", "Instagram", "social_video", ("creator", "subscriptions", "commerce")),
        WorldChannel("facebook", "Facebook", "social_video", ("content", "reels", "commerce")),
    )

    @classmethod
    def snapshot(cls, organization_id: int | None, world_id: str = "kemet-worlds", youtube_evidence: dict[str, Any] | None = None) -> dict[str, Any]:
        yt = youtube_evidence if youtube_evidence and youtube_evidence.get("verified") else None
        values = {"views": None, "watch_time": None, "retention_rate": None, "revenue": None,
                  "qualified_views": None, "revenue_per_1000_qualified_views": None}
        if yt:
            evidence = yt.get("evidence") or {}
            headers = evidence.get("headers") or []
            rows = evidence.get("rows") or []
            if headers and rows:
                names = [h.get("name") for h in headers]
                row = rows[0]
                for key in ("views", "estimatedMinutesWatched", "averageViewPercentage", "estimatedRevenue"):
                    if key in names:
                        value = row[names.index(key)]
                        target = {"estimatedMinutesWatched": "watch_time", "averageViewPercentage": "retention_rate", "estimatedRevenue": "revenue"}.get(key, key)
                        values[target] = value
                if values["revenue"] is not None and values["qualified_views"]:
                    values["revenue_per_1000_qualified_views"] = round(float(values["revenue"]) / float(values["qualified_views"]) * 1000, 6)
        channels = []
        for c in cls.CHANNELS:
            connected = c.channel_id == "youtube" and yt is not None
            row = {"channel_id": c.channel_id, "name": c.name, "kind": c.kind,
                   "monetization_paths": list(c.monetization_paths),
                   **({k: values[k] for k in values} if connected else {k: None for k in values}),
                   "status": "connected" if connected else "not_connected"}
            channels.append(row)
        totals = {k: values[k] for k in ("views", "qualified_views", "revenue", "retention_rate", "revenue_per_1000_qualified_views")}
        return {
            "version": cls.VERSION, "organization_id": organization_id, "world_id": world_id,
            "world_name": "Kemet Worlds", "child_worlds": ["Mendes World", "Kemet Kids", "Kemet Academy", "Kemet Stories"],
            "status": "measured" if yt else "measurement_ready", "channels": channels, "totals": totals,
            "evidence": {"source": yt.get("source") if yt else None, "verified": bool(yt), "digest": yt.get("evidence_digest") if yt else None},
            "analysis": {"primary_kpi": "revenue_per_1000_qualified_views",
                         "funnel": ["content", "publication", "views", "retention", "qualified_views", "monetization", "revenue", "learning"],
                         "causal_claims": False, "unverified_values_are_null": True},
            "governance": {"read_only": True, "tenant_scoped": True, "no_auto_publish": True, "no_payout_execution": True},
        }


kemet_worlds_intelligence_service = KemetWorldsIntelligenceService()
