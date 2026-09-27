from app.services.lead_intelligence_service import lead_intelligence_service


def calculate_lead_score(lead):
    result = lead_intelligence_service.analyze(lead, persist=False)
    return float(result["scoring"]["score"])


def classify_lead(score):
    if score >= 75:
        return "hot"
    if score >= 45:
        return "warm"
    return "cold"


def score_lead(lead, persist=False):
    result = lead_intelligence_service.analyze(lead, persist=persist)
    score = int(round(result["scoring"]["score"]))
    lead.lead_score = score
    return {
        "score": score,
        "temperature": result["scoring"]["temperature"],
        "confidence": result["qualification"]["confidence"],
        "qualification": result["qualification"],
        "evidence_digest": result["evidence_digest"],
        "evidence": result["scoring"]["evidence"],
        "method": result["scoring"]["method"],
    }
