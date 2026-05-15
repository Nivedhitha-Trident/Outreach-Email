import re
import wikipediaapi
from ddgs import DDGS


_wiki = wikipediaapi.Wikipedia(user_agent="EnterpriseIntel/1.0", language="en")


def _clean(text: str, max_chars: int = 600) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


def _wikipedia_summary(query: str) -> str:
    page = _wiki.page(query)
    if page.exists():
        return _clean(page.summary)
    # Try first word (company name without Inc/Ltd noise)
    short = query.split()[0]
    page = _wiki.page(short)
    if page.exists():
        return _clean(page.summary)
    return ""


def _ddg_snippets(query: str, max_results: int = 5) -> list[str]:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        return [r.get("body", "") for r in results if r.get("body")]
    except Exception:
        return []


def _is_relevant(text: str, company: str, industry: str, name: str) -> bool:
    text_lower = text.lower()
    signals = [s.lower() for s in [company, industry, name] if s]
    # keep if at least one signal word appears
    return any(sig.split()[0] in text_lower for sig in signals if sig.split())


def enrich_lead(lead: dict) -> str:
    company  = lead.get("company", "")
    industry = lead.get("industry", "")
    name     = lead.get("name", "")
    website  = lead.get("website", "")
    location = lead.get("location", "")

    sections = []

    # ── Wikipedia: company ───────────────────────────────────────────────────
    if company:
        wiki_text = _wikipedia_summary(company)
        if wiki_text and _is_relevant(wiki_text, company, industry, name):
            sections.append(f"[Wikipedia — {company}]\n{wiki_text}")

    # ── Wikipedia: industry context ──────────────────────────────────────────
    if industry and len(industry) > 3:
        wiki_ind = _wikipedia_summary(f"{industry} industry")
        if wiki_ind:
            sections.append(f"[Wikipedia — {industry} industry]\n{_clean(wiki_ind, 400)}")

    # ── DuckDuckGo: company news / profile ───────────────────────────────────
    if company:
        q = f"{company} {industry} company"
        snippets = _ddg_snippets(q, max_results=5)
        relevant = [s for s in snippets if _is_relevant(s, company, industry, name)][:3]
        if relevant:
            combined = "\n".join(f"• {_clean(s, 300)}" for s in relevant)
            sections.append(f"[Web — {company}]\n{combined}")

    # ── DuckDuckGo: person / role context ────────────────────────────────────
    if name and company:
        q = f"{name} {company} {lead.get('designation','')}"
        snippets = _ddg_snippets(q, max_results=3)
        relevant = [s for s in snippets if _is_relevant(s, company, industry, name)][:2]
        if relevant:
            combined = "\n".join(f"• {_clean(s, 250)}" for s in relevant)
            sections.append(f"[Web — {name}]\n{combined}")

    return "\n\n".join(sections) if sections else ""
