import json
from store import save_outreach, save_analysis, get_analysis
from services.llm_service import invoke_llm, stream_llm
from services.memory_service import recall_case_studies, store_outreach
from services.chroma_manager import semantic_search, format_search_results_as_context
from config.settings import COLLECTIONS, ROLE_TIERS
from config.knowledge_base import TRIDENT_INTRO
from prompts.templates import PERSONALIZED_EMAIL_PROMPT


def classify_role(designation: str) -> str:
    if not designation:
        return "professional"
    d = designation.lower()
    for tier, keywords in ROLE_TIERS.items():
        if any(k in d for k in keywords):
            return tier
    return "professional"


def role_profile_text(designation: str) -> str:
    tier = classify_role(designation or "")
    profiles = {
        "c_suite":   "C-Suite executive. Cares about vision, revenue impact, competitive advantage, and company-wide ROI. Has final decision authority. Time-poor, skeptical of pitches, responds to strategic thinking.",
        "vp_dir":    "VP/Director level. Owns a function and budget. Cares about hitting targets, team efficiency, and looking good to leadership. Evaluates solutions on outcomes and ease of implementation.",
        "manager":   "Manager/Team Lead. Deals with execution, coordination, and reporting. Cares about saving time, reducing manual work, and getting team results. May not have budget authority alone.",
        "technical": "Technical professional (developer/engineer/architect). Cares about how things work, integration ease, scalability, and not creating more problems. Skeptical of hype, responds to specifics.",
        "hr":        "HR/People professional. Cares about talent outcomes, employee experience, compliance, and reducing administrative burden. Measures success in human terms.",
        "marketing": "Marketing professional. Cares about leads, brand, campaign performance, and data-driven decisions. Familiar with tools and quickly evaluates ROI on marketing spend.",
        "sales":     "Sales/BD professional. Cares about pipeline, close rates, and revenue. Values tools that directly impact numbers and compress sales cycles.",
        "professional": "Professional. Focus on their functional role, efficiency, and delivering results in their domain.",
    }
    return profiles.get(tier, profiles["professional"])


def _build_context(lead: dict, analysis: dict) -> dict:
    pain_points = analysis.get("pain_points", [])
    if isinstance(pain_points, list) and pain_points:
        if isinstance(pain_points[0], dict):
            pain_text = "\n".join(
                f"- {p.get('area','')}: {p.get('description','')}" for p in pain_points[:6]
            )
        else:
            pain_text = "\n".join(f"- {p}" for p in pain_points[:6])
    else:
        pain_text = analysis.get("business_analysis", "")[:400]

    industry    = lead.get("industry", "")
    designation = lead.get("designation") or lead.get("title", "")
    company     = lead.get("company", "")
    existing    = lead.get("existing_services", "")

    search_q = f"{industry} {designation} {company} {existing} challenges automation transformation"
    sol_results = semantic_search(COLLECTIONS["solutions_kb"], search_q, n_results=5)
    cs_results  = semantic_search(COLLECTIONS["case_studies"],  search_q, n_results=3)
    solutions_text    = format_search_results_as_context(sol_results, max_tokens=900)
    case_studies_text = format_search_results_as_context(cs_results,  max_tokens=600)

    return {
        "name":              lead.get("name", "there"),
        "designation":       designation or "Professional",
        "company":           company or "your company",
        "industry":          industry or "your industry",
        "company_size":      lead.get("company_size", ""),
        "website":           lead.get("website", "N/A"),
        "existing_services": existing or "Not specified",
        "portfolio":         lead.get("portfolio", "N/A"),
        "notes":             lead.get("notes", "N/A"),
        "role_profile":      role_profile_text(designation),
        "pain_points":       pain_text or "operational efficiency and growth challenges",
        "solutions":         solutions_text or "our enterprise solutions portfolio",
        "case_studies":      case_studies_text or "Available on request",
        "business_analysis": analysis.get("business_analysis", "")[:800],
        "company_intro":     TRIDENT_INTRO,
    }


def generate_output(
    lead: dict,
    analysis: dict,
    output_type: str = "personalized_email",
    stream: bool = False,
    force_refresh: bool = False,
):
    lead_id = lead.get("id", "")

    if not force_refresh and lead_id:
        cached = get_analysis(lead_id, f"output_{output_type}")
        if cached:
            if stream:
                def _cached():
                    yield cached
                return _cached()
            return cached

    ctx    = _build_context(lead, analysis)
    prompt = PERSONALIZED_EMAIL_PROMPT.format(**ctx, email_type="strategic cold outreach")

    if stream:
        def _gen():
            full = ""
            for chunk in stream_llm(prompt):
                full += chunk
                yield chunk
            _persist(lead, output_type, full)
        return _gen()
    else:
        content = invoke_llm(prompt, temperature=0.7, max_tokens=1200)
        _persist(lead, output_type, content)
        return content


def _persist(lead: dict, output_type: str, content: str):
    lead_id = lead.get("id", "")
    if not lead_id or not content:
        return
    subject, body = "", content
    if "Subject:" in content:
        for i, line in enumerate(content.split("\n")):
            if line.strip().lower().startswith("subject:"):
                subject = line.split(":", 1)[1].strip()
                body = "\n".join(content.split("\n")[i + 1:]).strip()
                break
    save_outreach(lead_id, output_type, subject, body, platform="email")
    store_outreach(lead_id, output_type, content,
                   metadata={"company": lead.get("company", ""), "name": lead.get("name", "")})
    save_analysis(lead_id, f"output_{output_type}", content)
