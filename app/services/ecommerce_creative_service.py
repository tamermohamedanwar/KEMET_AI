from dataclasses import dataclass
from typing import Any, Mapping


CREATIVE_OUTPUTS = (
    "listing_image",
    "model_image",
    "product_showcase",
    "interaction_scene",
    "short_video",
    "social_post",
)

SUPPORTED_CHANNELS = ("web", "instagram", "tiktok", "facebook", "whatsapp", "telegram")


@dataclass(frozen=True)
class CreativeBrief:
    product_name: str
    objective: str
    audience: str
    channel: str
    output_type: str
    language: str
    key_message: str
    constraints: tuple[str, ...]


class EcommerceCreativeService:
    VERSION = "1.0"

    def build_brief(self, product: Mapping[str, Any], *, objective="sales", audience="", channel="web", output_type="product_showcase", language="ar", style=""):
        name = str(product.get("name") or "").strip()
        if not name:
            raise ValueError("product_name_required")
        channel = str(channel or "web").strip().lower()
        output_type = str(output_type or "product_showcase").strip().lower()
        if channel not in SUPPORTED_CHANNELS:
            raise ValueError("unsupported_channel")
        if output_type not in CREATIVE_OUTPUTS:
            raise ValueError("unsupported_output_type")
        features = self._features(product)
        constraints = ["preserve_product_identity", "no_unverified_claims", "no_fake_reviews"]
        if style:
            constraints.append(f"style:{str(style).strip()[:120]}")
        key_message = self._message(product, objective, features)
        brief = CreativeBrief(name, str(objective or "sales"), str(audience or "general buyers"), channel, output_type, str(language or "ar"), key_message, tuple(constraints))
        return {
            "success": True,
            "engine": "kemet_ecommerce_creative",
            "version": self.VERSION,
            "brief": {
                "product_name": brief.product_name,
                "objective": brief.objective,
                "audience": brief.audience,
                "channel": brief.channel,
                "output_type": brief.output_type,
                "language": brief.language,
                "key_message": brief.key_message,
                "features": features,
                "constraints": list(brief.constraints),
            },
            "prompt_contract": self._prompt_contract(brief, product, features),
            "governance": self._governance(),
            "commercial": {"lead_ready": True, "revenue": "not_available", "roi": "not_proven", "causal_claim": False},
        }

    @staticmethod
    def _features(product):
        values = product.get("features") or product.get("benefits") or []
        if isinstance(values, str):
            values = [values]
        return [str(value).strip() for value in values if str(value).strip()][:8]

    @staticmethod
    def _message(product, objective, features):
        explicit = str(product.get("key_message") or product.get("description") or "").strip()
        if explicit:
            return explicit[:500]
        if features:
            return f"{objective}: {product.get('name')} — {', '.join(features[:3])}"[:500]
        return f"{objective}: {product.get('name')}"[:500]

    @staticmethod
    def _prompt_contract(brief, product, features):
        return {
            "role": "commercial_product_creative_director",
            "task": f"Create a {brief.output_type} for {brief.product_name} on {brief.channel}.",
            "audience": brief.audience,
            "language": brief.language,
            "message": brief.key_message,
            "features": features,
            "source_product_data": {"name": brief.product_name, "sku": product.get("sku")},
            "must_not": ["invent_features", "alter_brand_identity", "claim_unverified_results", "publish_without_approval"],
        }

    @staticmethod
    def _governance():
        return {"read_only": True, "advisory": True, "database_mutation": False, "external_execution": False, "auto_execute": False, "human_approval_required": True}


ecommerce_creative_service = EcommerceCreativeService()
