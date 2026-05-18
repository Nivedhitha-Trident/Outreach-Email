import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent

DEEPINFRA_API_KEY = os.getenv("DEEPINFRA_API_KEY", "80tQ18Dnwa9lb5eWExGQRoSUnotrQ1Km")
DEEPINFRA_BASE_URL = os.getenv("DEEPINFRA_BASE_URL", "https://api.deepinfra.com/v1/openai")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-ai/DeepSeek-V4-Flash")
EMBED_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-large-en-v1.5")
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")


COLLECTIONS = {
    "solutions_kb": "solutions_kb",
    "case_studies": "case_studies",
    "lead_memory": "lead_memory",
    "outreach_memory": "outreach_memory",
    "industry_knowledge": "industry_knowledge",
    "ai_generated_insights": "ai_generated_insights",
    "company_intelligence": "company_intelligence",
}

LLM_TEMPERATURE = 0.7
LLM_MAX_TOKENS = 2048
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150
EMBEDDING_BATCH_SIZE = 20
TOP_K_RESULTS = 5

# Maps your Excel column names → internal field names
LEAD_FIELD_ALIASES = {
    "name":             ["name", "contact", "contact_name", "full_name", "first_name", "person"],
    "company":          ["company", "organization", "company_name", "employer", "account", "firm"],
    "email":            ["email", "email_address", "work_email", "mail"],
    "designation":      ["designation", "title", "job_title", "role", "position", "dept", "department"],
    "industry":         ["industry", "sector", "vertical", "business_type", "domain"],
    "company_size":     ["company_size", "employees", "headcount", "size", "team_size", "strength"],
    "phone":            ["phone", "phone_number", "mobile", "cell", "telephone", "contact_no"],
    "website":          ["website", "url", "domain", "company_url", "web", "site"],
    "linkedin":         ["linkedin", "linkedin_url", "linkedin_profile", "linkedin_id"],
    "location":         ["location", "city", "country", "region", "geography", "address"],
    "portfolio":        ["portfolio", "portfolio_url", "projects", "work_samples", "works"],
    "case_files":       ["case_files", "case_studies", "case", "cases", "past_work", "references"],
    "existing_services":["existing_services", "current_tools", "tools_used", "stack", "current_services",
                         "services_used", "technology", "tech_stack", "software_used"],
    "revenue":          ["revenue", "annual_revenue", "arr", "mrr", "funding", "turnover"],
    "notes":            ["notes", "description", "comments", "additional_info", "remarks", "details"],
}

ROLE_TIERS = {
    "c_suite":   ["ceo", "cto", "coo", "cfo", "cmo", "ciso", "chief", "president", "chairman", "managing director", "md", "founder", "co-founder"],
    "vp_dir":    ["vp", "vice president", "director", "head of", "svp", "evp"],
    "manager":   ["manager", "lead", "senior manager", "team lead", "principal"],
    "technical": ["engineer", "developer", "architect", "devops", "data scientist", "analyst", "tech"],
    "hr":        ["hr", "human resources", "talent", "recruiter", "people", "workforce"],
    "marketing": ["marketing", "brand", "growth", "digital", "content", "seo", "campaigns"],
    "sales":     ["sales", "business development", "bd", "account", "revenue"],
}
