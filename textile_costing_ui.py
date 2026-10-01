"""Textile Costing Studio — Streamlit frontend for the existing costing API.

Run: streamlit run ui_testing_astra.py
Dependencies: streamlit>=1.64, requests, pandas
Optional dependency: python-dotenv (for .env files)
Optional environment variable: TEXTILE_API_URL (default http://127.0.0.1:8000).
The backend remains the source of truth for all cost calculations.
"""

import json
import math
import os
from datetime import datetime
from urllib.parse import quote
import pandas as pd
import requests
import streamlit as st
try:
    from dotenv import load_dotenv
except ImportError:
    pass  # Environment variables work without the optional .env dependency.
else:
    load_dotenv()




API_BASE_URL = "https://textool.onrender.com"  # Update this if your API runs elsewhe
READ_TIMEOUT = (3, 8)
CALCULATE_TIMEOUT = (3, 30)



GLOBAL_FIELDS = [
    ("saree_cut", "Saree cut · K26", 6.6, 0.1, "%.2f"),
    ("saree_cut_m7", "Saree cut · M7", 6.2, 0.1, "%.2f"),
    ("job_rate_k24", "Job rate · K24", 0.25, 0.01, "%.2f"),
    ("job_rate_m8", "Job rate · M8", 0.28, 0.01, "%.2f"),
    ("total_card", "Total card · O8", 19649.0, 100.0, "%.0f"),
    ("divisor", "Calculation divisor", 9000000.0, 100000.0, "%.0f"),
]
MATERIAL_FIELDS = [
    ("denier", "Denier", 10.0),
    ("panno", "Panno", 10.0),
    ("peak", "Peak", 10.0),
    ("rate", "Rate", 10.0),
]

st.set_page_config(page_title="Textile Costing Studio", page_icon="◈", layout="wide")

STYLE = """
<style>
:root { color-scheme: dark; --ink:#eef3fb; --muted:#a8b6ca; --line:#2a3b52;
        --accent:#60e3c3; --panel:#142136; }
.stApp { background:radial-gradient(ellipse at 85% 0%,#123641 0,transparent 42%),#0b1423;
         color:var(--ink); }
[data-testid="stHeader"] { background:transparent; }
[data-testid="stMainBlockContainer"] { max-width:1500px; padding-top:1.8rem; padding-bottom:3rem; }
[data-testid="stSidebar"] { background:#101c2e; border-right:1px solid var(--line); }
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap:1rem; }
h1,h2,h3,p,label { color:var(--ink); }
h1 { font-size:2.15rem!important; font-weight:720!important; letter-spacing:-1.3px; }
h2 { font-size:1.35rem!important; letter-spacing:-.3px; }
h3 { font-size:1.05rem!important; }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { color:var(--muted)!important; }
[data-testid="stMarkdownContainer"] a { color:var(--accent); }
.brand { display:flex; align-items:center; gap:12px; margin:0 0 28px; }
.brand-icon { background:#60e3c3; color:#10283a; border-radius:12px; padding:7px 12px; font-size:25px; }
.brand-name { font-weight:750; font-size:17px; letter-spacing:.3px; }
.brand-sub { color:#a8b6ca; font-size:11px; letter-spacing:1.6px; margin-top:3px; }
.eyebrow { color:#60e3c3; font-size:11px; font-weight:700; letter-spacing:2px; margin:0 0 8px; }
.hero-copy { color:#b1bfd2; font-size:15px; line-height:1.65; max-width:650px; margin:0 0 12px; }
.status { display:inline-flex; align-items:center; gap:8px; border:1px solid #35564f;
          background:#17382f; color:#9aefd7; padding:7px 12px; border-radius:30px; font-size:12px; }
.status.offline { border-color:#795535; background:#382b21; color:#f2c796; }
.status-dot { width:7px; height:7px; border-radius:50%; background:currentColor; }
.step-label { font-size:11px; font-weight:700; letter-spacing:1.8px; color:#8ba6c7; margin:12px 0 3px; }
.material-title { display:flex; justify-content:space-between; align-items:center; margin-bottom:6px; }
.material-title strong { color:#edf4ff; font-size:15px; letter-spacing:.4px; }
.material-tag { color:#8be8d0; background:#193c3b; border:1px solid #2b5654;
                font-size:10px; letter-spacing:1px; padding:4px 8px; border-radius:7px; }
.empty { text-align:center; padding:48px 20px; border:1px dashed #3a4d68;
         border-radius:16px; background:#111e31; }
.empty-icon { font-size:32px; color:#60e3c3; margin-bottom:12px; }
.empty h3 { margin:0 0 8px; font-size:20px!important; }
.empty p { color:#a8b6ca; font-size:14px; margin:0; }
[data-testid="stVerticalBlockBorderWrapper"] > div { border-color:var(--line)!important; border-radius:16px!important; }
[data-testid="stVerticalBlockBorderWrapper"] { background:rgba(20,33,54,.6); border-radius:16px; }
[data-testid="stNumberInput"] [data-baseweb="input"],
[data-testid="stTextInput"] [data-baseweb="input"] { background:#0d192b; border-color:#354863; border-radius:10px; }
[data-testid="stNumberInput"] input, [data-testid="stTextInput"] input { color:#f2f6fd; font-variant-numeric:tabular-nums; }
[data-testid="stNumberInput"] button { color:#b9c8db; background:#1e3049; }
[data-testid="stNumberInput"] button:hover { background:#2b4763; color:#fff; }
[data-testid="stWidgetLabel"] p { font-size:13px; color:#b9c8db; }
.stButton button, .stDownloadButton button, [data-testid="stPopover"] > button,
[data-testid="stFormSubmitButton"] button { min-height:43px; border-radius:11px;
    font-weight:600; letter-spacing:.1px; transition:background .15s,border-color .15s,box-shadow .15s; }
button[kind="primary"], [data-testid="stFormSubmitButton"] button[kind="primary"] {
    background:linear-gradient(115deg,#70ebc9,#49cfbc); border:1px solid #74e8ce;
    color:#092c2b; box-shadow:0 4px 16px #45d5b51c; }
button[kind="primary"]:hover { background:#91f3d8; border-color:#b0ffe8; color:#092c2b; box-shadow:0 5px 22px #45d5b530; }
button[kind="secondary"], .stDownloadButton button, [data-testid="stPopover"] > button {
    background:#1a2a40; color:#e0eaf7; border:1px solid #3a506d; }
button[kind="secondary"]:hover, .stDownloadButton button:hover, [data-testid="stPopover"] > button:hover {
    background:#253c53; border-color:#64ceb8; color:#fff; }
button p { color:inherit!important; }
[data-testid="stToggle"] label:has(input:checked) > div:first-child { background:#39bfa4!important; }
button:focus-visible, input:focus-visible { outline:2px solid #85f4d6!important; outline-offset:3px; }
button:disabled { opacity:.45; cursor:not-allowed; }
[data-testid="stPills"] button { border-radius:9px; border-color:#3a506d; background:#1a2a40; color:#dce8f7; min-width:38px; }
[data-testid="stPills"] button[aria-pressed="true"] { background:#60e3c3; color:#0b2c2c; border-color:#60e3c3; }
[data-testid="stMetric"] { background:linear-gradient(125deg,#1a3044,#142136); border:1px solid #304761;
    border-radius:14px; padding:18px 20px; min-height:112px; }
[data-testid="stMetricLabel"] p { color:#b6c4d6; font-size:12px; }
[data-testid="stMetricValue"] { color:#8bf0d5; font-size:1.8rem; font-weight:650; }
[data-testid="stTabs"] [role="tablist"] { gap:24px; border-bottom:1px solid #2a3b52; }
[data-testid="stTabs"] [role="tab"] { color:#b1c1d6; padding:12px 2px; }
[data-testid="stTabs"] [role="tab"][aria-selected="true"] { color:#83efd1; }
[data-testid="stTabs"] [data-baseweb="tab-highlight"] { background:#60e3c3; }
[data-testid="stExpander"] { background:#142136; border-color:#304761; border-radius:12px; }
[data-testid="stExpander"] summary { color:#dbe7f7; }
[data-testid="stPopoverBody"] { background:#142136; color:#eef3fb; border-color:#354863; }
[data-testid="stAlert"] { border-radius:12px; }
hr { border-color:#2a3b52!important; }
@media(max-width:760px) {
    [data-testid="stMainBlockContainer"] { padding:1.7rem 1rem; }
    h1 { font-size:2rem!important; } .hero-copy { font-size:14px; }
    [data-testid="stMetric"] { min-height:96px; padding:14px; }
}
@media(prefers-reduced-motion:reduce) { *,*::before,*::after { transition:none!important; animation:none!important; } }
</style>
"""
st.markdown(STYLE, unsafe_allow_html=True)


def http_session():
    """Reuse connections per user session; never retry writes automatically."""
    if "http_session" not in st.session_state:
        st.session_state["http_session"] = requests.Session()
    return st.session_state["http_session"]


def request_json(method, path, payload=None):
    timeout = CALCULATE_TIMEOUT if method == "POST" else READ_TIMEOUT
    with http_session().request(method, f"{API_BASE_URL}{path}", json=payload,
                                timeout=timeout) as response:
        response.raise_for_status()
        if method == "DELETE":
            return True
        return response.json()


def api_request(method, path, payload=None, silent=False):
    """Bound waits and preserve inputs when a request fails."""
    try:
        return request_json(method, path, payload)
    except requests.Timeout:
        if not silent:
            message = "The service took too long to respond. Your inputs are still here."
            if method == "POST":
                message += " Check Previous calculations before retrying: the calculation may have been saved."
                st.session_state.pop("history_data", None)
            st.error(message)
    except (requests.RequestException, ValueError):
        if not silent:
            st.error("The request could not be completed. Check the service connection and try again. Your inputs are still here.")
    return None


def valid_inputs(data):
    """Validate API structure before changing any workspace values."""
    return (isinstance(data, dict)
            and isinstance(data.get("global_params", {}), dict)
            and isinstance(data.get("materials", []), list)
            and all(isinstance(item, dict) for item in data.get("materials", []))
            and len(data.get("materials", [])) <= 10)


def fetch_defaults():
    # Session-scoped: ordinary input edits never wait for an API request.
    if "defaults" not in st.session_state:
        data = request_json("GET", "/defaults")
        if not valid_inputs(data):
            raise ValueError("Invalid defaults response")
        st.session_state["defaults"] = data
    return st.session_state["defaults"]


def fetch_threads():
    # Fetch once per opening or explicit refresh, including failed attempts.
    # An unavailable history service must not stall every input edit.
    if "history_data" not in st.session_state:
        st.session_state["history_data"] = None
        data = api_request("GET", "/threads", silent=True)
        if not (isinstance(data, dict) and isinstance(data.get("threads"), list)
                and all(isinstance(item, dict) for item in data["threads"])):
            return None
        st.session_state["history_data"] = data
    return st.session_state["history_data"]


def new_calculation():
    seed_inputs(st.session_state["defaults"])
    st.session_state.pop("active_thread", None)
    st.session_state["show_history"] = False


def toggle_history():
    opening = not st.session_state.get("show_history", False)
    st.session_state["show_history"] = opening
    if opening:
        st.session_state.pop("history_data", None)


def number(value, fallback=0.0):
    try:
        result = float(value)
        return result if math.isfinite(result) and result >= 0 else float(fallback)
    except (TypeError, ValueError):
        return float(fallback)


def seed_inputs(source):
    """Apply new/loaded data before rendering widgets, clearing stale widget state."""
    for key in list(st.session_state):
        if key.startswith(("param_", "mat_")) or key in ("material_count", "cost_result", "result_payload", "design_no"):
            del st.session_state[key]
    params = source.get("global_params") or {}
    for key, _, fallback, _, _ in GLOBAL_FIELDS:
        st.session_state[f"param_{key}"] = number(params.get(key), fallback)
    materials = source.get("materials") or []
    st.session_state["material_count"] = min(10, max(1, len(materials)))
    for i in range(10):
        material = materials[i] if i < len(materials) else {}
        for field, _, _ in MATERIAL_FIELDS:
            st.session_state[f"mat_{i}_{field}"] = number(material.get(field))
        st.session_state[f"mat_{i}_multi"] = bool(material.get("has_e_multiplier", i > 0))
    st.session_state["design_no"] = str(source.get("design_no") or source.get("title") or "")
    st.session_state["initialized"] = True


def section(number_text, title):
    st.markdown(f'<div class="step-label">{number_text}</div>', unsafe_allow_html=True)
    st.subheader(title)


def display_results(result, payload):
    section("03 / COST OVERVIEW", "Your costing, at a glance")
    cards = st.columns(3)
    cards[0].metric("Final cost · K27", f"₹ {number(result.get('cost')):,.2f}")
    cards[1].metric("Total job · L24", f"₹ {number(result.get('total_job_alt')):,.2f}")
    cards[2].metric("Yarn amount · M24", f"₹ {number(result.get('total_amt_yarn')):,.2f}")
    breakdown, totals, trace = st.tabs(["Material breakdown", "Production totals", "Calculation details"])
    with breakdown:
        material_results = result.get("materials") or []
        if not isinstance(material_results, list) or not all(isinstance(row, dict) for row in material_results):
            material_results = []
        if material_results:
            df = pd.DataFrame(material_results)
            labels = {"material_name": "Material", "denier": "Denier", "peak": "Peak",
                      "panno": "Panno", "rate": "Rate (₹)", "ans": "Answer", "amt": "Amount",
                      "yarn_weight": "Weight (kg)", "yarn_price": "Yarn cost (₹)"}
            available = [col for col in labels if col in df.columns]
            table = df[available].rename(columns=labels)
            st.dataframe(table, width="stretch", hide_index=True)
            st.download_button("Download breakdown · CSV", table.to_csv(index=False).encode("utf-8-sig"),
                               "textile_cost_breakdown.csv", "text/csv", width="stretch", on_click="ignore")
        else:
            st.info("The service did not return a material breakdown for this calculation.")
    with totals:
        fields = [("Total pick · H26", "total_pick", ""), ("Sum amount · I21", "sum_amt", ""),
                  ("Yarn amount · N6", "n6", "₹ "), ("Total job · N9", "total_job", "₹ "),
                  ("Yarn + job · N11", "total_yarn_job", "₹ ")]
        for start in (0, 3):
            cols = st.columns(3)
            for col, (label, key, prefix) in zip(cols, fields[start:start + 3]):
                col.metric(label, f"{prefix}{number(result.get(key)):,.2f}")
    with trace:
        st.caption(f"Execution time: {result.get('execution_time_ms', '—')} ms")
        if result.get("thread_id"):
            st.caption(f"Saved calculation: {result['thread_id']}")
        nodes = result.get("workflow_nodes_executed") or []
        if nodes:
            for index, node in enumerate(nodes, 1):
                st.text(f"{index:02d}  {node}")
        else:
            st.caption("No execution trace was returned.")
        st.download_button("Export calculation · JSON", json.dumps({"inputs": payload, "results": result}, indent=2),
                           "textile_calculation.json", "application/json", width="stretch", on_click="ignore")


# Production settings live in the sidebar; workspace actions stay in the toolbar.
with st.sidebar:
    st.markdown('<div class="brand"><div class="brand-icon">◈</div><div><div class="brand-name">TEXTILE STUDIO</div><div class="brand-sub">COSTING WORKSPACE</div></div></div>', unsafe_allow_html=True)
    st.caption("PRODUCTION SETTINGS")
    st.subheader("Set your foundation")
    st.caption("Shared values applied to every material in this calculation.")

header, actions = st.columns([3, 1.25], vertical_alignment="center")
with header:
    st.markdown('<div class="eyebrow">PRECISION IN EVERY THREAD</div>', unsafe_allow_html=True)
    st.title("Textile Costing Studio")
    st.markdown('<p class="hero-copy">Plan your material mix, calculate production costs and revisit saved estimates.</p>', unsafe_allow_html=True)

try:
    defaults = fetch_defaults()
except (requests.RequestException, ValueError):
    with actions:
        st.caption("Connection unavailable")
    st.error("Production settings could not be loaded. Start the costing service and reconnect.")
    with st.expander("Connection settings"):
        st.code(API_BASE_URL, language=None)
        st.caption("Set TEXTILE_API_URL before starting this app if the backend runs at a different address.")
    if st.button("Reconnect", type="primary"):
        st.rerun()
    st.stop()

with actions:
    st.markdown('<div class="status"><span class="status-dot"></span>Workspace ready</div>', unsafe_allow_html=True)
    st.caption("Manufacturing / Cost planning")

if not st.session_state.get("initialized"):
    seed_inputs(defaults)

# Handle queued actions before any input widget is instantiated.
pending = st.session_state.pop("pending_action", None)
if pending == "load":
    thread_id = st.session_state.pop("pending_thread", "")
    loaded = api_request("GET", f"/threads/{quote(str(thread_id), safe='')}")
    if valid_inputs(loaded):
        seed_inputs({"global_params": loaded.get("global_params", defaults.get("global_params", {})),
                     "materials": loaded.get("materials", defaults.get("materials", [])),
                     "title": loaded.get("design_no") or loaded.get("title", "")})
        st.session_state["active_thread"] = thread_id
        st.session_state["show_history"] = False
        st.toast("Saved inputs loaded. Calculate to refresh the cost.")
    elif loaded is not None:
        st.error("This saved calculation has invalid inputs or more than 10 materials. Your workspace has been kept.")

# Interrupt widget cleanup for hidden materials, so reducing and increasing the
# count does not erase previously entered values.
for state_key in list(st.session_state):
    if state_key.startswith("mat_"):
        st.session_state[state_key] = st.session_state[state_key]

work, new, history = st.columns([2.6, 1, 1.2], vertical_alignment="center")
with work:
    if st.session_state.get("active_thread"):
        st.caption(f"EDITING SAVED CALCULATION · {st.session_state['active_thread']}")
    else:
        st.caption("NEW CALCULATION · Adjust your settings, then add your materials")
with new:
    st.button("＋ New calculation", width="stretch", on_click=new_calculation,
              help="Reset this workspace to its initial defaults. Saved calculations remain available.")
with history:
    st.button("Previous calculations", width="stretch", on_click=toggle_history,
              type="primary" if st.session_state.get("show_history") else "secondary")

if st.session_state.get("show_history", False):
    with st.container(border=True):
        st.subheader("Calculation history")
        st.caption("Load a previous set of inputs to continue working.")
        if st.button("Refresh history", key="refresh_history"):
            st.session_state.pop("history_data", None)
        history_data = fetch_threads()
        threads = history_data.get("threads", []) if isinstance(history_data, dict) else []
        if history_data is None:
            st.warning("History is temporarily unavailable. Use Refresh history to try again.")
        elif not threads:
            st.info("Your saved calculations will appear here.")
        else:
            query = st.text_input("Find a calculation", placeholder="Search by Design No or ID")
            visible = [t for t in threads if query.lower() in f"{t.get('title', '')} {t.get('id', '')}".lower()]
            st.caption(f"{len(visible)} matching calculation(s) · showing up to 20")
            shown_ids = set()
            for item in visible[:20]:
                tid = item.get("id")
                if tid is None or str(tid) in shown_ids:
                    continue
                shown_ids.add(str(tid))
                title = str(item.get("title") or "Untitled calculation")
                updated = str(item.get("updated_at") or "")
                try:
                    updated = datetime.fromisoformat(updated.replace("Z", "+00:00")).strftime("%d %b %Y · %H:%M")
                except ValueError:
                    updated = updated[:16]
                if st.button(f"₹ {number(item.get('cost')):,.2f} · {title[:32]}", key=f"load_{tid}",
                             help=updated or "Load saved inputs", width="stretch"):
                    st.session_state["pending_action"] = "load"
                    st.session_state["pending_thread"] = tid
                    st.rerun()
                with st.expander(f"Manage · {title[:24]}"):
                    st.caption(updated or "Date unavailable")
                    confirm = st.checkbox("Confirm permanent deletion", key=f"confirm_{tid}")
                    if st.button("Delete calculation", key=f"delete_{tid}", disabled=not confirm, width="stretch"):
                        if api_request("DELETE", f"/threads/{quote(str(tid), safe='')}"):
                            st.session_state.pop("history_data", None)
                            if st.session_state.get("active_thread") == tid:
                                st.session_state.pop("active_thread", None)
                            st.rerun()
            st.divider()
            clear_confirm = st.checkbox("Permanently delete all saved calculations", key="confirm_clear")
            if st.button("Clear all history", disabled=not clear_confirm, width="stretch"):
                if api_request("DELETE", "/threads"):
                    st.session_state.pop("history_data", None)
                    st.session_state.pop("active_thread", None)
                    st.rerun()

with st.sidebar:
    global_params = {}
    for key, label, fallback, step, fmt in GLOBAL_FIELDS:
        global_params[key] = st.number_input(label, min_value=0.0, step=step,
                                             format=fmt, key=f"param_{key}")
    st.caption("Applies to the current calculation. Start a new calculation from the toolbar above.")

section("01 / MATERIAL SETUP", "Build your material mix")
st.caption("Choose the total number of materials, including the warp. Values below are editable, not placeholders.")
design_no = st.text_input("Design No (Alphanumeric)", placeholder="Enter design number...", key="design_no")
count = st.pills("Material count", options=list(range(1, 11)), key="material_count") or 1
section("02 / COSTING SETUP", "Fine-tune each material")
materials_input = []
for start in range(0, count, 3):
    columns = st.columns(3)
    for i in range(start, min(start + 3, count)):
        with columns[i - start], st.container(border=True):
            title = "WARP" if i == 0 else f"FEEDER {i:02d}"
            tag = "FOUNDATION" if i == 0 else "WEFT"
            st.markdown(f'<div class="material-title"><strong>{title}</strong><span class="material-tag">{tag}</span></div>', unsafe_allow_html=True)
            # Preserve WRAP, the original backend material identifier.
            material = {"material_name": "WRAP" if i == 0 else f"FEEDER-{i}"}
            for row in (MATERIAL_FIELDS[:2], MATERIAL_FIELDS[2:]):
                left, right = st.columns(2)
                for col, (field, label, step) in zip((left, right), row):
                    with col:
                        material[field] = st.number_input(label, min_value=0.0, step=step,
                                                          format="%.2f", key=f"mat_{i}_{field}")
            material["has_e_multiplier"] = st.toggle("Apply E multiplier", key=f"mat_{i}_multi",
                help="Enable the 4-parameter calculation. Disable for the 3-parameter warp calculation.")
            materials_input.append(material)

payload = {"materials": materials_input, "global_params": global_params, "design_no": design_no}
st.write("")
with st.container(border=True):
    summary, calculate = st.columns([2, 1], vertical_alignment="center")
    with summary:
        st.markdown(f"**{count} material{'s' if count != 1 else ''} ready for costing**")
        st.caption("Review your yarn rates and production settings before calculating.")
    with calculate:
        clicked = st.button("Calculate production cost →", type="primary", width="stretch")

if clicked:
    if global_params["divisor"] <= 0:
        st.error("Set the calculation divisor above zero in Production settings.")
    elif global_params["saree_cut"] <= 0 or global_params["saree_cut_m7"] <= 0:
        st.error("Both saree cut values must be above zero.")
    else:
        with st.spinner("Calculating your production cost…"):
            result = api_request("POST", "/calculate", payload)
        if isinstance(result, dict) and number(result.get("cost"), -1) >= 0:
            st.session_state.pop("history_data", None)
            st.session_state["show_history"] = False
            st.session_state["cost_result"] = result
            st.session_state["result_payload"] = payload
            if result.get("thread_id"):
                st.session_state["active_thread"] = result["thread_id"]
            st.success("Calculation complete. Your cost breakdown is ready.")
        elif result is not None:
            st.error("The service returned an incomplete calculation. Please try again.")

result = st.session_state.get("cost_result")
if result:
    result_payload = st.session_state.get("result_payload", {})
    if result_payload != payload:
        st.warning("Inputs have changed. The results below show the previous calculation. Calculate again to update them.")
    display_results(result, result_payload)
else:
    st.markdown('<div class="empty"><div class="empty-icon">◈</div><h3>A clear view of your production cost</h3><p>Complete your material mix and calculate to see costs, yarn weights and job totals here.</p></div>', unsafe_allow_html=True)

st.caption("TEXTILE COSTING STUDIO  /  All amounts in INR · Costs are calculated by your connected service")
