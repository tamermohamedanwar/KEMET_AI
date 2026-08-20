from datetime import datetime


STATUS_SCORES = {
    "new": 10,
    "contacted": 25,
    "qualified": 50,
    "proposal": 70,
    "won": 100,
    "lost": 0,
}


def calculate_lead_score(lead):
    score = 0

    email = (lead.email or "").strip().lower()
    company = (lead.company_name or "").strip()
    message = (lead.message or "").strip()
    phone = (lead.phone or "").strip()
    source = (lead.source or "").strip().lower()
    status = (lead.status or "new").strip().lower()

    if email:
        score += 10

    if phone:
        score += 10

    if company:
        score += 10

    if len(message) >= 20:
        score += 10

    if len(message) >= 100:
        score += 10

    if source in {
        "referral",
        "website",
        "demo",
        "contact_form",
    }:
        score += 10

    score += STATUS_SCORES.get(status, 0)

    if lead.estimated_value:
        try:
            value = float(lead.estimated_value)

            if value >= 1000:
                score += 20
            elif value >= 500:
                score += 10
        except (TypeError, ValueError):
            pass

    if lead.next_follow_up_at:
        if lead.next_follow_up_at <= datetime.utcnow():
            score += 5

    return min(score, 100)


def classify_lead(score):
    if score >= 75:
        return "hot"

    if score >= 45:
        return "warm"

    return "cold"


def score_lead(lead):
    score = calculate_lead_score(lead)

    lead.lead_score = score

    return {
        "score": score,
        "temperature": classify_lead(score),
    }
