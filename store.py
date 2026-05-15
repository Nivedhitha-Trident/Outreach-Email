import uuid

# All data lives in memory and is cleared on app restart
_leads: dict = {}
_analyses: dict = {}      # (lead_id, analysis_type) -> content
_outreach: dict = {}      # lead_id -> list[dict]
_kb_docs: dict = {}       # doc_id -> dict
_scores: dict = {}        # lead_id -> dict


def init_db():
    pass


def upsert_lead(lead: dict) -> str:
    _leads[lead["id"]] = lead
    return lead["id"]


def get_all_leads() -> list[dict]:
    return list(_leads.values())


def get_lead(lead_id: str) -> dict | None:
    return _leads.get(lead_id)


def delete_lead(lead_id: str):
    _leads.pop(lead_id, None)
    for key in [k for k in _analyses if k[0] == lead_id]:
        del _analyses[key]
    _outreach.pop(lead_id, None)
    _scores.pop(lead_id, None)


def save_analysis(lead_id: str, analysis_type: str, content: str, model: str = None) -> str:
    _analyses[(lead_id, analysis_type)] = content
    return str(uuid.uuid4())


def get_analysis(lead_id: str, analysis_type: str) -> str | None:
    return _analyses.get((lead_id, analysis_type))


def save_outreach(lead_id: str, outreach_type: str, subject: str, content: str, platform: str = "email") -> str:
    _outreach.setdefault(lead_id, []).append({
        "id": str(uuid.uuid4()),
        "outreach_type": outreach_type,
        "subject": subject,
        "content": content,
        "platform": platform,
    })
    return _outreach[lead_id][-1]["id"]


def get_outreach_history(lead_id: str) -> list[dict]:
    return _outreach.get(lead_id, [])


def save_score(lead_id: str, scores: dict, reasoning: str):
    _scores[lead_id] = {**scores, "score_reasoning": reasoning, "lead_id": lead_id}


def get_score(lead_id: str) -> dict | None:
    return _scores.get(lead_id)


def save_kb_document(doc_id: str, filename: str, doc_type: str, collection: str, chunk_count: int, metadata: dict):
    _kb_docs[doc_id] = {
        "id": doc_id, "filename": filename, "doc_type": doc_type,
        "collection": collection, "chunk_count": chunk_count, "metadata": metadata,
    }


def get_kb_documents() -> list[dict]:
    return list(_kb_docs.values())


def clear_all_leads():
    _leads.clear()
    for key in list(_analyses.keys()):
        del _analyses[key]
    _outreach.clear()
    _scores.clear()


def clear_all_data():
    _leads.clear()
    _analyses.clear()
    _outreach.clear()
    _kb_docs.clear()
    _scores.clear()


def get_dashboard_stats() -> dict:
    return {
        "total_leads":   len(_leads),
        "analyzed":      len({k[0] for k in _analyses if k[1] == "full_intelligence"}),
        "scored":        len(_scores),
        "high_priority": sum(1 for s in _scores.values() if s.get("overall", 0) >= 75),
        "outreach_sent": sum(len(v) for v in _outreach.values()),
        "kb_docs":       len(_kb_docs),
    }
