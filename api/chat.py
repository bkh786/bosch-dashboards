"""
Bosch Dashboard — Gemini AI Chat Assistant Serverless Handler (/api/chat)
Pre-loads master datasets (Program & QC) into memory and interfaces with
Google Gemini 2.0 Flash for instant, data-aware intelligence without
re-querying external files on every visitor prompt.
"""

from http.server import BaseHTTPRequestHandler
import urllib.request
import urllib.error
import urllib.parse
import json
import os
import sys

# Reference project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# In-memory cached dataset to prevent disk re-reads on every query
_CACHE = {
    "program": None,
    "program_mtime": 0,
    "qc": None,
    "qc_mtime": 0
}

def load_dotenv():
    """Load variables from .env or .env.local if present."""
    for env_name in [".env", ".env.local"]:
        env_path = os.path.join(BASE_DIR, env_name)
        if os.path.exists(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip('"').strip("'")
                            if k not in os.environ:
                                os.environ[k] = v
            except Exception:
                pass

# Attempt loading .env once at module import
load_dotenv()

def resolve_api_key(override_key=None, header_key=None):
    """Resolve GEMINI_API_KEY from override, headers, environment, or .env."""
    if override_key and override_key.strip():
        return override_key.strip()
    if header_key and header_key.strip():
        return header_key.strip()
    env_key = os.environ.get("GEMINI_API_KEY")
    if env_key and env_key.strip():
        return env_key.strip()
    load_dotenv()
    return os.environ.get("GEMINI_API_KEY", "").strip()

def get_program_data():
    """Retrieve pre-parsed Program Performance dataset with caching."""
    filepath = os.path.join(BASE_DIR, "data.json")
    if not os.path.exists(filepath):
        return None
    try:
        mtime = os.path.getmtime(filepath)
        if _CACHE["program"] is None or _CACHE["program_mtime"] != mtime:
            with open(filepath, "r", encoding="utf-8") as f:
                _CACHE["program"] = json.load(f)
                _CACHE["program_mtime"] = mtime
        return _CACHE["program"]
    except Exception as e:
        print(f"Error loading data.json: {e}")
        return None

def get_qc_data():
    """Retrieve pre-parsed QC Tracker dataset with caching."""
    filepath = os.path.join(BASE_DIR, "data_qc.json")
    if not os.path.exists(filepath):
        return None
    try:
        mtime = os.path.getmtime(filepath)
        if _CACHE["qc"] is None or _CACHE["qc_mtime"] != mtime:
            with open(filepath, "r", encoding="utf-8") as f:
                _CACHE["qc"] = json.load(f)
                _CACHE["qc_mtime"] = mtime
        return _CACHE["qc"]
    except Exception as e:
        print(f"Error loading data_qc.json: {e}")
        return None

def build_system_instruction(dashboard_type="program", active_filters=None):
    """Build pre-loaded domain context and dataset for Gemini in compact, high-density format."""
    parts = []
    
    parts.append(
        "You are the Bosch Field Operations & VM Performance AI Copilot for the "
        "Bosch Visual Merchandising Program (operated by Channelplay).\n"
        "Your role is to assist visitors, operations managers, AOMs, and executives "
        "by instantly answering queries regarding visual merchandising field execution, "
        "targets, coverage rates, man-days, productivity, and quality audit compliance.\n\n"
        "### KEY OPERATIONAL BENCHMARKS & METRIC DEFINITIONS:\n"
        "- First Visit Time Adherence: Target benchmark is check-in by 11:30 AM.\n"
        "- Average Productivity: Benchmark target is ~4.0 visits per working man-day.\n"
        "- Category A (Cat A) Outlets: High-priority outlets requiring a 1st visit and a 2nd follow-up visit.\n"
        "- Category B (Cat B) Outlets: Secondary priority stores requiring regular monthly coverage.\n"
        "- Coverage Achievement %: (Coverage Achievement / Coverage Target).\n"
        "- Visit Achievement %: (Visits Achieved / Visit Target).\n"
        "- Productive Visit %: (Productive Visits / Total Visits) — visits resulting in actual display/POSM work.\n"
        "- Man-Days Achievement %: (Man-days Achieved / Target Man-days).\n"
        "- Base Town (BT) Outlets vs UPC Outlets: Base town outlets are in the VM's home city; UPC are outstation/upcountry.\n"
        "- Final Achievement & Rank: Official executive score ranking all Visual Merchandisers.\n"
        "- Quality Audit (QC Tracker): Benchmark target is ≥ 80% approval. Evaluates Display Audit (Ref, WM, DW, Chimney, 360 photo), "
        "External & Internal Visibility, and Campaign/POSM compliance.\n\n"
        "### TONE & GUIDELINES:\n"
        "- Answer with precise figures, percentages, and names directly from the pre-loaded dataset below.\n"
        "- Use clean, concise Markdown formatting (bullet points, bold highlights, concise summary tables).\n"
        "- If the user asks for top performers or bottom performers, provide ranks, AOM names, and key metrics.\n"
        "- Be proactive: provide actionable context (e.g., highlight if first-visit adherence or Cat A 2nd visits are pulling a score down).\n\n"
    )

    if active_filters:
        parts.append(
            f"### ACTIVE DASHBOARD VIEW / SCREEN STATE:\n"
            f"The visitor currently has the following filters applied on their screen:\n"
            f"{json.dumps(active_filters, indent=2)}\n"
            "If their question pertains to their active selection, focus your analysis on that subset first, "
            "while using the broader dataset for comparison and benchmarks.\n\n"
        )

    # Pre-load Program dataset in compact tabular format (~2.6k tokens)
    if dashboard_type != "qc":
        prog_data = get_program_data()
        if prog_data:
            parts.append(
                f"### MASTER PROGRAM PERFORMANCE DATASET (Month: {prog_data.get('currentMonth')}, Updated: {prog_data.get('dataUpdatedUpto')}):\n\n"
            )

            # 1. AOM Executive Leaderboard Table
            aoms = prog_data.get("aoms", [])
            if aoms:
                parts.append("#### AOM EXECUTIVE PERFORMANCE LEADERBOARD:\n")
                parts.append("Rank|AOM Name|Base Town|Coverage%|Cat A Cov%|Mandays%|Productivity|11:30 Adherence%|Final Ach%\n")
                for a in sorted(aoms, key=lambda x: x.get("Rank", 99)):
                    cov = round((a.get("Coverage %") or 0) * 100, 1)
                    cat_a = round((a.get("Cat A Coverage") or 0) * 100, 1)
                    md = round((a.get("Achi Mandays %") or 0) * 100, 1)
                    prod = round(a.get("Productivity") or 0, 2)
                    adh = round((a.get("First Visit Time Adherence (11:30 AM)") or 0) * 100, 1)
                    fin = round((a.get("Final Achievement") or 0) * 100, 1)
                    parts.append(f"{a.get('Rank')}|{a.get('Aom Name')}|{a.get('Base Town')}|{cov}%|{cat_a}%|{md}%|{prod}|{adh}%|{fin}%\n")
                parts.append("\n")

            # 2. Complete VM Performance Table
            vms = prog_data.get("vms", [])
            if vms:
                parts.append(f"#### COMPLETE VM RANK REPORT ({len(vms)} VMs):\n")
                parts.append("Rank|VM Name|AOM|Region|State|Coverage%|Visits Ach|Cat A 1st%|Cat A 2nd%|Cat B%|Prod%|Avg Prod|11:30 Adh%|Final Ach%\n")
                for v in sorted(vms, key=lambda x: x.get("Rank") or 999):
                    cov = round((v.get("Coverage Achievement %") or 0) * 100, 1)
                    cat1 = round((v.get("Cat A 1st Visit %") or 0) * 100, 1)
                    cat2 = round((v.get("Cat A 2nd Visit %") or 0) * 100, 1)
                    catb = round((v.get("Cat B Coverage %") or 0) * 100, 1)
                    prod_pct = round((v.get("Productive Visit %") or 0) * 100, 1)
                    prod_avg = round(v.get("Avg. Productivity") or 0, 2)
                    adh = round((v.get("First Visit Time Adherence (11:30 AM)") or 0) * 100, 1)
                    fin = round((v.get("Final Achievement") or 0) * 100, 1)
                    parts.append(f"{v.get('Rank')}|{v.get('VM Name')}|{v.get('AOM Name')}|{v.get('Region')}|{v.get('State')}|{cov}%|{v.get('Visits Achieved')}|{cat1}%|{cat2}%|{catb}%|{prod_pct}%|{prod_avg}|{adh}%|{fin}%\n")
                parts.append("\n")

    # Pre-load QC dataset in compact summary format (~1k tokens)
    if dashboard_type == "qc" or dashboard_type == "all":
        qc_data = get_qc_data()
        if qc_data and len(qc_data) > 1:
            rows = qc_data[2:]
            total_audits = len(rows)
            scores = [r[24] for r in rows if len(r) > 24 and r[24] is not None and isinstance(r[24], (int, float))]
            avg_score = round(sum(scores) / len(scores) * 100, 1) if scores else 0

            # Count AOM audits
            aom_counts = {}
            mistake_counts = {}
            for r in rows:
                if len(r) > 9 and r[9]:
                    aom_counts[r[9]] = aom_counts.get(r[9], 0) + 1
                if len(r) > 25 and r[25] and str(r[25]).lower() not in ("none", "na"):
                    mistake_counts[r[25]] = mistake_counts.get(r[25], 0) + 1

            sorted_mistakes = sorted(mistake_counts.items(), key=lambda x: x[1], reverse=True)[:10]

            parts.append(
                f"### MASTER QC PERFORMANCE AUDIT DATASET ({total_audits} Audits, Avg QC Score: {avg_score}%):\n\n"
            )
            parts.append("#### AOM AUDIT VOLUMES:\n")
            for aom, cnt in sorted(aom_counts.items(), key=lambda x: x[1], reverse=True):
                parts.append(f"- {aom}: {cnt} audits\n")
            parts.append("\n#### TOP REPORTED QC MISTAKES:\n")
            for m, cnt in sorted_mistakes:
                parts.append(f"- {m} ({cnt} times)\n")
            parts.append("\n")

    return "".join(parts)


def get_status_dict(api_key=None):
    """Return health and status info."""
    has_key = bool(api_key and len(api_key) > 5)
    prog_data = get_program_data()
    qc_data = get_qc_data()
    return {
        "status": "online",
        "assistant": "Bosch AI Copilot",
        "apiKeyConfigured": has_key,
        "datasets": {
            "programLoaded": prog_data is not None,
            "totalVMs": len(prog_data.get("vms", [])) if prog_data else 0,
            "totalAOMs": len(prog_data.get("aoms", [])) if prog_data else 0,
            "qcLoaded": qc_data is not None,
            "totalQCRows": len(qc_data) if qc_data else 0
        }
    }


def get_available_google_models(api_key):
    """Query Google AI ModelService dynamically to discover supported text models."""
    non_text_tags = ["tts", "embed", "image", "audio", "realtime", "whisper", "deep-research", "imagen", "search"]
    for api_version in ["v1beta", "v1"]:
        try:
            url = f"https://generativelanguage.googleapis.com/{api_version}/models?key={api_key}"
            req = urllib.request.Request(url, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models = data.get("models", [])
                supported = []
                for m in models:
                    methods = m.get("supportedGenerationMethods", [])
                    name = m.get("name", "").replace("models/", "")
                    lower = name.lower()
                    if "generateContent" in methods and not any(tag in lower for tag in non_text_tags):
                        supported.append((api_version, name))
                if supported:
                    return supported
        except Exception as e:
            print(f"[api/chat] ModelService check on {api_version}: {e}")
    return []


def pick_model_candidates(api_key, requested_model=""):
    """Return ordered list of (api_version, model_name) strictly prioritizing available text models."""
    discovered = get_available_google_models(api_key)
    
    preferred = [
        ("v1beta", "gemini-3.8-flash"),
        ("v1beta", "gemini-3.5-flash-lite"),
        ("v1beta", "gemini-flash-lite-latest"),
        ("v1beta", "gemini-2.5-pro"),
        ("v1beta", "gemini-flash-latest"),
        ("v1", "gemini-2.5-pro"),
        ("v1", "gemini-1.5-flash"),
    ]

    candidates = []
    if requested_model:
        clean = requested_model.replace("models/", "")
        candidates.append(("v1beta", clean))
        candidates.append(("v1", clean))

    for item in preferred:
        if item not in candidates:
            candidates.append(item)

    if discovered:
        for ver, name in discovered:
            pair = (ver, name)
            if pair not in candidates:
                candidates.append(pair)

    return candidates


def process_chat_query(body, api_key):
    """Execute Gemini query and return (status_code, result_dict)."""
    prompt = body.get("prompt", "").strip()
    if not prompt:
        return 400, {"error": "Prompt parameter is required."}

    if not api_key:
        return 401, {
            "error": "Missing Gemini API Key. Please provide GEMINI_API_KEY in your .env, Vercel environment, or in the widget settings."
        }

    dashboard_type = body.get("dashboard", "program").lower()
    active_filters = body.get("activeFilters", {})
    history = body.get("history", [])

    system_instruction_text = build_system_instruction(dashboard_type, active_filters)

    contents = []
    for msg in history[-8:]:
        role = "user" if msg.get("role") in ("user", "human") else "model"
        text = msg.get("text") or msg.get("content") or ""
        if text:
            contents.append({
                "role": role,
                "parts": [{"text": text}]
            })

    contents.append({
        "role": "user",
        "parts": [{"text": prompt}]
    })

    gemini_payload = {
        "system_instruction": {
            "parts": [{"text": system_instruction_text}]
        },
        "contents": contents,
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 2048,
            "topP": 0.95
        }
    }

    candidates = pick_model_candidates(api_key, body.get("model", ""))
    last_error_code = 500
    last_error_msg = "Failed to communicate with Gemini API"

    for api_version, model_name in candidates:
        gemini_url = f"https://generativelanguage.googleapis.com/{api_version}/models/{model_name}:generateContent?key={api_key}"
        print(f"[api/chat] Attempting {api_version}/models/{model_name}...")
        try:
            req_data = json.dumps(gemini_payload).encode("utf-8")
            req = urllib.request.Request(
                gemini_url,
                data=req_data,
                headers={"Content-Type": "application/json"}
            )
            # 15s per model attempt allows rapid failover if a model is congested
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                reply_text = ""
                cand = resp_data.get("candidates", [])
                if cand:
                    parts_resp = cand[0].get("content", {}).get("parts", [])
                    reply_text = "".join([p.get("text", "") for p in parts_resp])

                if not reply_text:
                    reply_text = "I received your query but was unable to generate an answer from the dataset."

                print(f"[api/chat] ✓ Success with {api_version}/models/{model_name}!")
                return 200, {
                    "reply": reply_text,
                    "model": model_name,
                    "apiVersion": api_version,
                    "dashboard": dashboard_type,
                    "activeFilters": active_filters
                }

        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            error_msg = f"Gemini API error ({e.code}): {err_body}"
            try:
                err_json = json.loads(err_body)
                if "error" in err_json and "message" in err_json["error"]:
                    error_msg = err_json["error"]["message"]
            except Exception:
                pass

            print(f"[api/chat] ✕ {api_version}/{model_name} failed ({e.code}): {error_msg}")
            last_error_code = e.code
            last_error_msg = error_msg

            is_retryable = (
                e.code in (404, 429, 500, 502, 503, 504)
                or "not found" in error_msg.lower()
                or "no longer available" in error_msg.lower()
                or "high demand" in error_msg.lower()
                or "temporarily unavailable" in error_msg.lower()
                or "overloaded" in error_msg.lower()
            )
            if is_retryable:
                print(f"[api/chat] ↻ Model {model_name} returned {e.code} ({error_msg[:60]}...). Failover to next candidate...")
                continue
            return e.code, {"error": error_msg}

        except Exception as e:
            print(f"[api/chat] ✕ Timeout/Error on {model_name}: {e}. Trying next candidate...")
            last_error_code = 500
            last_error_msg = f"Internal server error: {str(e)}"
            continue

    return last_error_code, {"error": last_error_msg}


class handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, x-gemini-api-key")
        self.end_headers()

    def do_GET(self):
        api_key = resolve_api_key(header_key=self.headers.get("x-gemini-api-key"))
        status_info = get_status_dict(api_key)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(status_info).encode("utf-8"))

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
        try:
            body = json.loads(raw_body)
        except Exception:
            body = {}

        api_key = resolve_api_key(
            override_key=body.get("apiKey"),
            header_key=self.headers.get("x-gemini-api-key")
        )

        status_code, result = process_chat_query(body, api_key)
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(result).encode("utf-8"))
