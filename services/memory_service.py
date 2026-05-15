import json
from datetime import datetime, timezone
from services.chroma_manager import upsert_document, semantic_search, format_search_results_as_context
from config.settings import COLLECTIONS


def store_lead_intelligence(lead_id: str, lead_data: dict, intelligence: dict):
    company = lead_data.get("company", "Unknown")
    name = lead_data.get("name", "")
    industry = lead_data.get("industry", "")

    summary = f"""Company: {company}
Contact: {name} - {lead_data.get('title', '')}
Industry: {industry}
Size: {lead_data.get('company_size', 'Unknown')}

Business Analysis:
{intelligence.get('business_analysis', '')}

Pain Points:
{json.dumps(intelligence.get('pain_points', []), indent=2)}

Opportunities:
{json.dumps(intelligence.get('opportunities', []), indent=2)}
"""

    upsert_document(
        collection_name=COLLECTIONS["lead_memory"],
        text=summary,
        metadata={
            "lead_id": lead_id,
            "company": company,
            "industry": industry,
            "name": name,
            "type": "lead_intelligence",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        doc_id=f"lead_intel_{lead_id}",
    )


def store_company_intelligence(lead_id: str, company: str, intelligence_text: str, metadata: dict = None):
    upsert_document(
        collection_name=COLLECTIONS["company_intelligence"],
        text=intelligence_text,
        metadata={
            "lead_id": lead_id,
            "company": company,
            "type": "company_intel",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **(metadata or {}),
        },
        doc_id=f"company_intel_{lead_id}",
    )


def store_ai_insight(lead_id: str, insight_type: str, content: str, metadata: dict = None):
    upsert_document(
        collection_name=COLLECTIONS["ai_generated_insights"],
        text=content,
        metadata={
            "lead_id": lead_id,
            "insight_type": insight_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **(metadata or {}),
        },
        doc_id=f"{insight_type}_{lead_id}",
    )


def store_outreach(lead_id: str, outreach_type: str, content: str, metadata: dict = None):
    upsert_document(
        collection_name=COLLECTIONS["outreach_memory"],
        text=content,
        metadata={
            "lead_id": lead_id,
            "outreach_type": outreach_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **(metadata or {}),
        },
        doc_id=f"outreach_{outreach_type}_{lead_id}",
    )


def recall_lead_context(lead_id: str, query: str) -> str:
    results = semantic_search(
        COLLECTIONS["lead_memory"],
        query=query,
        n_results=3,
        where={"lead_id": lead_id},
    )
    if not results:
        results = semantic_search(COLLECTIONS["lead_memory"], query=query, n_results=3)
    return format_search_results_as_context(results)


def recall_industry_context(industry: str, query: str = None) -> str:
    search_query = query or f"{industry} industry challenges operations transformation"
    results = semantic_search(COLLECTIONS["industry_knowledge"], search_query, n_results=5)
    kb_results = semantic_search(COLLECTIONS["solutions_kb"], search_query, n_results=3)
    all_results = sorted(results + kb_results, key=lambda x: x["relevance"], reverse=True)
    return format_search_results_as_context(all_results[:6])


def recall_relevant_solutions(pain_points_text: str) -> str:
    results = semantic_search(COLLECTIONS["solutions_kb"], pain_points_text, n_results=5)
    return format_search_results_as_context(results)


def recall_case_studies(context: str) -> str:
    results = semantic_search(COLLECTIONS["case_studies"], context, n_results=4)
    return format_search_results_as_context(results)


def recall_for_chat(query: str, leads_context: str = "") -> str:
    collections_to_search = [
        COLLECTIONS["lead_memory"],
        COLLECTIONS["solutions_kb"],
        COLLECTIONS["case_studies"],
        COLLECTIONS["ai_generated_insights"],
        COLLECTIONS["industry_knowledge"],
    ]
    all_results = []
    for cname in collections_to_search:
        results = semantic_search(cname, query, n_results=3)
        for r in results:
            r["collection"] = cname
        all_results.extend(results)
    all_results.sort(key=lambda x: x["relevance"], reverse=True)
    top_results = all_results[:8]
    return format_search_results_as_context(top_results)


def get_historical_insights(company: str) -> str:
    query = f"{company} analysis intelligence recommendations"
    results = semantic_search(COLLECTIONS["ai_generated_insights"], query, n_results=3)
    company_results = semantic_search(COLLECTIONS["company_intelligence"], query, n_results=2)
    all_results = sorted(results + company_results, key=lambda x: x["relevance"], reverse=True)
    return format_search_results_as_context(all_results[:4])
