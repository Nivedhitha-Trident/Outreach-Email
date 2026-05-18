import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from store import save_outreach, save_analysis, get_analysis
from services.llm_service import invoke_llm, stream_llm
from services.memory_service import recall_case_studies, store_outreach
from services.chroma_manager import semantic_search, format_search_results_as_context
from config.settings import COLLECTIONS, ROLE_TIERS
from config.knowledge_base import TRIDENT_INTRO
from prompts.templates import PERSONALIZED_EMAIL_PROMPT, EMAIL_JUDGE_PROMPT


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


def _parse_web_sections(web_ctx: str) -> dict:
    """Split web_context into typed buckets for targeted use in email generation."""
    buckets = {
        "website_pages":   [],   # Jina-scraped pages (services, about, case studies)
        "search_snippets": [],   # Tavily / web search results
        "hiring_signals":  [],   # hiring/jobs snippets
        "tech_stack":      [],   # technology signals
        "wikipedia":       [],   # Wikipedia summary
    }
    if not web_ctx:
        return buckets

    sep = "§§§" if "§§§" in web_ctx else "\n\n"
    for block in web_ctx.strip().split(sep):
        block = block.strip()
        if not block:
            continue
        lines  = block.splitlines()
        header = lines[0].strip("[]") if lines[0].startswith("[") else ""
        body   = "\n".join(lines[1:]).strip()
        if not body:
            continue
        if "Wikipedia" in header:
            buckets["wikipedia"].append(body[:600])
        elif "Website:" in header:
            buckets["website_pages"].append(body[:1200])
        elif "Hiring" in header:
            buckets["hiring_signals"].append(body[:400])
        elif "Tech Stack" in header:
            buckets["tech_stack"].append(body[:400])
        else:
            buckets["search_snippets"].append(body[:400])

    return buckets


def _infer_company_stage(company_size: str) -> str:
    s = (company_size or "").lower()
    if any(x in s for x in ["1000", "2000", "5000", "10000", "enterprise", "large", "mnc"]):
        return "Enterprise (1000+ people)"
    if any(x in s for x in ["200", "300", "400", "500", "mid", "medium"]):
        return "Mid-market (200–1000 people)"
    if any(x in s for x in ["50", "100", "150", "growth", "scale"]):
        return "Growth stage (50–200 people)"
    if any(x in s for x in ["1", "5", "10", "15", "20", "30", "startup", "early", "seed"]):
        return "Startup (< 50 people)"
    # fallback: try to parse a number
    import re
    nums = re.findall(r'\d+', s)
    if nums:
        n = int(nums[0])
        if n >= 1000: return "Enterprise (1000+ people)"
        if n >= 200:  return "Mid-market (200–1000 people)"
        if n >= 50:   return "Growth stage (50–200 people)"
        return "Startup (< 50 people)"
    return "Growth stage (company size not specified — assume mid-size)"


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
    company_size = lead.get("company_size", "")

    search_q = f"{industry} {designation} {company} {existing} challenges automation transformation"
    sol_results = semantic_search(COLLECTIONS["solutions_kb"], search_q, n_results=5)
    cs_results  = semantic_search(COLLECTIONS["case_studies"],  search_q, n_results=3)
    solutions_text    = format_search_results_as_context(sol_results, max_tokens=900)
    case_studies_text = format_search_results_as_context(cs_results,  max_tokens=600)

    # Parse web research into typed buckets
    web_buckets = _parse_web_sections(analysis.get("web_context", ""))

    # Website intel: scraped services/about/case-study pages — most valuable for personalisation
    website_intel = ""
    if web_buckets["website_pages"]:
        website_intel = "\n\n---\n\n".join(web_buckets["website_pages"][:3])
    elif web_buckets["search_snippets"]:
        website_intel = "\n".join(f"• {s}" for s in web_buckets["search_snippets"][:4])

    # Tech stack from scraping vs. lead field
    scraped_stack = "\n".join(f"• {s}" for s in web_buckets["tech_stack"][:3])
    hiring_intel  = "\n".join(f"• {s}" for s in web_buckets["hiring_signals"][:3])

    services_gap = (
        f"Known tools/stack: {existing or 'not specified'}. "
        f"Scraped tech signals: {scraped_stack or 'none found'}. "
        f"Hiring signals: {hiring_intel or 'none found'}. "
        f"Company size: {company_size or 'not specified'}. Industry: {industry or 'not specified'}. "
        f"Use all of the above to infer: what they own in-house, what they outsource, "
        f"and where the engineering/QA/cloud/AI gaps are."
    )

    return {
        "name":              lead.get("name", "there"),
        "designation":       designation or "Professional",
        "company":           company or "your company",
        "industry":          industry or "your industry",
        "company_size":      company_size,
        "company_stage":     _infer_company_stage(company_size),
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
        "services_gap":      services_gap,
        "website_intel":     website_intel or "No website data scraped.",
    }


def _generate_one_variant(prompt: str, temperature: float) -> str:
    return invoke_llm(prompt, temperature=temperature, max_tokens=1200)


def _generate_variants(prompt: str) -> tuple[str, str, str]:
    """Generate 3 email variants in parallel at different creative temperatures."""
    temperatures = [0.55, 0.78, 0.96]
    results = [None, None, None]
    with ThreadPoolExecutor(max_workers=3) as ex:
        futures = {ex.submit(_generate_one_variant, prompt, t): i
                   for i, t in enumerate(temperatures)}
        for fut in as_completed(futures):
            idx = futures[fut]
            try:
                results[idx] = fut.result()
            except Exception:
                results[idx] = ""
    # Fallback: if any variant failed, replace with a sequential call
    for i, r in enumerate(results):
        if not r:
            results[i] = invoke_llm(prompt, temperature=temperatures[i], max_tokens=1200)
    return results[0], results[1], results[2]


def _judge_variants(ctx: dict, v1: str, v2: str, v3: str) -> str:
    """Send all 3 variants to the LLM judge. Returns the winning email text."""
    judge_prompt = EMAIL_JUDGE_PROMPT.format(
        name=ctx["name"],
        designation=ctx["designation"],
        company=ctx["company"],
        industry=ctx["industry"],
        company_stage=ctx["company_stage"],
        variant_1=v1,
        variant_2=v2,
        variant_3=v3,
    )
    winner = invoke_llm(judge_prompt, temperature=0.2, max_tokens=1400)
    return winner.strip()


def generate_output(
    lead: dict,
    analysis: dict,
    output_type: str = "personalized_email",
    stream: bool = False,
    force_refresh: bool = False,
    on_progress=None,
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
        # Stream mode: single variant (streaming 3 in parallel isn't practical)
        def _gen():
            full = ""
            for chunk in stream_llm(prompt):
                full += chunk
                yield chunk
            _persist(lead, output_type, full)
        return _gen()

    # ── 3-variant + judge flow ────────────────────────────────────────────────
    if on_progress:
        on_progress("Drafting 3 email variants in parallel…", 20)

    v1, v2, v3 = _generate_variants(prompt)

    if on_progress:
        on_progress("Selecting the best variant…", 80)

    content = _judge_variants(ctx, v1, v2, v3)

    # Save all 3 variants for reference
    save_analysis(lead_id, "email_variant_1", v1)
    save_analysis(lead_id, "email_variant_2", v2)
    save_analysis(lead_id, "email_variant_3", v3)

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
