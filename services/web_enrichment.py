import re
import requests
import wikipediaapi
from urllib.parse import urlparse
from pydantic import BaseModel, Field
from config.settings import TAVILY_API_KEY, SERPER_API_KEY

_wiki = wikipediaapi.Wikipedia(user_agent="EnterpriseIntel/1.0", language="en")

JINA_BASE    = "https://r.jina.ai/"
JINA_TIMEOUT = 20
SERPER_URL   = "https://google.serper.dev/search"
TAVILY_URL   = "https://api.tavily.com/search"
SECTION_SEP  = "§§§"

# Extensions / patterns that are never useful pages
_SKIP_PATTERNS = (
    ".png", ".jpg", ".jpeg", ".svg", ".gif", ".ico", ".webp",
    ".pdf", ".zip", ".mp4", ".mp3",
    "mailto:", "tel:", "javascript:",
    "linkedin.com", "twitter.com", "facebook.com", "instagram.com",
    "youtube.com", "github.com",
    "#", "?utm_", "?ref=",
)

# Serper site: queries to find real subpages (not guessed paths)
_SITE_QUERIES = [
    "services OR solutions OR products OR offerings",
    "about OR company OR team OR leadership",
    "case studies OR clients OR customers OR success",
    "careers OR jobs OR hiring",
]


# ── Structured model ──────────────────────────────────────────────────────────

class ScrapedPage(BaseModel):
    url:     str = ""
    label:   str = ""
    content: str = ""


class CompanyInsight(BaseModel):
    company:           str               = ""
    wikipedia_summary: str               = ""
    scraped_pages:     list[ScrapedPage] = Field(default_factory=list)
    recent_news:       list[str]         = Field(default_factory=list)
    hiring_signals:    list[str]         = Field(default_factory=list)
    tech_stack_hints:  list[str]         = Field(default_factory=list)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _clean(text: str, max_chars: int = 600) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


def _is_skip(url: str) -> bool:
    u = url.lower()
    return any(p in u for p in _SKIP_PATTERNS)


def _is_relevant(text: str, company: str, industry: str, name: str) -> bool:
    text_lower = text.lower()
    signals = [s.lower() for s in [company, industry, name] if s]
    return any(sig.split()[0] in text_lower for sig in signals if sig.split())


# ── Checkpoint 1: Strict company relevance score ──────────────────────────────

def _company_relevance_score(text: str, company: str) -> float:
    """
    Returns 0.0–1.0 measuring how likely the text is about THIS specific company.
    - Full company name present  → 1.0  (definitive)
    - All significant tokens match → 0.7
    - Most significant tokens match → 0.4
    - Only one generic token matches → 0.0 (rejected)
    """
    if not company or not text:
        return 0.0
    text_lower = text.lower()
    company_lower = company.lower()

    # Best case: full name present
    if company_lower in text_lower:
        return 1.0

    # Token-level: ignore short filler words (≤3 chars) like "and", "the", "inc"
    tokens = [t for t in re.split(r'[\s\-_,\.]+', company_lower) if len(t) > 3]
    if not tokens:
        return 1.0 if company_lower.split()[0] in text_lower else 0.0

    matched = sum(1 for t in tokens if t in text_lower)
    ratio   = matched / len(tokens)

    if ratio >= 1.0:
        return 0.7   # all meaningful tokens present but not as a phrase
    if ratio >= 0.6:
        return 0.4   # most tokens — ambiguous
    return 0.0       # too few tokens — likely irrelevant


# ── Checkpoint 2: Location-aware quality + relevance gate ────────────────────

def _location_tokens(location: str) -> list[str]:
    """Extract meaningful location tokens: city, country, region words."""
    if not location:
        return []
    return [t.lower() for t in re.split(r'[\s,/\-]+', location) if len(t) > 2]


def _passes_checkpoint(
    text: str,
    company: str,
    location: str = "",
    min_chars: int = 60,
    min_score: float = 0.4,
) -> bool:
    """
    Three-gate filter applied to every snippet before it enters the insight.

    Gate A — minimum content length (rejects boilerplate stubs).
    Gate B — company relevance score must meet threshold.
    Gate C — location check: if the lead has a location AND the snippet
              mentions a recognisable city/country that does NOT match,
              the snippet is rejected as belonging to a different entity
              with a similar name.
    """
    text_lower = text.strip().lower()

    # Gate A: content quality
    if len(text_lower) < min_chars:
        return False

    # Gate B: company relevance
    score = _company_relevance_score(text, company)
    if score < min_score:
        return False

    # Gate C: location cross-check
    # Only active when lead has a location AND snippet passed Gate B at a
    # borderline score (< 1.0 means full name wasn't found as a phrase).
    if location and score < 1.0:
        lead_loc_tokens = _location_tokens(location)
        if lead_loc_tokens:
            # Common cities/countries that, if present in the snippet, signal
            # it's talking about a specific place we can verify.
            _WORLD_CITIES = {
                "london", "new york", "sydney", "toronto", "singapore",
                "dubai", "berlin", "paris", "tokyo", "beijing", "shanghai",
                "mumbai", "delhi", "bangalore", "chennai", "hyderabad",
                "amsterdam", "zurich", "stockholm", "oslo", "seoul",
                "jakarta", "manila", "kuala lumpur", "nairobi", "lagos",
            }
            snippet_cities = {c for c in _WORLD_CITIES if c in text_lower}
            if snippet_cities:
                # If snippet mentions a city and none of them match the lead's
                # location tokens, this is the wrong company instance.
                location_match = any(
                    tok in text_lower for tok in lead_loc_tokens
                )
                if not location_match:
                    return False

    return True


def _is_error_page(text: str) -> bool:
    low = text.lower()[:300]
    return any(p in low for p in ["404", "page not found", "not found", "error", "doesn't exist"])


# ── Wikipedia ─────────────────────────────────────────────────────────────────

def _wikipedia_summary(query: str) -> str:
    page = _wiki.page(query)
    if page.exists():
        return _clean(page.summary)
    short = query.split()[0]
    page = _wiki.page(short)
    if page.exists():
        return _clean(page.summary)
    return ""


# ── Tavily (primary search) ───────────────────────────────────────────────────

def _tavily_results(query: str, max_results: int = 5, include_domains: list[str] = None) -> list[dict]:
    """Return raw Tavily result dicts: {title, url, content, score}."""
    if not TAVILY_API_KEY:
        return []
    payload = {
        "api_key":        TAVILY_API_KEY,
        "query":          query,
        "search_depth":   "basic",
        "max_results":    max_results,
        "include_answer": False,
    }
    if include_domains:
        payload["include_domains"] = include_domains
    try:
        resp = requests.post(TAVILY_URL, json=payload, timeout=12)
        if resp.status_code == 200:
            return resp.json().get("results", [])
    except Exception:
        pass
    return []


def _tavily_snippets(query: str, max_results: int = 5) -> list[str]:
    results = _tavily_results(query, max_results)
    if results:
        return [r.get("content", "") for r in results if r.get("content")]
    # Fallback chain: Serper → DuckDuckGo
    return _serper_snippets_raw(query, max_results) or _ddgs_fallback(query, max_results)


def _tavily_urls(query: str, domain: str, max_results: int = 4) -> list[str]:
    """Return page URLs scoped to a domain via Tavily include_domains."""
    results = _tavily_results(query, max_results, include_domains=[domain])
    return [
        r.get("url", "") for r in results
        if r.get("url") and not _is_skip(r.get("url", ""))
    ]


# ── Serper (fallback for snippets) ───────────────────────────────────────────

def _serper_snippets_raw(query: str, max_results: int = 5) -> list[str]:
    if not SERPER_API_KEY:
        return []
    try:
        resp = requests.post(
            SERPER_URL,
            headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
            json={"q": query, "num": max_results},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return [r.get("snippet", "") for r in data.get("organic", []) if r.get("snippet")]
    except Exception:
        return []


def _serper_urls(query: str, max_results: int = 4) -> list[str]:
    """Return page URLs from Serper — used for site: subpage discovery fallback."""
    if not SERPER_API_KEY:
        return []
    try:
        resp = requests.post(
            SERPER_URL,
            headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
            json={"q": query, "num": max_results},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return [
            r.get("link", "") for r in data.get("organic", [])
            if r.get("link") and not _is_skip(r.get("link", ""))
        ]
    except Exception:
        return []


def _ddgs_fallback(query: str, max_results: int = 5) -> list[str]:
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        return [r.get("body", "") for r in results if r.get("body")]
    except Exception:
        return []


# ── Jina AI Reader ────────────────────────────────────────────────────────────

def _jina_fetch(url: str) -> str:
    """Fetch one page via Jina Reader. Returns full clean text, no arbitrary truncation."""
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        resp = requests.get(
            f"{JINA_BASE}{url}",
            headers={
                "Accept":           "text/plain",
                "X-Return-Format":  "markdown",
                "X-Timeout":        "15000",
            },
            timeout=JINA_TIMEOUT,
        )
        if resp.status_code == 200:
            text = resp.text.strip()
            if _is_error_page(text):
                return ""
            return text
    except Exception:
        pass
    return ""


def _apex_domain(domain: str) -> str:
    """Strip www. prefix so site: queries work regardless of subdomain."""
    return domain.removeprefix("www.")


def _discover_subpage_urls(domain: str, base_url: str) -> list[str]:
    """
    Use Serper site: queries to find real indexed subpages for this domain.
    Much more reliable than guessing paths, since Google knows what actually exists.
    """
    apex = _apex_domain(domain)
    discovered = []
    for suffix in _SITE_QUERIES:
        urls = _tavily_urls(suffix, domain=apex, max_results=3) or _serper_urls(f"site:{apex} {suffix}", max_results=3)
        for u in urls:
            # accept URLs on apex or www subdomain
            if apex in u and u.rstrip("/") != base_url.rstrip("/") and not _is_skip(u):
                discovered.append(u)
    return list(dict.fromkeys(discovered))  # dedupe, preserve order


def _normalize_url(url: str) -> str:
    """Canonical form for deduplication: https + no www + no trailing slash."""
    p = urlparse(url)
    netloc = p.netloc.removeprefix("www.")
    return f"https://{netloc}{p.path.rstrip('/')}"


def _scrape_site(base_url: str) -> list[ScrapedPage]:
    """Scrape homepage + real subpages discovered via Serper."""
    if not base_url:
        return []
    if not base_url.startswith(("http://", "https://")):
        base_url = "https://" + base_url
    base_url = base_url.rstrip("/")
    domain = urlparse(base_url).netloc

    pages: list[ScrapedPage] = []
    visited_norm = set()

    # 1 — Homepage (always)
    home_content = _jina_fetch(base_url)
    if home_content:
        pages.append(ScrapedPage(url=base_url, label="Homepage", content=home_content))
        visited_norm.add(_normalize_url(base_url))

    # 2 — Discover real subpage URLs via Serper
    subpage_urls = _discover_subpage_urls(domain, base_url)

    # 3 — Scrape up to 5 subpages
    scraped = 0
    for raw_url in subpage_urls:
        if scraped >= 5:
            break
        if _normalize_url(raw_url) in visited_norm:
            continue

        # If discovered URL uses a different host than base, try base host first
        disc_parsed = urlparse(raw_url)
        base_parsed = urlparse(base_url)
        if _apex_domain(disc_parsed.netloc) == _apex_domain(base_parsed.netloc):
            candidate = f"{base_parsed.scheme}://{base_parsed.netloc}{disc_parsed.path}"
        else:
            candidate = raw_url

        content = _jina_fetch(candidate)
        if not content or len(content) < 300:
            # Fallback: try the discovered URL as-is
            content = _jina_fetch(raw_url)

        if content and len(content) > 300:
            norm = _normalize_url(candidate)
            if norm not in visited_norm:
                visited_norm.add(norm)
                path = urlparse(candidate).path.strip("/")
                # Clean up .php / .html extensions for the label
                label = re.sub(r'\.(php|html?)$', '', path, flags=re.I)
                label = label.replace("-", " ").replace("_", " ").replace("/", " › ").title() or "Page"
                pages.append(ScrapedPage(url=candidate, label=label, content=content))
                scraped += 1

    return pages


# ── Main enrichment ───────────────────────────────────────────────────────────

def enrich_lead(lead: dict) -> str:
    company  = lead.get("company", "")
    industry = lead.get("industry", "")
    name     = lead.get("name", "")
    website  = lead.get("website", "")
    location = lead.get("location", "")

    insight = CompanyInsight(company=company)

    # 1 — Wikipedia
    if company:
        wiki = _wikipedia_summary(company)
        if wiki and _is_relevant(wiki, company, industry, name):
            insight.wikipedia_summary = wiki

    # 2 — Full website scrape (homepage + Serper-discovered subpages)
    if website:
        insight.scraped_pages = _scrape_site(website)

    # 3 — Tavily: company news/profile
    # Checkpoint: full name or all tokens must appear in the snippet
    if company:
        snippets = _tavily_snippets(f"{company} {industry} company", max_results=5)
        insight.recent_news = [
            _clean(s, 400) for s in snippets
            if _passes_checkpoint(s, company, location=location, min_chars=80, min_score=0.4)
        ][:3]

    # 4 — Tavily: hiring signals
    # Checkpoint: snippet must reference this company specifically, not generic job boards
    if company:
        hiring = _tavily_snippets(f"{company} hiring jobs careers engineering", max_results=4)
        insight.hiring_signals = [
            _clean(s, 300) for s in hiring
            if _passes_checkpoint(s, company, location=location, min_chars=60, min_score=0.4)
        ][:2]

    # 5 — Tavily: tech stack hints
    # Checkpoint: must mention the company — pure generic tech articles are useless
    if company:
        tech = _tavily_snippets(f"{company} technology stack software tools platform", max_results=4)
        insight.tech_stack_hints = [
            _clean(s, 300) for s in tech
            if _passes_checkpoint(s, company, location=location, min_chars=60, min_score=0.4)
        ][:2]

    return _format_insight(insight)


# ── Format ────────────────────────────────────────────────────────────────────

def _format_insight(insight: CompanyInsight) -> str:
    sections = []

    if insight.wikipedia_summary:
        sections.append(f"[Wikipedia — {insight.company}]\n{insight.wikipedia_summary}")

    for page in insight.scraped_pages:
        sections.append(f"[Website: {page.label} — {page.url}]\n{page.content}")

    if insight.recent_news:
        body = "\n".join(f"• {s}" for s in insight.recent_news)
        sections.append(f"[Web Search — {insight.company}]\n{body}")

    if insight.hiring_signals:
        body = "\n".join(f"• {s}" for s in insight.hiring_signals)
        sections.append(f"[Hiring Signals — {insight.company}]\n{body}")

    if insight.tech_stack_hints:
        body = "\n".join(f"• {s}" for s in insight.tech_stack_hints)
        sections.append(f"[Tech Stack Signals — {insight.company}]\n{body}")

    return SECTION_SEP.join(sections) if sections else ""
