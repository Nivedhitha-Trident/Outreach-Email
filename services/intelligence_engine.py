import json
from datetime import datetime
from graphs.intelligence_graph import run_lead_intelligence
from store import save_analysis, get_analysis
from services.llm_service import invoke_llm


def analyze_lead(lead: dict, force_refresh: bool = False) -> dict:
    lead_id = lead.get("id", "")

    if not force_refresh:
        existing_analysis = get_analysis(lead_id, "full_intelligence")
        existing_pain = get_analysis(lead_id, "pain_points")
        existing_opps = get_analysis(lead_id, "opportunities")
        existing_web = get_analysis(lead_id, "web_context") or ""

        if existing_analysis and existing_pain:
            pain_points = _safe_json_load(existing_pain, [])
            opportunities = _safe_json_load(existing_opps, [])
            return {
                "business_analysis": existing_analysis,
                "pain_points": pain_points,
                "opportunities": opportunities,
                "web_context": existing_web,
                "from_cache": True,
                "lead_id": lead_id,
            }

    result = run_lead_intelligence(lead)

    business_analysis = result.get("business_analysis", "")
    pain_points = result.get("pain_points", [])
    opportunities = result.get("opportunities", [])
    web_context = result.get("web_context", "")

    if business_analysis:
        save_analysis(lead_id, "full_intelligence", business_analysis)
    if pain_points:
        save_analysis(lead_id, "pain_points", json.dumps(pain_points))
    if opportunities:
        save_analysis(lead_id, "opportunities", json.dumps(opportunities))
    if web_context:
        save_analysis(lead_id, "web_context", web_context)

    return {
        "business_analysis": business_analysis,
        "pain_points": pain_points,
        "opportunities": opportunities,
        "web_context": web_context,
        "errors": result.get("errors", []),
        "completed_steps": result.get("completed_steps", []),
        "from_cache": False,
        "lead_id": lead_id,
    }



def get_intelligence_summary(lead: dict, analysis: dict) -> dict:
    pain_points = analysis.get("pain_points", [])
    opportunities = analysis.get("opportunities", [])

    high_pain = [p for p in pain_points if p.get("severity") == "high"]
    immediate_opps = [o for o in opportunities if o.get("urgency") == "immediate"]

    business_analysis = analysis.get("business_analysis", "")
    ai_readiness = _infer_ai_readiness(business_analysis)
    maturity = _infer_business_maturity(lead, business_analysis)

    return {
        "total_pain_points": len(pain_points),
        "high_severity_pain": len(high_pain),
        "opportunities_count": len(opportunities),
        "immediate_opportunities": len(immediate_opps),
        "ai_readiness": ai_readiness,
        "business_maturity": maturity,
        "top_pain_areas": [p.get("area", "") for p in pain_points[:3]],
        "top_opportunity": opportunities[0].get("title", "") if opportunities else "",
    }


def _infer_ai_readiness(analysis_text: str) -> str:
    text_lower = analysis_text.lower()
    if any(w in text_lower for w in ["ai", "machine learning", "automation", "digital native", "tech-forward"]):
        return "High"
    elif any(w in text_lower for w in ["scaling", "growth", "modernizing", "upgrading", "transformation"]):
        return "Medium"
    else:
        return "Developing"


def _infer_business_maturity(lead: dict, analysis: str) -> str:
    size = lead.get("company_size", "").lower()
    if any(s in size for s in ["1000", "500", "enterprise", "large"]):
        return "Enterprise"
    elif any(s in size for s in ["200", "100", "mid", "medium"]):
        return "Mid-Market"
    elif any(s in size for s in ["50", "small", "startup", "smb"]):
        return "Growth Stage"
    return "Mid-Market"


def _safe_json_load(text: str, default):
    if not text:
        return default
    try:
        return json.loads(text)
    except Exception:
        return default
