import json
from typing import TypedDict, Optional, Any
from langgraph.graph import StateGraph, END
from services.llm_service import invoke_llm, invoke_llm_json
from services.chroma_manager import semantic_search, format_search_results_as_context
from services.memory_service import (
    recall_industry_context, recall_relevant_solutions, recall_case_studies,
    store_lead_intelligence, store_ai_insight
)
from config.settings import COLLECTIONS
from prompts.templates import (
    BUSINESS_INTELLIGENCE_PROMPT,
    PAIN_POINT_EXTRACTION_PROMPT,
    OPPORTUNITY_MAPPING_PROMPT,
)


class LeadIntelligenceState(TypedDict):
    lead_data: dict
    web_context: str
    industry_context: str
    solutions_context: str
    business_analysis: str
    pain_points: list
    opportunities: list
    raw_pain_points_text: str
    errors: list
    completed_steps: list


def _lead_to_text(lead: dict) -> str:
    designation = lead.get('designation') or lead.get('title', 'Unknown')
    return f"""Name: {lead.get('name', 'Unknown')}
Designation: {designation}
Company: {lead.get('company', 'Unknown')}
Industry: {lead.get('industry', 'Unknown')}
Company Size: {lead.get('company_size', 'Unknown')}
Location: {lead.get('location', 'Unknown')}
Website: {lead.get('website', 'N/A')}
Existing Services: {lead.get('existing_services', 'Unknown')}
Portfolio: {lead.get('portfolio', 'N/A')}
Revenue: {lead.get('revenue', 'Unknown')}
Notes: {lead.get('notes', 'None')}"""


def web_enrich_node(state: LeadIntelligenceState) -> LeadIntelligenceState:
    from services.web_enrichment import enrich_lead
    lead = state["lead_data"]
    try:
        web_ctx = enrich_lead(lead)
    except Exception as e:
        web_ctx = ""
        return {**state, "web_context": web_ctx,
                "errors": state.get("errors", []) + [f"Web enrichment error: {e}"],
                "completed_steps": state.get("completed_steps", []) + ["web_enriched"]}
    return {
        **state,
        "web_context": web_ctx,
        "completed_steps": state.get("completed_steps", []) + ["web_enriched"],
    }


def retrieve_context_node(state: LeadIntelligenceState) -> LeadIntelligenceState:
    lead = state["lead_data"]
    industry = lead.get("industry", "")
    company = lead.get("company", "")
    role = lead.get("designation") or lead.get("title", "")

    industry_query = f"{industry} enterprise challenges digital transformation operational pain points {role}"
    industry_ctx = recall_industry_context(industry, industry_query)

    solutions_query = f"{industry} automation workflow intelligence data operations {company}"
    solutions_ctx = recall_relevant_solutions(solutions_query)

    return {
        **state,
        "industry_context": industry_ctx,
        "solutions_context": solutions_ctx,
        "completed_steps": state.get("completed_steps", []) + ["context_retrieved"],
    }


def analyze_business_node(state: LeadIntelligenceState) -> LeadIntelligenceState:
    lead = state["lead_data"]
    lead_text = _lead_to_text(lead)

    web_ctx = state.get("web_context", "")
    web_section = f"\n\nWEB RESEARCH (Wikipedia + DuckDuckGo — verified against lead details):\n{web_ctx}" if web_ctx else ""

    prompt = BUSINESS_INTELLIGENCE_PROMPT.format(
        lead_data=lead_text + web_section,
        industry_context=state.get("industry_context", "No specific industry context available."),
        solutions_context=state.get("solutions_context", "No solutions context available."),
    )

    try:
        analysis = invoke_llm(prompt, temperature=0.6, max_tokens=2000)
    except Exception as e:
        analysis = f"Analysis unavailable due to error: {e}"
        return {**state, "business_analysis": analysis, "errors": state.get("errors", []) + [str(e)]}

    return {
        **state,
        "business_analysis": analysis,
        "completed_steps": state.get("completed_steps", []) + ["business_analyzed"],
    }


def extract_pain_points_node(state: LeadIntelligenceState) -> LeadIntelligenceState:
    analysis = state.get("business_analysis", "")
    if not analysis or "unavailable" in analysis.lower():
        return {**state, "pain_points": [], "raw_pain_points_text": ""}

    prompt = PAIN_POINT_EXTRACTION_PROMPT.format(analysis=analysis)

    try:
        result = invoke_llm_json(prompt, temperature=0.3)
        if result and "pain_points" in result:
            pain_points = result["pain_points"]
        else:
            pain_points = _fallback_pain_points(analysis)
    except Exception as e:
        pain_points = _fallback_pain_points(analysis)

    raw_text = "\n".join([
        f"- {pp.get('area', '')}: {pp.get('description', '')}"
        for pp in pain_points
    ])

    return {
        **state,
        "pain_points": pain_points,
        "raw_pain_points_text": raw_text,
        "completed_steps": state.get("completed_steps", []) + ["pain_points_extracted"],
    }


def _fallback_pain_points(analysis: str) -> list:
    lines = [l.strip() for l in analysis.split("\n") if l.strip().startswith("-") or l.strip().startswith("•")]
    pain_points = []
    for line in lines[:6]:
        clean = line.lstrip("-•").strip()
        if len(clean) > 20:
            pain_points.append({
                "area": "Operational",
                "description": clean,
                "severity": "medium",
                "impact": "Business efficiency and productivity"
            })
    return pain_points or [{"area": "General", "description": "Operational efficiency improvement needed", "severity": "medium", "impact": "Cost and productivity"}]


def map_opportunities_node(state: LeadIntelligenceState) -> LeadIntelligenceState:
    pain_points_text = state.get("raw_pain_points_text", "")
    business_analysis = state.get("business_analysis", "")
    solutions_ctx = state.get("solutions_context", "")

    if not business_analysis:
        return {**state, "opportunities": []}

    prompt = OPPORTUNITY_MAPPING_PROMPT.format(
        business_analysis=business_analysis,
        pain_points=pain_points_text,
        solutions_context=solutions_ctx,
    )

    try:
        result = invoke_llm_json(prompt, temperature=0.5)
        if result and "opportunities" in result:
            opportunities = result["opportunities"]
        else:
            opportunities = _fallback_opportunities(business_analysis)
    except Exception as e:
        opportunities = _fallback_opportunities(business_analysis)

    return {
        **state,
        "opportunities": opportunities,
        "completed_steps": state.get("completed_steps", []) + ["opportunities_mapped"],
    }


def _fallback_opportunities(analysis: str) -> list:
    return [
        {
            "title": "Process Automation",
            "description": "Automate repetitive operational workflows",
            "solution_fit": "Workflow automation platform",
            "roi_potential": "20-40% efficiency gain",
            "urgency": "short-term",
            "transformation_impact": "Significant reduction in manual work"
        }
    ]


def store_intelligence_node(state: LeadIntelligenceState) -> LeadIntelligenceState:
    lead = state["lead_data"]
    lead_id = lead.get("id", "unknown")

    intelligence = {
        "business_analysis": state.get("business_analysis", ""),
        "pain_points": state.get("pain_points", []),
        "opportunities": state.get("opportunities", []),
    }

    try:
        store_lead_intelligence(lead_id, lead, intelligence)
        store_ai_insight(
            lead_id,
            "full_intelligence",
            state.get("business_analysis", ""),
            metadata={"company": lead.get("company", ""), "industry": lead.get("industry", "")},
        )
    except Exception as e:
        return {**state, "errors": state.get("errors", []) + [f"Memory storage error: {e}"]}

    return {
        **state,
        "completed_steps": state.get("completed_steps", []) + ["intelligence_stored"],
    }


def build_intelligence_graph():
    builder = StateGraph(LeadIntelligenceState)

    builder.add_node("web_enrich",       web_enrich_node)
    builder.add_node("retrieve_context", retrieve_context_node)
    builder.add_node("analyze_business", analyze_business_node)
    builder.add_node("extract_pain_points", extract_pain_points_node)
    builder.add_node("map_opportunities", map_opportunities_node)
    builder.add_node("store_intelligence", store_intelligence_node)

    builder.set_entry_point("web_enrich")
    builder.add_edge("web_enrich",       "retrieve_context")
    builder.add_edge("retrieve_context", "analyze_business")
    builder.add_edge("analyze_business", "extract_pain_points")
    builder.add_edge("extract_pain_points", "map_opportunities")
    builder.add_edge("map_opportunities", "store_intelligence")
    builder.add_edge("store_intelligence", END)

    return builder.compile()


_intelligence_graph = None


def get_intelligence_graph():
    global _intelligence_graph
    if _intelligence_graph is None:
        _intelligence_graph = build_intelligence_graph()
    return _intelligence_graph


def run_lead_intelligence(lead: dict) -> dict:
    graph = get_intelligence_graph()
    initial_state = LeadIntelligenceState(
        lead_data=lead,
        web_context="",
        industry_context="",
        solutions_context="",
        business_analysis="",
        pain_points=[],
        opportunities=[],
        raw_pain_points_text="",
        errors=[],
        completed_steps=[],
    )
    result = graph.invoke(initial_state)
    return result
