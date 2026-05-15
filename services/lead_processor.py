import uuid
import hashlib
import json
from datetime import datetime, timezone
import pandas as pd
from config.settings import LEAD_FIELD_ALIASES
from store import upsert_lead, get_all_leads
from services.chroma_manager import upsert_document
from config.settings import COLLECTIONS


def normalize_col(col: str) -> str:
    return col.lower().strip().replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "_")


def detect_field_mapping(columns: list[str]) -> dict[str, str]:
    normalized = {normalize_col(c): c for c in columns}
    mapping = {}
    for field, aliases in LEAD_FIELD_ALIASES.items():
        for alias in aliases:
            if alias in normalized:
                mapping[field] = normalized[alias]
                break
        if field not in mapping:
            for alias in aliases:
                for norm_col, orig_col in normalized.items():
                    if alias in norm_col or norm_col in alias:
                        mapping[field] = orig_col
                        break
                if field in mapping:
                    break
    return mapping


def parse_leads_from_dataframe(df: pd.DataFrame, batch_id: str = None) -> tuple[list[dict], list[str]]:
    if batch_id is None:
        batch_id = f"batch_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

    df.columns = [str(c) for c in df.columns]
    df = df.dropna(how="all").reset_index(drop=True)
    mapping = detect_field_mapping(list(df.columns))

    existing_emails = {l["email"] for l in get_all_leads() if l.get("email")}
    processed, warnings = [], []

    for idx, row in df.iterrows():
        lead = {}
        for field, col in mapping.items():
            val = row.get(col)
            if pd.notna(val) and str(val).strip() not in ("", "nan", "None"):
                lead[field] = str(val).strip()

        if not lead.get("name") and not lead.get("company"):
            continue

        lead.setdefault("company", "Unknown Company")
        lead.setdefault("name", lead.get("company", f"Contact {idx+1}"))

        email = lead.get("email", "")
        if email and email in existing_emails:
            warnings.append(f"Duplicate email skipped: {email}")
            continue

        raw = {str(k): str(v) for k, v in row.items() if pd.notna(v)}
        uid = hashlib.md5(
            f"{lead.get('name','')}{lead.get('company','')}{lead.get('email','')}".encode()
        ).hexdigest()[:12]

        lead["id"] = f"lead_{uid}"
        lead["raw_data"] = json.dumps(raw)
        lead["upload_batch"] = batch_id

        for field in ["name", "company", "email", "designation", "industry", "company_size",
                      "phone", "website", "linkedin", "location", "portfolio",
                      "case_files", "existing_services", "revenue", "notes"]:
            lead.setdefault(field, "")

        # Map 'designation' also to 'title' for backward-compat
        if lead.get("designation") and not lead.get("title"):
            lead["title"] = lead["designation"]
        elif lead.get("title") and not lead.get("designation"):
            lead["designation"] = lead["title"]

        processed.append(lead)

    return processed, warnings


def save_leads_to_db(leads: list[dict]) -> int:
    saved = 0
    for lead in leads:
        try:
            upsert_lead(lead)
            _index_lead_in_chroma(lead)
            saved += 1
        except Exception as e:
            print(f"Error saving {lead.get('name')}: {e}")
    return saved


def _index_lead_in_chroma(lead: dict):
    designation = lead.get("designation") or lead.get("title", "")
    text = f"""Company: {lead.get('company','')}
Contact: {lead.get('name','')} — {designation}
Industry: {lead.get('industry','')}
Size: {lead.get('company_size','')}
Website: {lead.get('website','')}
Existing Services: {lead.get('existing_services','')}
Portfolio: {lead.get('portfolio','')}
Case Files: {lead.get('case_files','')}
Notes: {lead.get('notes','')}"""

    upsert_document(
        collection_name=COLLECTIONS["lead_memory"],
        text=text,
        metadata={
            "lead_id": lead["id"],
            "company": lead.get("company", ""),
            "industry": lead.get("industry", ""),
            "name": lead.get("name", ""),
            "designation": designation,
            "type": "lead_profile",
        },
        doc_id=f"profile_{lead['id']}",
    )


def get_leads_summary(leads: list[dict]) -> str:
    if not leads:
        return "No leads loaded."
    companies = [l.get("company", "") for l in leads[:15]]
    industries = list(set(l.get("industry", "") for l in leads if l.get("industry")))[:8]
    return f"{len(leads)} leads. Companies: {', '.join(companies[:8])}. Industries: {', '.join(industries) or 'various'}."


def get_lead_display_name(lead: dict) -> str:
    name = lead.get("name", "")
    company = lead.get("company", "")
    desig = lead.get("designation") or lead.get("title", "")
    return f"{company} — {name}" + (f" ({desig})" if desig else "")
