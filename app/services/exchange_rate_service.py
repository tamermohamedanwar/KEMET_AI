import os
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone

import requests


# السعر الاحتياطي في حالة تعطل جميع المصادر.
DEFAULT_USD_TO_EGP = Decimal("50.33")

# المصدر الرئيسي: Frankfurter باستخدام بيانات البنك المركزي المصري CBE.
CBE_RATE_URL = os.getenv(
    "USD_EGP_CBE_RATE_URL",
    "https://api.frankfurter.dev/v2/rate/USD/EGP?providers=CBE",
)

# مصدر احتياطي مستقل نسبيًا.
FRANKFURTER_RATE_URL = os.getenv(
    "USD_EGP_RATE_URL",
    "https://api.frankfurter.dev/v2/rate/USD/EGP",
)


def _parse_rate(data):
    """
    Extract and validate USD/EGP rate from Frankfurter v2 response.
    Expected:
    {
        "date": "...",
        "base": "USD",
        "quote": "EGP",
        "rate": 50.33
    }
    """
    rate = data.get("rate")

    if rate is None:
        raise ValueError("USD/EGP rate not found")

    rate = Decimal(str(rate))

    if rate <= 0:
        raise ValueError("Invalid USD/EGP rate")

    return rate


def _request_rate(url):
    response = requests.get(
        url,
        timeout=10,
        headers={
            "Accept": "application/json",
            "User-Agent": "Kemet-AI/1.0",
        },
    )

    response.raise_for_status()

    data = response.json()

    rate = _parse_rate(data)

    return {
        "rate": rate,
        "source": url,
        "provider_date": data.get("date"),
        "updated_at": datetime.now(timezone.utc),
        "fallback": False,
    }


def get_usd_to_egp():
    """
    Return the latest available USD -> EGP rate.

    Priority:
    1. Central Bank of Egypt data through Frankfurter.
    2. Frankfurter general rate.
    3. Local fallback value.

    The returned dictionary always has the same structure so callers
    do not need to know which provider supplied the rate.
    """

    # ---------------------------------------------------------
    # 1. CBE
    # ---------------------------------------------------------
    try:
        return _request_rate(CBE_RATE_URL)
    except (
        requests.RequestException,
        ValueError,
        InvalidOperation,
        TypeError,
    ):
        pass

    # ---------------------------------------------------------
    # 2. Frankfurter general source
    # ---------------------------------------------------------
    try:
        return _request_rate(FRANKFURTER_RATE_URL)
    except (
        requests.RequestException,
        ValueError,
        InvalidOperation,
        TypeError,
    ):
        pass

    # ---------------------------------------------------------
    # 3. Safe fallback
    # ---------------------------------------------------------
    return {
        "rate": DEFAULT_USD_TO_EGP,
        "source": "fallback",
        "provider_date": None,
        "updated_at": datetime.now(timezone.utc),
        "fallback": True,
    }


def convert_usd_to_egp(amount_usd):
    """
    Convert a USD amount to EGP using the latest available rate.
    """

    amount_usd = Decimal(str(amount_usd))

    if amount_usd < 0:
        raise ValueError("USD amount cannot be negative")

    result = get_usd_to_egp()

    amount_egp = (
        amount_usd * result["rate"]
    ).quantize(Decimal("0.01"))

    return {
        "usd": amount_usd,
        "egp": amount_egp,
        "rate": result["rate"],
        "source": result["source"],
        "provider_date": result["provider_date"],
        "updated_at": result["updated_at"],
        "fallback": result["fallback"],
    }
