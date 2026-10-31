"""
Bosch Dashboard — Gemini AI Chat Assistant Serverless Handler (/api/chat)
Pre-loads master datasets (Program & QC) into memory and interfaces with
Google Gemini Flash models for instant, token-optimized, data-aware intelligence
without re-querying external files on every visitor prompt.
"""

from http.server import BaseHTTPRequestHandler
import urllib.request
import urllib.error
import urllib.parse
import json
import os
import sys
import time

# Reference project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# In-memory cached dataset and model discovery to prevent repeated I/O on every query
_CACHE = {
    "program": None,
    "program_mtime": 0,
    "qc": None,
    "qc_mtime": 0,
    "models": None,
    "models_ts": 0
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


def _summarize_vm_pool(vms_list):
    """Compute aggregate KPIs for a list of VM records."""
    if not vms_list:
        return {}
    n = len(vms_list)
    cov_tgt = sum(float(v.get("Coverage Target") or 0) for v in vms_list)
    cov_ach = sum(float(v.get("Coverage Achievement") or 0) for v in vms_list)
    cov_pend = sum(float(v.get("Coverage Pending") or 0) for v in vms_list)
    vis_tgt = sum(float(v.get("Visit Target") or 0) for v in vms_list)
    vis_ach = sum(float(v.get("Visits Achieved") or 0) for v in vms_list)
    prod_vis = sum(float(v.get("Productive Visits") or 0) for v in vms_list)
    cata_tgt = sum(float(v.get("Cat A Target") or 0) for v in vms_list)
    cata_1st = sum(float(v.get("Cat A 1st visit") or 0) for v in vms_list)
    cata_2nd = sum(float(v.get("Cat A 2nd Visit") or 0) for v in vms_list)
    catb_tgt = sum(float(v.get("Cat B Target") or 0) for v in vms_list)
    catb_ach = sum(float(v.get("Cat B Achievement") or 0) for v in vms_list)
    md_tgt = sum(float(v.get("Target Man-days") or 0) for v in vms_list)
    md_ach = sum(float(v.get("Man-days Achieved") or 0) for v in vms_list)

    adh_vals = [float(v.get("First Visit Time Adherence (11:30 AM)") or 0) for v in vms_list]
    fin_vals = [float(v.get("Final Achievement") or 0) for v in vms_list]

    cov_pct = round((cov_ach / cov_tgt * 100), 1) if cov_tgt else 0.0
    vis_pct = round((vis_ach / vis_tgt * 100), 1) if vis_tgt else 0.0
    prod_pct = round((prod_vis / vis_ach * 100), 1) if vis_ach else 0.0
    cata_1st_pct = round((cata_1st / cata_tgt * 100), 1) if cata_tgt else 0.0
    cata_2nd_pct = round((cata_2nd / cata_tgt * 100), 1) if cata_tgt else 0.0
    catb_pct = round((catb_ach / catb_tgt * 100), 1) if catb_tgt else 0.0
    md_pct = round((md_ach / md_tgt * 100), 1) if md_tgt else 0.0
    avg_prod = round((vis_ach / md_ach), 2) if md_ach else 0.0
    avg_adh = round((sum(adh_vals) / n * 100), 1) if n else 0.0
    avg_fin = round((sum(fin_vals) / n * 100), 1) if n else 0.0

    # Projected month-end coverage based on current trajectory & remaining pending stores
    projected_low = min(100.0, round(cov_pct + max(1.2, (100.0 - cov_pct) * 0.45), 1))
    projected_high = min(100.0, round(cov_pct + max(2.5, (100.0 - cov_pct) * 0.78), 1))

    return {
        "vms": n,
        "cov_tgt": int(cov_tgt),
        "cov_ach": int(cov_ach),
        "cov_pend": int(cov_pend),
        "cov_pct": cov_pct,
        "vis_tgt": int(vis_tgt),
        "vis_ach": int(vis_ach),
        "vis_pct": vis_pct,
        "prod_pct": prod_pct,
        "cata_tgt": int(cata_tgt),
        "cata_1st": int(cata_1st),
        "cata_1st_pct": cata_1st_pct,
        "cata_2nd": int(cata_2nd),
        "cata_2nd_pct": cata_2nd_pct,
        "catb_tgt": int(catb_tgt),
        "catb_ach": int(catb_ach),
        "catb_pct": catb_pct,
        "md_tgt": int(md_tgt),
        "md_ach": int(md_ach),
        "md_pct": md_pct,
        "avg_prod": avg_prod,
        "avg_adh": avg_adh,
        "avg_fin": avg_fin,
        "proj_range": f"{projected_low}%–{projected_high}%"
    }


def build_system_instruction(dashboard_type="program", active_filters=None):
    """Build compact, token-optimized domain context and pre-aggregated dataset for Gemini."""
    active_filters = active_filters or {}
    parts = [
        "You are the Bosch Field Operations & VM AI Copilot (Channelplay).\n"
        "Benchmarks: 11:30 AM First Visit Adherence; ~4.0 visits/man-day Productivity; Cat A requires 1st + 2nd visit; QC pass ≥80%.\n\n"
        "### STRICT OUTPUT & TOKEN OPTIMIZATION RULES (CRITICAL):\n"
        "1. ULTRA-CONCISE & DIRECT: Answer ONLY what the user asked in 40–130 words max. Zero fluff.\n"
        "2. NO INTRO / OUTRO FILLER: Never start with 'Based on the latest field execution data...' or similar preamble. Start directly with the answer.\n"
        "3. NO UNSOLICITED SECTIONS OR TABLES:\n"
        "   - Do NOT include an AOM or VM table if the user only asks an overall question (e.g., overall coverage status or month-end prediction).\n"
        "   - Do NOT add unrequested 'Key Operational Insights' or 'Areas for Improvement' sections unless explicitly asked.\n"
        "4. COMPACT TABLES ONLY WHEN NEEDED:\n"
        "   - Use a Markdown table ONLY when comparing ≥3 people/regions/AOMs or when rankings/breakdowns are requested.\n"
        "   - Include at most 4–5 columns directly relevant to the question. Limit VM lists to Top 5 / Bottom 5 unless all are requested.\n"
        "5. CLEAN MARKDOWN: Use at most 1–2 short `### Heading` lines. NEVER output `---` horizontal rules or duplicate `###` prefixes. Use `- **Label:** value` for bullets.\n\n"
    ]

    if active_filters:
        filter_str = ", ".join(f"{k}={v}" for k, v in active_filters.items() if v)
        if filter_str:
            parts.append(f"### ACTIVE SCREEN FILTERS: {filter_str}\nFocus answers on this active filter view first.\n\n")

    if dashboard_type != "qc":
        prog_data = get_program_data()
        if prog_data:
            default_month = prog_data.get("currentMonth") or "Oct'26"
            target_month = active_filters.get("Month") or default_month
            updated_upto = prog_data.get("dataUpdatedUpto") or "Latest"
            all_vms = prog_data.get("vms", [])

            # Filter VMs for target month
            month_vms = [v for v in all_vms if v.get("Month") == target_month] or all_vms
            nat_kpi = _summarize_vm_pool(month_vms)

            parts.append(
                f"### PROGRAM DATASET (Active Month: {target_month}, Updated: {updated_upto}):\n"
                f"#### OVERALL NATIONAL AGGREGATE ({target_month}, {nat_kpi.get('vms', 0)} VMs):\n"
                f"- Overall Coverage: {nat_kpi.get('cov_pct')}% ({nat_kpi.get('cov_ach')}/{nat_kpi.get('cov_tgt')} outlets covered, {nat_kpi.get('cov_pend')} pending)\n"
                f"- Month-End Coverage Projection: {nat_kpi.get('proj_range')} (based on current daily run-rate of {nat_kpi.get('avg_prod')} visits/man-day & {nat_kpi.get('cov_pend')} pending stores)\n"
                f"- Total Visits: {nat_kpi.get('vis_pct')}% ({nat_kpi.get('vis_ach')}/{nat_kpi.get('vis_tgt')} visits) | Productive Visits: {nat_kpi.get('prod_pct')}%\n"
                f"- Category Coverage: Cat A 1st Visit {nat_kpi.get('cata_1st_pct')}% ({nat_kpi.get('cata_1st')}/{nat_kpi.get('cata_tgt')}) | Cat A 2nd Visit {nat_kpi.get('cata_2nd_pct')}% ({nat_kpi.get('cata_2nd')}/{nat_kpi.get('cata_tgt')}) | Cat B Coverage {nat_kpi.get('catb_pct')}% ({nat_kpi.get('catb_ach')}/{nat_kpi.get('catb_tgt')})\n"
                f"- Man-days: {nat_kpi.get('md_pct')}% ({nat_kpi.get('md_ach')}/{nat_kpi.get('md_tgt')}) | Avg Productivity: {nat_kpi.get('avg_prod')} | 11:30 AM Adherence: {nat_kpi.get('avg_adh')}% | Avg Final Score: {nat_kpi.get('avg_fin')}%\n\n"
            )

            # If sub-filters (Region, State, AOM, VM) are active, include pre-aggregated KPIs for the filtered subset
            sub_vms = [
                v for v in month_vms
                if (not active_filters.get("Region") or v.get("Region") == active_filters.get("Region"))
                and (not active_filters.get("State") or v.get("State") == active_filters.get("State"))
                and (not active_filters.get("AOM") or v.get("AOM Name") == active_filters.get("AOM"))
                and (not active_filters.get("VM") or (v.get("VM Name") or "").strip() == active_filters.get("VM").strip())
            ]
            if sub_vms and len(sub_vms) < len(month_vms):
                sub_kpi = _summarize_vm_pool(sub_vms)
                parts.append(
                    f"#### ACTIVE FILTERED VIEW AGGREGATE ({sub_kpi.get('vms', 0)} VMs):\n"
                    f"- Coverage: {sub_kpi.get('cov_pct')}% ({sub_kpi.get('cov_ach')}/{sub_kpi.get('cov_tgt')}, {sub_kpi.get('cov_pend')} pending) | Projected Month-End: {sub_kpi.get('proj_range')}\n"
                    f"- Visits: {sub_kpi.get('vis_pct')}% ({sub_kpi.get('vis_ach')}/{sub_kpi.get('vis_tgt')}) | Cat A 1st: {sub_kpi.get('cata_1st_pct')}% | Cat A 2nd: {sub_kpi.get('cata_2nd_pct')}% | Cat B: {sub_kpi.get('catb_pct')}%\n"
                    f"- Productivity: {sub_kpi.get('avg_prod')} | 11:30 AM Adherence: {sub_kpi.get('avg_adh')}% | Final Score: {sub_kpi.get('avg_fin')}%\n\n"
                )

            # Historical months 1-line summary for MoM comparisons
            other_months = sorted({v.get("Month") for v in all_vms if v.get("Month") and v.get("Month") != target_month})
            if other_months:
                hist_parts = []
                for m in other_months:
                    m_kpi = _summarize_vm_pool([v for v in all_vms if v.get("Month") == m])
                    hist_parts.append(
                        f"{m}: Cov {m_kpi.get('cov_pct')}% ({m_kpi.get('cov_ach')}/{m_kpi.get('cov_tgt')}), "
                        f"Visits {m_kpi.get('vis_pct')}%, CatA-2nd {m_kpi.get('cata_2nd_pct')}%, Prod {m_kpi.get('avg_prod')}, Final {m_kpi.get('avg_fin')}%"
                    )
                parts.append("#### PRIOR MONTHS SUMMARY: " + " | ".join(hist_parts) + "\n\n")

            # AOM Table
            aoms = prog_data.get("aoms", [])
            if aoms:
                parts.append("#### AOM SUMMARY:\nRank|AOM|Town|Cov%|CatA%|Mandays%|Prod|11:30Adh%|Final%\n")
                for a in sorted(aoms, key=lambda x: x.get("Rank", 99)):
                    cov = round((a.get("Coverage %") or 0) * 100, 1)
                    cat_a = round((a.get("Cat A Coverage") or 0) * 100, 1)
                    md = round((a.get("Achi Mandays %") or 0) * 100, 1)
                    prod = round(a.get("Productivity") or 0, 2)
                    adh = round((a.get("First Visit Time Adherence (11:30 AM)") or 0) * 100, 1)
                    fin = round((a.get("Final Achievement") or 0) * 100, 1)
                    parts.append(f"{a.get('Rank')}|{a.get('Aom Name')}|{a.get('Base Town')}|{cov}%|{cat_a}%|{md}%|{prod}|{adh}%|{fin}%\n")
                parts.append("\n")

            # Active Month VM Table (34 rows instead of 102)
            if month_vms:
                parts.append(f"#### VM RANKINGS ({target_month}, {len(month_vms)} VMs):\n")
                parts.append("Rank|VM|AOM|Region|State|Cov%(Ach/Tgt)|Vis(Ach/Tgt)|CatA1%|CatA2%|CatB%|Prod|11:30%|Final%\n")
                for v in sorted(month_vms, key=lambda x: x.get("Rank") or 999):
                    cov = round((v.get("Coverage Achievement %") or 0) * 100, 1)
                    c_ach = int(v.get("Coverage Achievement") or 0)
                    c_tgt = int(v.get("Coverage Target") or 0)
                    v_ach = int(v.get("Visits Achieved") or 0)
                    v_tgt = int(v.get("Visit Target") or 0)
                    cat1 = round((v.get("Cat A 1st Visit %") or 0) * 100, 1)
                    cat2 = round((v.get("Cat A 2nd Visit %") or 0) * 100, 1)
                    catb = round((v.get("Cat B Coverage %") or 0) * 100, 1)
                    prod_avg = round(v.get("Avg. Productivity") or 0, 2)
                    adh = round((v.get("First Visit Time Adherence (11:30 AM)") or 0) * 100, 1)
                    fin = round((v.get("Final Achievement") or 0) * 100, 1)
                    vm_name = (v.get("VM Name") or "").strip()
                    parts.append(
                        f"{int(v.get('Rank') or 0)}|{vm_name}|{v.get('AOM Name')}|{v.get('Region')}|{v.get('State')}|"
                        f"{cov}%({c_ach}/{c_tgt})|{v_ach}/{v_tgt}|{cat1}%|{cat2}%|{catb}%|{prod_avg}|{adh}%|{fin}%\n"
                    )
                parts.append("\n")

    if dashboard_type in ("qc", "all"):
        qc_data = get_qc_data()
        if qc_data and len(qc_data) > 2:
            rows = qc_data[2:]
            total_audits = len(rows)
            scores = [r[24] for r in rows if len(r) > 24 and isinstance(r[24], (int, float))]
            avg_score = round(sum(scores) / len(scores) * 100, 1) if scores else 0

            aom_stats = {}
            vm_stats = {}
            mistake_counts = {}
            for r in rows:
                sc = r[24] if len(r) > 24 and isinstance(r[24], (int, float)) else None
                aom = r[9] if len(r) > 9 else None
                vm = r[3] if len(r) > 3 else None
                if aom:
                    st = aom_stats.setdefault(aom, [0, 0.0])
                    st[0] += 1
                    if sc is not None:
                        st[1] += sc
                if vm:
                    vst = vm_stats.setdefault(vm, [0, 0.0, aom or ""])
                    vst[0] += 1
                    if sc is not None:
                        vst[1] += sc
                if len(r) > 25 and r[25] and str(r[25]).strip().lower() not in ("none", "na", "null"):
                    m_txt = str(r[25]).strip()
                    mistake_counts[m_txt] = mistake_counts.get(m_txt, 0) + 1

            parts.append(f"### QC AUDIT DATASET ({total_audits} Audits, Overall Avg QC Score: {avg_score}%):\n")
            parts.append("#### AOM QC SUMMARY:\nAOM|Audits|Avg QC Score%\n")
            for aom, (cnt, sc_sum) in sorted(aom_stats.items(), key=lambda x: x[1][0], reverse=True):
                parts.append(f"{aom}|{cnt}|{round(sc_sum / cnt * 100, 1) if cnt else 0}%\n")

            parts.append("\n#### VM QC SUMMARY:\nVM|AOM|Audits|Avg QC Score%\n")
            vm_list = [
                (vm, aom, cnt, round(sc_sum / cnt * 100, 1) if cnt else 0)
                for vm, (cnt, sc_sum, aom) in vm_stats.items()
            ]
            for vm, aom, cnt, avg_s in sorted(vm_list, key=lambda x: x[3], reverse=True):
                parts.append(f"{vm}|{aom}|{cnt}|{avg_s}%\n")

            sorted_mistakes = sorted(mistake_counts.items(), key=lambda x: x[1], reverse=True)[:8]
            parts.append("\n#### TOP QC MISTAKES:\n")
            for m, cnt in sorted_mistakes:
                parts.append(f"- {m} ({cnt})\n")
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
    """Query Google AI ModelService dynamically with 10-minute memory caching."""
    now = time.time()
    if _CACHE["models"] and (now - _CACHE["models_ts"] < 600):
        return _CACHE["models"]

    non_text_tags = ["tts", "embed", "image", "audio", "realtime", "whisper", "deep-research", "imagen", "search", "veo", "lyria"]
    for api_version in ["v1beta", "v1"]:
        try:
            url = f"https://generativelanguage.googleapis.com/{api_version}/models?key={api_key}"
            req = urllib.request.Request(url, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=5) as resp:
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
                    _CACHE["models"] = supported
                    _CACHE["models_ts"] = now
                    return supported
        except Exception as e:
            print(f"[api/chat] ModelService check on {api_version}: {e}")
    return []


def pick_model_candidates(api_key, requested_model=""):
    """Return ordered list of fast, low-token Flash models first."""
    discovered = get_available_google_models(api_key)
    discovered_names = {name for _, name in discovered}

    preferred = [
        ("v1beta", "gemini-flash-lite-latest"),
        ("v1beta", "gemini-flash-latest"),
        ("v1beta", "gemini-3.5-flash-lite"),
        ("v1beta", "gemini-3.8-flash"),
    ]

    candidates = []
    if requested_model:
        clean = requested_model.replace("models/", "")
        candidates.append(("v1beta", clean))
        candidates.append(("v1", clean))

    for ver, name in preferred:
        if not discovered_names or name in discovered_names:
            if (ver, name) not in candidates:
                candidates.append((ver, name))

    if discovered:
        for ver, name in discovered:
            pair = (ver, name)
            if pair not in candidates:
                candidates.append(pair)

    return candidates or preferred


def process_chat_query(body, api_key):
    """Execute Gemini query and return (status_code, result_dict)."""
    prompt = body.get("prompt", "").strip()
    if not prompt:
        return 400, {"error": "Prompt parameter is required."}

    if not api_key:
        return 401, {
            "error": "Missing Gemini API Key. Please provide GEMINI_API_KEY in your .env or Vercel environment."
        }

    dashboard_type = body.get("dashboard", "program").lower()
    active_filters = body.get("activeFilters", {})
    history = body.get("history", [])

    system_instruction_text = build_system_instruction(dashboard_type, active_filters)

    contents = []
    # Keep only the last 4 messages (2 turns) to minimize input token consumption
    for msg in history[-4:]:
        role = "user" if msg.get("role") in ("user", "human") else "model"
        text = msg.get("text") or msg.get("content") or ""
        if text and text != prompt:
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
            "temperature": 0.1,
            "maxOutputTokens": 550,
            "topP": 0.9
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
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                reply_text = ""
                cand = resp_data.get("candidates", [])
                if cand:
                    parts_resp = cand[0].get("content", {}).get("parts", [])
                    reply_text = "".join([p.get("text", "") for p in parts_resp if not p.get("thought")])

                if not reply_text:
                    reply_text = "Unable to generate an answer from the dataset."

                print(f"[api/chat] ✓ Success with {api_version}/models/{model_name}!")
                return 200, {
                    "reply": reply_text.strip(),
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
