TRIDENT_KB = """
NAME= senthil kumar
ROLE= founder & CEO
COMPANY: itTrident (formerly Testing Solutionz / Trident SQA).
TAGLINE: "AI-Powered Software Engineering. From Strategy to Production. Faster Than You Expect."
FOUNDED: 2011 in Chennai, by three engineers.
SIZE: 120+ engineers across 3 offices — India (Chennai HQ), USA (Great Neck, NY), UAE (Ras Al Khaimah).
CERTIFICATIONS: ISO 9001:2015, ISO/IEC 27001:2022 (93 controls).
TRACK RECORD: 89+ projects · 15+ industries · 95% client retention · 12+ year average partnership · zero security breaches.

SERVICES (8 practice lines):
1. Digital Product Engineering — Product Dev, Modernization, Platform Dev, Experience Engineering, Enterprise Apps, BPM, Integrations
2. Data & AI — Data-Intensive Apps, Applied AI, GenAI Enablement, AI Product Integration, Intelligent Automation
3. Quality Engineering — Manual QA, Test Automation, Performance Testing, Security Testing
4. Cloud & Platform — Cloud Security, Cloud Engineering, DevOps, Platform Engineering, Observability/SRE
5. Enterprise Productivity — M365 Digital Workplace, Power Platform, Enterprise Portals, Workflow Automation
6. Cybersecurity — VAPT, Compliance & Audit, Zero Trust
7. Data Engineering & BI
8. Governance & Strategy — Requirements Engineering, Delivery Governance

DOMAINS SERVED (15+): Airline · Banking · Insurance · Mutual Fund · Investment Banking · E-Commerce · CRM · Entertainment/Streaming · Travel · Healthcare · Manufacturing · Education/EdTech · Real Estate · PropTech · Logistics & Supply Chain · Media & Advertising · Telecom · Non-Profit.

TECHNOLOGY STACK:
- Frontend: React, Angular, Vue, Next.js
- Backend: Node.js, Python, .NET, Java, PHP
- Mobile: React Native, Flutter, Ionic, Swift, Kotlin
- DB: MongoDB, MySQL, PostgreSQL, SQL Server
- Cloud: AWS, Azure, GCP, Firebase, Docker, Kubernetes
- CI/CD: Jenkins, Azure DevOps, GitHub Actions, GitLab CI
- AI/ML: OpenAI, DeepSeek AI, TensorFlow, PyTorch, LangChain
- QA: Selenium, Cypress, Playwright, Appium, Postman, JMeter, Gatling
- Security: Burp Suite, OWASP ZAP, SQLmap, Frida, MobSF, Metasploit

NOTABLE PROOF POINTS:
- Allegiant Air: 10+ yr QA/DevOps partnership; 15M+ passengers/yr; 20K+ concurrent users; 60% faster QA cycle; $2.4M annual savings.
- Jazeera Airways: VAPT/OWASP for 8M+ users; critical vulnerabilities remediated.
- Manufacturing AI NCR System: DeepSeek AI for root-cause analysis; 35% scrap reduction; 40% less downtime.
- Healthcare Medical Visa Platform: 10K+ concurrent users; 100% defect-free release; HIPAA-compliant.
- $200M+ Fintech Security: 100K+ users; 99% critical vulnerability reduction.
- Mutual Fund Utilities: $5B+ AUM; 40+ AMC integrations; 100% regulatory compliance.
- Charter Airline AI Copilot: 38% faster flight planning.
- Aviation MRO Dashboard: maintenance reporting 3 days → 4 hours.
- Mid-tier Bank Reconciliation: ~12,000 manual hours/yr eliminated.
- Healthcare ISV Cloud Modernisation: 41% infra cost reduction.
- Manufacturing IoT Platform: 27% less unplanned downtime.
- SaaS Engineering Productivity: release cycle 6 weeks → 8 days.

DELIVERY:
- Engagement Models: Fixed Price · T&M · Dedicated Team · Hybrid (India/USA/UAE).
- Methodology: 5-phase — Discovery → Design → AI-accelerated Sprint Dev → Test & Launch → Support & Scale.
- SLAs: 5-day kickoff · 99.99% uptime · 24/7 global support · 30% faster dev via AI-Velocity Framework.
- Compliance: ISO 9001:2015 + ISO 27001:2022 · regulated-industry experience across Banking, Healthcare, Aviation, Fintech.
"""

TRIDENT_KB_DOC_ID = "trident_kb_v1"
TRIDENT_KB_TITLE  = "itTrident Knowledge Base"


def _parse_kb_identity(kb_text: str) -> tuple[str, str, str]:
    """Extract sender name, company name, and years of experience from the KB doc."""
    import re
    from datetime import date

    name         = ""
    company      = ""
    founded_year = None

    for line in kb_text.splitlines():
        s = line.strip()
        if re.match(r'NAME\s*[=:]', s, re.I) and not name:
            val  = re.split(r'[=:]', s, maxsplit=1)[1].strip()
            name = val.title()
        elif re.match(r'COMPANY\s*[=:]', s, re.I) and not company:
            val     = re.split(r'[=:]', s, maxsplit=1)[1].strip()
            company = re.split(r'[\(,]', val)[0].strip().rstrip('.')
        elif re.match(r'FOUNDED\s*[=:]', s, re.I) and not founded_year:
            m = re.search(r'\b(19|20)\d{2}\b', s)
            if m:
                founded_year = int(m.group())

    years = f"{date.today().year - founded_year} years" if founded_year else "10+ years"
    return name or "Founder", company or "Company", years


SENDER_NAME, COMPANY_NAME, YEARS_EXPERIENCE = _parse_kb_identity(TRIDENT_KB)
