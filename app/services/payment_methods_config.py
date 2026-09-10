"""
Kemet AI Payment Methods Configuration

Payment-method routing layer.
This file does not process or store card data.
Provider credentials remain in environment variables.
"""

PAYMENT_METHODS = {
    "egypt": {
        "currency": "EGP",
        "methods": [
            {
                "id": "card",
                "name": "Card",
                "enabled": True,
                "provider": "paymob",
            },
            {
                "id": "local",
                "name": "Local Payment Methods",
                "enabled": True,
                "provider": "paymob",
            },
        ],
    },

    "mena": {
        "currency": "USD",
        "methods": [
            {
                "id": "card",
                "name": "Visa / Mastercard",
                "enabled": True,
                "provider": "international",
            },
            {
                "id": "wallet",
                "name": "Supported Digital Wallets",
                "enabled": True,
                "provider": "international",
            },
        ],
    },

    "international": {
        "currency": "USD",
        "methods": [
            {
                "id": "card",
                "name": "Visa / Mastercard",
                "enabled": True,
                "provider": "international",
            },
            {
                "id": "wallet",
                "name": "Supported Digital Wallets",
                "enabled": True,
                "provider": "international",
            },
        ],
    },
}


MARKET_ALIASES = {
    "eg": "egypt",
    "egypt": "egypt",
    "egyptian": "egypt",

    "mena": "mena",
    "arab": "mena",
    "arabic": "mena",
    "gcc": "mena",
    "middle_east": "mena",
    "middle-east": "mena",

    "international": "international",
    "global": "international",
    "world": "international",
}


def normalize_market(market):
    value = str(market or "").strip().lower()
    return MARKET_ALIASES.get(value, "international")


def get_payment_methods(market="international"):
    market = normalize_market(market)

    return {
        "market": market,
        "currency": PAYMENT_METHODS[market]["currency"],
        "methods": [
            dict(method)
            for method in PAYMENT_METHODS[market]["methods"]
            if method.get("enabled")
        ],
    }


def get_enabled_method_ids(market="international"):
    return [
        method["id"]
        for method in get_payment_methods(market)["methods"]
    ]


def is_method_enabled(method_id, market="international"):
    return method_id in get_enabled_method_ids(market)
