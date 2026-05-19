import cgi
import json
import mimetypes
import os
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(__file__))

from config.settings import COLLECTIONS
from services.chroma_manager import clear_all_collections, get_collection_stats
from services.email_sender import send_email, smtp_configured
from services.intelligence_engine import analyze_lead, get_intelligence_summary
from services.kb_ingestion import ingest_document, ingest_text_note, seed_trident_kb
from services.lead_processor import parse_leads_from_dataframe, save_leads_to_db
from services.outreach_generator import generate_output
from store import (
    clear_all_data,
    clear_all_leads,
    get_all_leads,
    get_analysis,
    get_dashboard_stats,
    get_kb_documents,
    get_outreach_history,
    save_analysis,
)
from utils.document_processor import read_dataframe


ROOT_DIR = Path(__file__).resolve().parent
FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"
API_PREFIX = "/api"

_APP_INITIALIZED = False
_SENT_EMAILS: dict[str, dict] = {}


def _init_app() -> None:
    global _APP_INITIALIZED
    if _APP_INITIALIZED:
        return

    clear_all_data()
    clear_all_collections()
    seed_trident_kb()
    _SENT_EMAILS.clear()
    _APP_INITIALIZED = True


def _parse_email_content(content: str) -> tuple[str, str]:
    subject, body = "", content or ""
    if content and "Subject:" in content:
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if line.strip().lower().startswith("subject:"):
                subject = line.split(":", 1)[1].strip()
                body = "\n".join(lines[i + 1:]).strip()
                break
    return subject, body


def _json_default(value):
    if isinstance(value, (set, tuple)):
        return list(value)
    return str(value)


def _serialize_lead(lead: dict) -> dict:
    lead_id = lead.get("id", "")
    analysis = _cached_analysis_payload(lead_id)
    content = get_analysis(lead_id, "output_personalized_email") or ""
    subject, body = _parse_email_content(content) if content else ("", "")

    summary = get_intelligence_summary(lead, analysis) if analysis else None
    sent = lead_id in _SENT_EMAILS

    payload = {
        "id": lead_id,
        "name": lead.get("name", ""),
        "company": lead.get("company", ""),
        "email": lead.get("email", ""),
        "designation": lead.get("designation") or lead.get("title", ""),
        "title": lead.get("title", ""),
        "industry": lead.get("industry", ""),
        "company_size": lead.get("company_size", ""),
        "location": lead.get("location", ""),
        "website": lead.get("website", ""),
        "linkedin": lead.get("linkedin", ""),
        "existing_services": lead.get("existing_services", ""),
        "portfolio": lead.get("portfolio", ""),
        "revenue": lead.get("revenue", ""),
        "notes": lead.get("notes", ""),
        "has_analysis": bool(analysis),
        "has_email": bool(content),
        "sent": sent,
        "summary": summary,
        "subject": subject,
        "body": body,
    }
    if sent:
        payload["sent_at"] = _SENT_EMAILS[lead_id]["sent_at"]
    return payload


def _cached_analysis_payload(lead_id: str) -> dict | None:
    business_analysis = get_analysis(lead_id, "full_intelligence")
    pain_points = get_analysis(lead_id, "pain_points")
    opportunities = get_analysis(lead_id, "opportunities")
    web_context = get_analysis(lead_id, "web_context") or ""

    if not business_analysis:
        return None

    return {
        "lead_id": lead_id,
        "business_analysis": business_analysis,
        "pain_points": _safe_json_load(pain_points, []),
        "opportunities": _safe_json_load(opportunities, []),
        "web_context": web_context,
        "from_cache": True,
    }


def _safe_json_load(text: str, default):
    if not text:
        return default
    try:
        return json.loads(text)
    except Exception:
        return default


def _lead_detail(lead_id: str) -> dict:
    lead = next((item for item in get_all_leads() if item.get("id") == lead_id), None)
    if not lead:
        return {}

    analysis = _cached_analysis_payload(lead_id)
    content = get_analysis(lead_id, "output_personalized_email") or ""
    subject, body = _parse_email_content(content) if content else ("", "")
    variants = [
        get_analysis(lead_id, "email_variant_1") or "",
        get_analysis(lead_id, "email_variant_2") or "",
        get_analysis(lead_id, "email_variant_3") or "",
    ]

    return {
        "lead": _serialize_lead(lead),
        "analysis_ready": bool(analysis),
        "analysis": analysis,
        "summary": get_intelligence_summary(lead, analysis) if analysis else None,
        "email": {
            "content": content,
            "subject": subject,
            "body": body,
            "variants": variants,
            "sent": lead_id in _SENT_EMAILS,
            "sent_at": _SENT_EMAILS.get(lead_id, {}).get("sent_at", ""),
        },
        "outreach_history": get_outreach_history(lead_id),
    }


def _dashboard_payload(query: str = "") -> dict:
    leads = get_all_leads()
    if query:
        needle = query.lower().strip()
        leads = [
            lead for lead in leads
            if needle in f"{lead.get('company', '')} {lead.get('name', '')} {lead.get('email', '')}".lower()
        ]

    stats = get_dashboard_stats()
    kb_stats = get_collection_stats()
    stats["sent_emails"] = len(_SENT_EMAILS)
    stats["kb_chunks"] = sum(kb_stats.values())

    return {
        "stats": stats,
        "leads": [_serialize_lead(lead) for lead in leads],
        "sent_emails": list(_SENT_EMAILS.values()),
        "knowledge_docs": get_kb_documents(),
        "knowledge_chunks": kb_stats,
    }


def _refresh_dashboard() -> dict:
    return _dashboard_payload()


def _read_json_body(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    raw = handler.rfile.read(length) if length else b""
    if not raw:
        return {}
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return {}


def _read_multipart_form(handler: BaseHTTPRequestHandler) -> cgi.FieldStorage:
    env = {
        "REQUEST_METHOD": "POST",
        "CONTENT_TYPE": handler.headers.get("Content-Type", ""),
    }
    return cgi.FieldStorage(
        fp=handler.rfile,
        headers=handler.headers,
        environ=env,
        keep_blank_values=True,
    )


def _send_json(handler: BaseHTTPRequestHandler, payload, status: int = 200) -> None:
    data = json.dumps(payload, default=_json_default).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
    handler.end_headers()
    handler.wfile.write(data)


def _send_text(handler: BaseHTTPRequestHandler, text: str, status: int = 200, content_type: str = "text/plain; charset=utf-8") -> None:
    data = text.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(data)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(data)


def _serve_static(handler: BaseHTTPRequestHandler, path: str) -> bool:
    if not FRONTEND_DIST.exists():
        return False

    target = FRONTEND_DIST / "index.html" if path in {"/", ""} else FRONTEND_DIST / path.lstrip("/")
    if target.is_dir():
        target = target / "index.html"

    if not target.exists():
        if path.startswith("/api/"):
            return False
        target = FRONTEND_DIST / "index.html"
        if not target.exists():
            return False

    mime = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
    _send_text(handler, target.read_text(encoding="utf-8"), content_type=mime)
    return True


class Handler(BaseHTTPRequestHandler):
    server_version = "AeroMailAPI/1.0"

    def log_message(self, format, *args):
        return

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == f"{API_PREFIX}/health":
            _send_json(self, {"ok": True, "timestamp": datetime.utcnow().isoformat() + "Z"})
            return

        if path == f"{API_PREFIX}/dashboard":
            query = parse_qs(parsed.query).get("q", [""])[0]
            _send_json(self, _dashboard_payload(query))
            return

        if path == f"{API_PREFIX}/sent":
            _send_json(self, {"items": list(_SENT_EMAILS.values())})
            return

        if path == f"{API_PREFIX}/knowledge":
            payload = {
                "documents": get_kb_documents(),
                "collection_stats": get_collection_stats(),
            }
            _send_json(self, payload)
            return

        if path.startswith(f"{API_PREFIX}/leads/"):
            lead_id = path.split("/", 3)[3]
            payload = _lead_detail(lead_id)
            if not payload:
                _send_json(self, {"error": "Lead not found"}, status=404)
                return
            _send_json(self, payload)
            return

        if _serve_static(self, path):
            return

        if path in {"/", ""}:
            if FRONTEND_DIST.exists():
                _serve_static(self, "/")
                return
            _send_text(
                self,
                "AeroMail API is running.\n"
                "Start the React frontend in /frontend or build it to serve static assets.\n"
                f"Health: {API_PREFIX}/health\n",
            )
            return

        _send_json(self, {"error": "Not found"}, status=404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == f"{API_PREFIX}/leads/upload":
            form = _read_multipart_form(self)
            if "file" not in form:
                _send_json(self, {"error": "Missing file"}, status=400)
                return
            file_item = form["file"]
            filename = file_item.filename or "upload.csv"
            file_bytes = file_item.file.read()
            try:
                df = read_dataframe(file_bytes, filename)
                leads, warnings = parse_leads_from_dataframe(df)
                saved = save_leads_to_db(leads)
                payload = {
                    "success": True,
                    "imported": saved,
                    "warnings": warnings,
                    "dashboard": _refresh_dashboard(),
                }
                _send_json(self, payload)
            except Exception as exc:
                _send_json(self, {"error": str(exc)}, status=400)
            return

        if path == f"{API_PREFIX}/knowledge/upload":
            form = _read_multipart_form(self)
            if "file" not in form:
                _send_json(self, {"error": "Missing file"}, status=400)
                return
            file_item = form["file"]
            filename = file_item.filename or "document.txt"
            doc_type = (form.getfirst("doc_type", "solution") or "solution").strip()
            result = ingest_document(file_item.file.read(), filename, doc_type=doc_type)
            status = 200 if result.get("success") else 400
            result["knowledge"] = _refresh_dashboard().get("knowledge_docs", [])
            _send_json(self, result, status=status)
            return

        if path == f"{API_PREFIX}/knowledge/text":
            data = _read_json_body(self)
            title = (data.get("title") or "My Solutions & Services").strip()
            content = data.get("content") or ""
            doc_type = (data.get("doc_type") or "solution").strip()
            result = ingest_text_note(title, content, doc_type=doc_type)
            status = 200 if result.get("success") else 400
            result["knowledge"] = _refresh_dashboard().get("knowledge_docs", [])
            _send_json(self, result, status=status)
            return

        if path == f"{API_PREFIX}/leads":
            _send_json(self, {"error": "Use upload endpoint"}, status=405)
            return

        if path.startswith(f"{API_PREFIX}/leads/") and path.endswith("/analyze"):
            lead_id = path.split("/", 3)[3].rsplit("/", 1)[0]
            lead = next((item for item in get_all_leads() if item.get("id") == lead_id), None)
            if not lead:
                _send_json(self, {"error": "Lead not found"}, status=404)
                return
            analysis = analyze_lead(lead, force_refresh=True)
            payload = _lead_detail(lead_id)
            payload["analysis_result"] = analysis
            _send_json(self, payload)
            return

        if path.startswith(f"{API_PREFIX}/leads/") and path.endswith("/generate-email"):
            lead_id = path.split("/", 3)[3].rsplit("/", 1)[0]
            lead = next((item for item in get_all_leads() if item.get("id") == lead_id), None)
            if not lead:
                _send_json(self, {"error": "Lead not found"}, status=404)
                return
            body = _read_json_body(self)
            force_refresh = bool(body.get("force_refresh", False))
            analysis = _cached_analysis_payload(lead_id)
            if not analysis:
                analysis = analyze_lead(lead, force_refresh=False)
            content = generate_output(
                lead,
                analysis,
                "personalized_email",
                stream=False,
                force_refresh=force_refresh,
            )
            payload = _lead_detail(lead_id)
            payload["generated"] = {
                "content": content,
                "subject": payload["email"]["subject"],
                "body": payload["email"]["body"],
                "variants": payload["email"]["variants"],
            }
            _send_json(self, payload)
            return

        if path.startswith(f"{API_PREFIX}/leads/") and path.endswith("/send-email"):
            lead_id = path.split("/", 3)[3].rsplit("/", 1)[0]
            lead = next((item for item in get_all_leads() if item.get("id") == lead_id), None)
            if not lead:
                _send_json(self, {"error": "Lead not found"}, status=404)
                return
            body = _read_json_body(self)
            content = body.get("content") or get_analysis(lead_id, "output_personalized_email") or ""
            if not content:
                _send_json(self, {"error": "No email draft available"}, status=400)
                return
            if not smtp_configured():
                _send_json(
                    self,
                    {
                        "error": "SMTP is not configured",
                        "hint": "Set SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, and SMTP_FROM_EMAIL in .env",
                    },
                    status=400,
                )
                return
            subject, body_text = _parse_email_content(content)
            try:
                send_email(
                    to_email=lead.get("email", "").strip(),
                    subject=subject or f"Quick note for {lead.get('company', lead.get('name', 'you'))}",
                    body=body_text,
                    reply_to=None,
                )
                sent_at = datetime.now().strftime("%d %b %Y, %I:%M %p")
                _SENT_EMAILS[lead_id] = {
                    "id": lead_id,
                    "name": lead.get("name", ""),
                    "company": lead.get("company", ""),
                    "email": lead.get("email", ""),
                    "sent_at": sent_at,
                }
                _send_json(self, {"success": True, "sent_at": sent_at, "lead": _serialize_lead(lead)})
            except Exception as exc:
                _send_json(self, {"error": str(exc)}, status=500)
            return

        _send_json(self, {"error": "Not found"}, status=404)

    def do_PUT(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path.startswith(f"{API_PREFIX}/leads/") and path.endswith("/email"):
            lead_id = path.split("/", 3)[3].rsplit("/", 1)[0]
            lead = next((item for item in get_all_leads() if item.get("id") == lead_id), None)
            if not lead:
                _send_json(self, {"error": "Lead not found"}, status=404)
                return
            body = _read_json_body(self)
            content = body.get("content", "")
            save_analysis(lead_id, "output_personalized_email", content)
            _send_json(self, {"success": True, "lead": _lead_detail(lead_id)})
            return

        _send_json(self, {"error": "Not found"}, status=404)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == f"{API_PREFIX}/leads":
            clear_all_leads()
            _SENT_EMAILS.clear()
            _send_json(self, {"success": True, "dashboard": _refresh_dashboard()})
            return

        _send_json(self, {"error": "Not found"}, status=404)


def main():
    _init_app()
    host = os.getenv("API_HOST", "127.0.0.1")
    port = int(os.getenv("API_PORT", "8000"))
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"AeroMail API running on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
