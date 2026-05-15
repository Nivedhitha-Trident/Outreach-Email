import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import pandas as pd
import io

st.set_page_config(
    page_title="AI Mail Generator",
    page_icon="✉",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* ── Force dark everywhere ── */
html, body, [class*="css"], .stApp {
    font-family: 'Inter', sans-serif !important;
    background-color: #0f0f17 !important;
    color: #d4d4e8 !important;
}
.main .block-container {
    padding: 1.2rem 1.5rem 2rem 1.5rem;
    max-width: 100%;
    background: #0f0f17;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: #13131f !important;
    border-right: 1px solid #1e1e30 !important;
}
section[data-testid="stSidebar"] > div { padding: 1.2rem 1rem; }
section[data-testid="stSidebar"] * { color: #c0c0d8 !important; }

/* All text defaults */
p, span, div, label, li { color: #c8c8e0; }
h1, h2, h3, h4 { color: #e8e8ff !important; }

/* Step labels */
.step-label {
    font-size: 0.67rem; font-weight: 700; letter-spacing: 0.12em;
    text-transform: uppercase; color: #5555aa !important;
    margin: 1.2rem 0 0.5rem 0;
}

/* Lead cards */
.lead-card {
    background: #16162a; border: 1px solid #22223a; border-radius: 10px;
    padding: 0.7rem 1rem; margin-bottom: 0.35rem;
    transition: border-color 0.15s, background 0.15s;
}
.lead-card:hover { border-color: #7c7cff; background: #1a1a30; }
.lead-card.selected { border-color: #7c7cff; background: #1c1c35; }
.lead-name { font-size: 0.88rem; font-weight: 600; color: #e0e0ff !important; }
.lead-sub  { font-size: 0.75rem; color: #6868a0 !important; margin-top: 2px; }

/* Role pills */
.role-pill {
    display: inline-block; padding: 2px 8px; border-radius: 20px;
    font-size: 0.67rem; font-weight: 700; margin-left: 6px;
}
.pill-csuite    { background: rgba(124,124,255,0.18); color: #a0a0ff !important; border: 1px solid #4444aa; }
.pill-technical { background: rgba(250,204,21,0.12);  color: #fbbf24 !important; border: 1px solid #78600a; }
.pill-manager   { background: rgba(52,211,153,0.12);  color: #34d399 !important; border: 1px solid #065f46; }
.pill-hr        { background: rgba(244,114,182,0.12); color: #f472b6 !important; border: 1px solid #831843; }
.pill-marketing { background: rgba(96,165,250,0.12);  color: #60a5fa !important; border: 1px solid #1e3a8a; }
.pill-sales     { background: rgba(251,191,36,0.12);  color: #fbbf24 !important; border: 1px solid #78600a; }
.pill-other     { background: rgba(156,163,175,0.10); color: #9ca3af !important; border: 1px solid #374151; }

/* Email display box */
.email-box {
    background: #13131f; border: 1px solid #22223a; border-radius: 12px;
    padding: 1.5rem 1.8rem; font-size: 0.875rem; line-height: 1.8;
    color: #d4d4f0 !important; white-space: pre-wrap;
    font-family: 'Inter', sans-serif; min-height: 300px;
}
.subject-line {
    font-size: 1rem; font-weight: 700; color: #e8e8ff !important;
    margin-bottom: 1rem; padding-bottom: 0.8rem;
    border-bottom: 1px solid #1e1e30;
}

/* Analysis chips */
.analysis-chip {
    display: inline-block; background: #1e1e35; border: 1px solid #2a2a48;
    border-radius: 6px; padding: 3px 10px; font-size: 0.73rem;
    color: #8888cc !important; margin: 3px 3px 3px 0;
}

/* Pain / solution lines */
.pain-line {
    border-left: 3px solid #f87171; background: rgba(248,113,113,0.07);
    padding: 6px 10px; border-radius: 0 6px 6px 0;
    font-size: 0.8rem; color: #d4d4e8 !important; margin-bottom: 4px;
}
.solution-line {
    border-left: 3px solid #34d399; background: rgba(52,211,153,0.07);
    padding: 6px 10px; border-radius: 0 6px 6px 0;
    font-size: 0.8rem; color: #d4d4e8 !important; margin-bottom: 4px;
}

/* Empty hint */
.empty-hint {
    text-align: center; padding: 4rem 2rem;
    color: #3a3a60 !important; font-size: 0.9rem; line-height: 1.8;
}

/* Buttons */
.stButton > button {
    border-radius: 8px; font-weight: 600; font-size: 0.85rem;
    transition: all 0.18s; border: none;
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #5b5bdb, #7c7cff) !important;
    color: #fff !important; padding: 0.55rem 1rem;
}
.stButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg, #4a4ac9, #6b6bef) !important;
    box-shadow: 0 4px 18px rgba(100,100,255,0.35);
}
.stButton > button[kind="secondary"] {
    background: #1a1a2e !important; border: 1px solid #2a2a48 !important;
    color: #a0a0cc !important;
}
.stButton > button[kind="secondary"]:hover {
    background: #22223a !important; color: #c0c0e0 !important;
}

/* Streamlit native widgets */
div[data-testid="stFileUploader"] {
    border: 1.5px dashed #2a2a48 !important; border-radius: 8px;
    background: #12121e !important;
}
div[data-testid="stFileUploader"] * { color: #7070aa !important; }

.stTextArea textarea {
    background: #13131f !important; border: 1px solid #22223a !important;
    color: #d4d4f0 !important; border-radius: 8px; font-size: 0.85rem;
}
.stTextInput > div > div > input {
    background: #13131f !important; border: 1px solid #22223a !important;
    color: #d4d4f0 !important; border-radius: 8px;
}
.stTextInput > div > div > input::placeholder { color: #3a3a60 !important; }
.stTextArea textarea::placeholder { color: #3a3a60 !important; }

.stSelectbox > div > div {
    background: #13131f !important; border: 1px solid #22223a !important;
    color: #d4d4f0 !important;
}

/* Checkbox */
.stCheckbox label { color: #8888b0 !important; font-size: 0.82rem; }
.stCheckbox span[data-baseweb="checkbox"] { border-color: #3a3a60 !important; }

/* Metrics */
div[data-testid="metric-container"] {
    background: #13131f; border: 1px solid #1e1e30; border-radius: 10px;
}
div[data-testid="metric-container"] label { color: #5555aa !important; }
div[data-testid="metric-container"] div[data-testid="stMetricValue"] {
    color: #e0e0ff !important;
}

/* Expander */
div[data-testid="stExpander"] {
    background: #13131f !important; border: 1px solid #1e1e30 !important;
    border-radius: 10px;
}
div[data-testid="stExpander"] summary { color: #9090c0 !important; }
div[data-testid="stExpander"] summary:hover { color: #b0b0e0 !important; }

/* Alerts / success / warning */
div[data-testid="stAlert"] { border-radius: 8px !important; }
.stSuccess { background: rgba(52,211,153,0.1) !important; border: 1px solid rgba(52,211,153,0.3) !important; }
.stWarning { background: rgba(251,191,36,0.1) !important; border: 1px solid rgba(251,191,36,0.3) !important; }
.stError   { background: rgba(248,113,113,0.1) !important; border: 1px solid rgba(248,113,113,0.3) !important; }
.stInfo    { background: rgba(96,165,250,0.1)  !important; border: 1px solid rgba(96,165,250,0.3)  !important; }

/* Progress bar */
.stProgress > div > div > div > div {
    background: linear-gradient(90deg, #5b5bdb, #7c7cff) !important;
}

/* Dataframe / table */
div[data-testid="stDataFrame"] { border: 1px solid #1e1e30 !important; border-radius: 8px; }

/* Divider */
hr { border-color: #1a1a2e !important; }

/* Caption */
.stCaption { color: #4a4a7a !important; font-size: 0.75rem; }

/* Download button */
.stDownloadButton > button {
    background: #1a1a2e !important; border: 1px solid #2a2a48 !important;
    color: #a0a0cc !important; border-radius: 8px; font-weight: 600;
}
.stDownloadButton > button:hover {
    background: #22223a !important; color: #c0c0e0 !important;
}

/* Scrollbar */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: #0f0f17; }
::-webkit-scrollbar-thumb { background: #22223a; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #2e2e50; }

/* Info bar */
.info-bar {
    background: #13131f; border: 1px solid #1e1e30; border-radius: 10px;
    padding: 0.9rem 1.2rem; margin-bottom: 1rem;
}
</style>
""", unsafe_allow_html=True)


# ── Init ──────────────────────────────────────────────────────────────────────

def init():
    if "app_started" not in st.session_state:
        # First run of this session — wipe everything clean
        from store import init_db, clear_all_data
        from services.chroma_manager import clear_all_collections
        from services.kb_ingestion import seed_trident_kb
        init_db()
        clear_all_data()
        clear_all_collections()
        seed_trident_kb()
        st.session_state.app_started    = True
        st.session_state.leads          = []
        st.session_state.db_ready       = True
        st.session_state.selected_id    = None
        st.session_state.analysis_cache = {}
        st.session_state.email_cache    = {}
        st.session_state.brief_cache    = {}
        st.session_state.processed_files = set()
        st.session_state.sent_emails    = {}   # lead_id -> {name, company, email, sent_at}


def _reload_leads():
    from store import get_all_leads
    st.session_state.leads = get_all_leads()


def _role_pill(designation: str) -> str:
    from services.outreach_generator import classify_role
    tier = classify_role(designation or "")
    labels = {"c_suite": ("C-Suite", "csuite"), "vp_dir": ("VP/Dir", "manager"),
               "manager": ("Manager", "manager"), "technical": ("Technical", "technical"),
               "hr": ("HR", "hr"), "marketing": ("Marketing", "marketing"),
               "sales": ("Sales", "sales"), "professional": ("", "other")}
    lbl, cls = labels.get(tier, ("", "other"))
    return f'<span class="role-pill pill-{cls}">{lbl}</span>' if lbl else ""


# ── Sidebar ───────────────────────────────────────────────────────────────────

def render_sidebar():
    with st.sidebar:
        st.markdown("## ✉ AI Mail Generator")
        st.markdown("*Upload leads → generate personalized emails*")
        st.markdown("---")

        # Step 1: Upload Leads
        st.markdown('<div class="step-label">Step 1 — Upload Leads (Excel / CSV)</div>', unsafe_allow_html=True)
        lead_file = st.file_uploader("Leads file", type=["xlsx", "xls", "csv"],
                                     label_visibility="collapsed", key="lead_upload")
        if lead_file:
            fkey = f"lead_{lead_file.name}_{lead_file.size}"
            if fkey not in st.session_state.processed_files:
                _handle_lead_upload(lead_file)
                st.session_state.processed_files.add(fkey)

        st.markdown("---")

        # Stats
        leads = st.session_state.leads
        from services.chroma_manager import get_collection_stats
        col_stats = get_collection_stats()
        sol_count = col_stats.get("solutions_kb", 0)
        analyzed = sum(1 for l in leads if l["id"] in st.session_state.analysis_cache)

        st.markdown(f"""
<div style="display:flex;gap:0;justify-content:space-between;">
    <div style="text-align:center;flex:1;">
        <div style="font-size:1.4rem;font-weight:700;color:#111827;">{len(leads)}</div>
        <div style="font-size:0.68rem;color:#9ca3af;text-transform:uppercase;">Leads</div>
    </div>
    <div style="text-align:center;flex:1;">
        <div style="font-size:1.4rem;font-weight:700;color:#6366f1;">{sol_count}</div>
        <div style="font-size:0.68rem;color:#9ca3af;text-transform:uppercase;">KB Chunks</div>
    </div>
    <div style="text-align:center;flex:1;">
        <div style="font-size:1.4rem;font-weight:700;color:#10b981;">{analyzed}</div>
        <div style="font-size:0.68rem;color:#9ca3af;text-transform:uppercase;">Analyzed</div>
    </div>
</div>
""", unsafe_allow_html=True)

        if leads:
            st.markdown("---")
            if st.button("🗑 Clear All Leads", use_container_width=True, key="clear_leads"):
                from store import clear_all_leads
                clear_all_leads()
                st.session_state.leads = []
                st.session_state.analysis_cache = {}
                st.session_state.email_cache = {}
                st.session_state.brief_cache = {}
                st.session_state.processed_files = set()
                st.session_state.selected_id = None
                st.rerun()


def _handle_lead_upload(file):
    from utils.document_processor import read_dataframe
    from services.lead_processor import parse_leads_from_dataframe, save_leads_to_db
    try:
        df = read_dataframe(file.read(), file.name)
        leads, warnings = parse_leads_from_dataframe(df)
        saved = save_leads_to_db(leads)
        _reload_leads()
        st.success(f"✓ {saved} leads imported")
        if warnings:
            st.warning(f"{len(warnings)} duplicates skipped")
    except Exception as e:
        st.error(f"Error: {e}")


def _handle_solution_upload(file):
    from services.kb_ingestion import ingest_document
    result = ingest_document(file.read(), file.name, doc_type="solution")
    if result.get("success"):
        st.success(f"✓ {file.name} added ({result['chunk_count']} chunks)")
    else:
        st.error(result.get("error"))


def _handle_solution_text(text: str):
    from services.kb_ingestion import ingest_text_note
    result = ingest_text_note("My Solutions & Services", text, doc_type="solution")
    if result.get("success"):
        st.success("✓ Solutions saved")
    else:
        st.error(result.get("error"))


# ── Main: Leads List or Lead Detail Page ──────────────────────────────────────

def render_main():
    leads = st.session_state.leads
    sel   = st.session_state.selected_id

    # ── Lead detail page ──────────────────────────────────────────────────────
    if sel:
        lead = next((l for l in leads if l["id"] == sel), None)
        if lead:
            # Back button
            if st.button("← Back to Leads", key="back_btn", type="secondary"):
                st.session_state.selected_id = None
                st.rerun()
            st.markdown("<hr style='border-color:#1e1e30;margin:0.6rem 0 1.2rem 0;'>",
                        unsafe_allow_html=True)
            render_brief_panel(lead)
        return

    # ── Leads list page ───────────────────────────────────────────────────────
    if not leads:
        st.markdown("""
<div class="empty-hint">
    <div style="font-size:2.5rem;margin-bottom:1rem;">✉</div>
    <strong>Upload your leads file to get started</strong><br><br>
    1. Upload Excel / CSV with leads — sidebar left<br>
    2. Click a lead to open its full brief page
</div>
""", unsafe_allow_html=True)
        return

    # ── Sent emails status panel ──────────────────────────────────────────────
    sent = st.session_state.sent_emails
    if sent:
        st.markdown('<div class="step-label">Emails Sent This Session</div>', unsafe_allow_html=True)
        rows = list(sent.items())
        for i in range(0, len(rows), 3):
            chunk = rows[i:i+3]
            cols = st.columns(len(chunk))
            for col, (slid, info) in zip(cols, chunk):
                col.markdown(
                    f'<div style="background:#0e1f14;border:1px solid #1a3a24;border-radius:8px;'
                    f'padding:0.6rem 0.9rem;margin-bottom:0.4rem;">'
                    f'<div style="font-size:0.82rem;font-weight:600;color:#34d399;">{info["company"]}</div>'
                    f'<div style="font-size:0.75rem;color:#5a8a6a;">{info["name"]}'
                    f'{" · " + info["email"] if info["email"] else ""}</div>'
                    f'<div style="font-size:0.7rem;color:#2d5a3d;margin-top:3px;">✓ Sent {info["sent_at"]}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        st.markdown("<hr style='border-color:#1e1e30;margin:0.8rem 0 1rem 0;'>", unsafe_allow_html=True)

    st.markdown(f'<div class="step-label">Step 3 — Select a lead ({len(leads)} total)</div>',
                unsafe_allow_html=True)

    search = st.text_input("Search", placeholder="🔍 Search company or name…",
                           label_visibility="collapsed", key="lead_search")
    filtered = [l for l in leads
                if not search or search.lower() in (l.get("company","") + l.get("name","")).lower()]

    # Responsive grid: 3 cards per row
    cols = st.columns(3, gap="medium")
    for i, lead in enumerate(filtered[:90]):
        lid   = lead["id"]
        desig = lead.get("designation") or lead.get("title", "")
        pill  = _role_pill(desig)
        done  = "✓ " if lid in st.session_state.brief_cache else ""
        ind   = lead.get("industry", "")
        size  = lead.get("company_size", "")

        with cols[i % 3]:
            st.markdown(f"""
<div class="lead-card" style="min-height:90px;">
    <div class="lead-name">{lead.get('company','—')}{pill}</div>
    <div class="lead-sub">{done}{lead.get('name','')} · {desig}</div>
    {"<div class='lead-sub'>" + ind + ("&nbsp;·&nbsp;" + size if size else "") + "</div>" if ind else ""}
</div>
""", unsafe_allow_html=True)
            if st.button("Open →", key=f"sel_{lid}", use_container_width=True, type="primary"):
                st.session_state.selected_id = lid
                st.rerun()



def render_brief_panel(lead: dict):
    from services.intelligence_engine import analyze_lead
    from services.outreach_generator import generate_output
    from store import get_analysis as db_get, save_analysis

    lid   = lead["id"]
    desig = lead.get("designation") or lead.get("title", "")
    pill  = _role_pill(desig)

    # ── Lead details at top ───────────────────────────────────────────────────
    st.markdown(f"""
<div style="background:#13131f;border:1px solid #22223a;border-radius:12px;
     padding:1rem 1.4rem;margin-bottom:0.8rem;">
  <div style="font-size:1.05rem;font-weight:700;color:#e0e0ff;">
    {lead.get('company','—')} {pill}
  </div>
  <div style="font-size:0.85rem;color:#7070a8;margin-top:3px;">
    {lead.get('name','')} &nbsp;·&nbsp; {desig}
    {f' &nbsp;·&nbsp; {lead.get("industry","")}' if lead.get('industry') else ''}
    {f' &nbsp;·&nbsp; {lead.get("company_size","")}' if lead.get('company_size') else ''}
  </div>
  {f'<div style="font-size:0.78rem;color:#4a4a70;margin-top:4px;">📧 {lead.get("email","")}</div>' if lead.get('email') else ''}
</div>
""", unsafe_allow_html=True)

    with st.expander("Additional Details"):
        rows = [
            ("Website",  lead.get("website","")),
            ("LinkedIn", lead.get("linkedin","")),
            ("Location", lead.get("location","")),
            ("Stack",    lead.get("existing_services","")),
            ("Revenue",  lead.get("revenue","")),
            ("Notes",    lead.get("notes","")),
        ]
        for label, val in rows:
            if val:
                st.markdown(
                    f'<div style="font-size:0.82rem;color:#9090c8;padding:3px 0;">'
                    f'<span style="color:#5555aa;font-weight:600;min-width:80px;'
                    f'display:inline-block;">{label}</span> {val}</div>',
                    unsafe_allow_html=True)

        cached_analysis = st.session_state.analysis_cache.get(lid)
        if cached_analysis:
            st.markdown("<hr style='border-color:#1a1a2e;margin:0.8rem 0;'>", unsafe_allow_html=True)

            # Business Analysis
            biz = cached_analysis.get("business_analysis", "")
            if biz:
                st.markdown(
                    '<div style="font-size:0.75rem;font-weight:700;letter-spacing:0.1em;'
                    'text-transform:uppercase;color:#5555aa;margin-bottom:0.5rem;">Business Analysis</div>',
                    unsafe_allow_html=True)
                st.markdown(
                    f'<div style="font-size:0.82rem;color:#9090c8;line-height:1.7;'
                    f'background:#12121e;border-radius:8px;padding:0.7rem 1rem;">{biz}</div>',
                    unsafe_allow_html=True)
                st.markdown("<div style='margin-top:0.8rem;'></div>", unsafe_allow_html=True)

            # Pain Points
            pain_points = cached_analysis.get("pain_points", [])
            if pain_points:
                st.markdown(
                    '<div style="font-size:0.75rem;font-weight:700;letter-spacing:0.1em;'
                    'text-transform:uppercase;color:#5555aa;margin-bottom:0.5rem;">Pain Points</div>',
                    unsafe_allow_html=True)
                for pp in pain_points:
                    area = pp.get("area", "")
                    desc = pp.get("description", "")
                    severity = pp.get("severity", "")
                    sev_color = "#f87171" if severity == "high" else ("#fbbf24" if severity == "medium" else "#6868a0")
                    sev_badge = (f'<span style="font-size:0.65rem;background:rgba(248,113,113,0.12);'
                                 f'color:{sev_color};border:1px solid {sev_color}40;border-radius:4px;'
                                 f'padding:1px 6px;margin-left:6px;font-weight:700;">{severity.upper()}</span>'
                                 if severity else "")
                    st.markdown(
                        f'<div class="pain-line"><strong style="color:#e0b0b0;">{area}</strong>'
                        f'{sev_badge}<br><span style="font-size:0.78rem;">{desc}</span></div>',
                        unsafe_allow_html=True)
                st.markdown("<div style='margin-top:0.8rem;'></div>", unsafe_allow_html=True)

            # Opportunities
            opportunities = cached_analysis.get("opportunities", [])
            if opportunities:
                st.markdown(
                    '<div style="font-size:0.75rem;font-weight:700;letter-spacing:0.1em;'
                    'text-transform:uppercase;color:#5555aa;margin-bottom:0.5rem;">Opportunities</div>',
                    unsafe_allow_html=True)
                for opp in opportunities:
                    title   = opp.get("title", "")
                    detail  = opp.get("description", "") or opp.get("detail", "")
                    urgency = opp.get("urgency", "")
                    urg_color = "#34d399" if urgency == "immediate" else "#6868a0"
                    urg_badge = (f'<span style="font-size:0.65rem;background:rgba(52,211,153,0.1);'
                                 f'color:{urg_color};border:1px solid {urg_color}40;border-radius:4px;'
                                 f'padding:1px 6px;margin-left:6px;font-weight:700;">{urgency.upper()}</span>'
                                 if urgency else "")
                    detail_html = f'<br><span style="font-size:0.78rem;">{detail}</span>' if detail else ""
                    st.markdown(
                        f'<div class="solution-line"><strong style="color:#a0e0c0;">{title}</strong>'
                        f'{urg_badge}{detail_html}</div>',
                        unsafe_allow_html=True)

            # Web Research (Wikipedia + DuckDuckGo)
            web_ctx = cached_analysis.get("web_context", "")
            if web_ctx:
                st.markdown("<div style='margin-top:0.8rem;'></div>", unsafe_allow_html=True)
                st.markdown(
                    '<div style="font-size:0.75rem;font-weight:700;letter-spacing:0.1em;'
                    'text-transform:uppercase;color:#5555aa;margin-bottom:0.5rem;">Web Research</div>',
                    unsafe_allow_html=True)
                for block in web_ctx.strip().split("\n\n"):
                    lines = block.strip().splitlines()
                    if not lines:
                        continue
                    header = lines[0].strip("[]") if lines[0].startswith("[") else ""
                    body   = "\n".join(lines[1:]) if header else block
                    source_icon = "📖" if "Wikipedia" in header else "🌐"
                    header_html = (
                        f'<div style="font-size:0.72rem;font-weight:600;color:#7070b8;'
                        f'margin-bottom:3px;">{source_icon} {header}</div>'
                        if header else ""
                    )
                    st.markdown(
                        f'{header_html}'
                        f'<div style="font-size:0.80rem;color:#8888bb;line-height:1.65;'
                        f'background:#0f0f1e;border-left:2px solid #2a2a50;'
                        f'border-radius:0 6px 6px 0;padding:0.5rem 0.8rem;'
                        f'margin-bottom:0.5rem;white-space:pre-wrap;">{body}</div>',
                        unsafe_allow_html=True)

    st.markdown("<div style='margin-top:0.6rem;'></div>", unsafe_allow_html=True)

    # ── Auto-analyze on open ──────────────────────────────────────────────────
    analysis = st.session_state.analysis_cache.get(lid)

    if not analysis:
        prog_bar = st.progress(0)
        status   = st.empty()
        status.markdown("🧠 Analyzing…")
        prog_bar.progress(10)
        analysis = analyze_lead(lead, force_refresh=True)
        st.session_state.analysis_cache[lid] = analysis
        prog_bar.progress(100)
        status.empty()
        prog_bar.empty()
        st.rerun()

    # ── Generate button ───────────────────────────────────────────────────────
    gc1, gc2 = st.columns([2, 1])
    gen_btn   = gc1.button("⚡ Generate Email", type="primary",
                            key=f"gen_{lid}", use_container_width=True)
    force_new = gc2.checkbox("Regenerate", key=f"force_{lid}", value=False)

    if gen_btn:
        prog_bar = st.progress(0)
        status   = st.empty()
        status.markdown("✍️ Writing outreach email…")
        generate_output(lead, analysis, "personalized_email", stream=False, force_refresh=force_new)
        prog_bar.progress(100)
        st.session_state.brief_cache[lid] = True
        status.empty()
        prog_bar.empty()
        st.rerun()

    # ── Outreach email ────────────────────────────────────────────────────────
    content = db_get(lid, "output_personalized_email")
    if content:
        subject, body = "", content
        if "Subject:" in content:
            for i, ln in enumerate(content.split("\n")):
                if ln.strip().lower().startswith("subject:"):
                    subject = ln.split(":", 1)[1].strip()
                    body = "\n".join(content.split("\n")[i+1:]).strip()
                    break
        if subject:
            st.markdown(f'<div class="subject-line">📧 {subject}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="email-box">{body}</div>', unsafe_allow_html=True)

        # ── Send / Edit / Download row ────────────────────────────────────────
        already_sent = lid in st.session_state.sent_emails
        sa, sb, sc = st.columns([1, 1, 1])

        if sa.button(
            "✅ Sent" if already_sent else "📤 Mark as Sent",
            key=f"send_{lid}",
            type="primary" if not already_sent else "secondary",
            use_container_width=True,
            disabled=already_sent,
        ):
            from datetime import datetime
            st.session_state.sent_emails[lid] = {
                "name":     lead.get("name", ""),
                "company":  lead.get("company", ""),
                "email":    lead.get("email", ""),
                "sent_at":  datetime.now().strftime("%d %b %Y, %I:%M %p"),
            }
            st.rerun()

        with sb.expander("✏️ Edit"):
            edited = st.text_area("", value=content, height=260,
                                  key=f"edit_email_{lid}", label_visibility="collapsed")
            if st.button("Save", key=f"save_email_{lid}", type="secondary"):
                save_analysis(lid, "output_personalized_email", edited)
                st.success("Saved")

        sc.download_button(
            "⬇ Download",
            data=content.encode(),
            file_name=f"{lead.get('company','lead')}_email.txt",
            mime="text/plain",
            key=f"dl_email_{lid}",
            use_container_width=True,
        )
    else:
        st.markdown(
            '<div class="empty-hint" style="padding:2rem;">Click '
            '<strong>⚡ Generate Email</strong> above to generate the outreach email.</div>',
            unsafe_allow_html=True)



# ── Run ───────────────────────────────────────────────────────────────────────

def main():
    init()
    render_sidebar()
    render_main()


if __name__ == "__main__":
    main()
