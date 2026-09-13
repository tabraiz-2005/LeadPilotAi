"""
LeadPilot AI - Streamlit Frontend
==================================
Talks to the FastAPI backend to let a (non-technical) user:
  1. Upload portfolio files (pdf/docx/txt) -> ingested into RAG
  2. Upload a leads CSV -> creates lead records
  3. View a dashboard of leads with fit scores
  4. Drill into a lead, trigger analysis, review AI drafts, and approve/edit/reject

Run locally:   streamlit run app.py
Run in Docker: see Dockerfile (port 8501)

Config:
  BACKEND_URL - base URL of the FastAPI backend (default http://localhost:8000)
"""

import os
import io
import base64
from pathlib import Path
import requests
import streamlit as st
from dotenv import load_dotenv
from embedded_backend import ensure_backend

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
load_dotenv()  # allows a local .env file with BACKEND_URL=... during dev

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
REQUEST_TIMEOUT = 90  # AI research + scoring + two outreach drafts can take time

st.set_page_config(page_title="LeadPilot AI", page_icon="🧭", layout="wide")

ensure_backend()

LOGO_PATH = Path(__file__).resolve().parent / "assets" / "leadpilot-mark.svg"
LOGO_URI = "data:image/svg+xml;base64," + base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii")

# ---------------------------------------------------------------------------
# Visual system — navy + white, intentionally leaving the product flow intact
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

    :root {
        --lp-navy: #08172B;
        --lp-blue: #153E75;
        --lp-accent: #2563EB;
        --lp-accent-hover: #1D4ED8;
        --lp-accent-active: #1E40AF;
        --lp-pale: #EEF4FF;
        --lp-line: #DCE5F0;
        --lp-text: #172033;
        --lp-muted: #64748B;
        --lp-white: #FFFFFF;
        --lp-disabled-bg: #F1F5F9;
        --lp-disabled-text: #94A3B8;
        --lp-shadow-card: 0 1px 2px rgba(15,23,42,.03), 0 4px 6px -1px rgba(15,23,42,.05), 0 12px 28px -12px rgba(15,23,42,.10);
        --lp-shadow-button: 0 1px 2px rgba(15,23,42,.08), 0 4px 10px -4px rgba(37,99,235,.28);
    }

    html, body, [class*="css"], .stApp, button, input, textarea, select {
        font-family: "Plus Jakarta Sans", "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
        text-rendering: optimizeLegibility;
    }
    .stApp { background: #F6F8FC; color: var(--lp-text); }
    [data-testid="stHeader"] { background: rgba(246,248,252,.88); backdrop-filter: blur(14px); }
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #080E1A 0%, #0D1728 55%, #111C30 100%);
        border-right: 1px solid rgba(255,255,255,.08);
    }
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 { color: #F8FAFC !important; }
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] label { color: #CBD5E1 !important; }
    [data-testid="stSidebar"] a { color: #93C5FD !important; }
    [data-testid="stSidebar"] [role="radiogroup"] label {
        padding: .62rem .72rem;
        border: 1px solid transparent;
        border-radius: 11px;
        margin-bottom: .24rem;
        transition: background .22s cubic-bezier(.2,.8,.2,1), border-color .22s cubic-bezier(.2,.8,.2,1), transform .22s cubic-bezier(.2,.8,.2,1);
    }
    [data-testid="stSidebar"] [role="radiogroup"] label:hover {
        background: rgba(148,163,184,.10);
        border-color: rgba(148,163,184,.18);
        transform: translateX(2px);
    }
    [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
        background: rgba(37,99,235,.18);
        border-color: rgba(96,165,250,.32);
    }
    [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p,
    [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) span {
        color: #F8FAFC !important;
        font-weight: 700;
    }
    .block-container { max-width: 1180px; padding-top: 2.2rem; padding-bottom: 4rem; }
    h1, h2, h3 { color: var(--lp-navy) !important; letter-spacing: -.025em; }
    h1 { font-size: 2.25rem !important; font-weight: 750 !important; }
    p, label, [data-testid="stCaptionContainer"] { color: var(--lp-muted); }

    .lp-page-head {
        position: relative;
        overflow: hidden;
        background:
            radial-gradient(circle at 84% 14%, rgba(96,165,250,.18) 0%, rgba(59,130,246,.08) 26%, transparent 58%),
            radial-gradient(circle at 8% 110%, rgba(99,102,241,.14) 0%, transparent 48%),
            linear-gradient(135deg, #081426 0%, #0B1F3A 52%, #102C50 100%);
        padding: 1.65rem 1.8rem;
        border: 1px solid rgba(148,163,184,.16);
        border-radius: 20px;
        box-shadow: 0 2px 4px rgba(2,6,23,.06), 0 18px 44px -20px rgba(8,20,38,.42);
        margin-bottom: 1.5rem;
    }
    .lp-kicker { color: #93C5FD; font-size: .73rem; font-weight: 800; letter-spacing: .15em; text-transform: uppercase; }
    .lp-page-title { color: #F8FAFC; font-size: 2rem; line-height: 1.15; font-weight: 800; margin: .3rem 0 .42rem; }
    .lp-page-subtitle { color: #CBD5E1; font-size: .96rem; max-width: 760px; line-height: 1.62; }
    .lp-brand { padding: .35rem .15rem 1.25rem; }
    .lp-brand-lockup { display: flex; align-items: center; gap: .8rem; }
    .lp-brand-mark { width: 3.15rem; height: 3.15rem; filter: drop-shadow(0 8px 14px rgba(79,70,229,.28)); }
    .lp-brand-title { color: white; font-size: 1.65rem; font-weight: 800; letter-spacing: -.035em; line-height: 1.05; }
    .lp-brand-ai { color: #A5B4FC; }
    .lp-brand-copy { color: #B9CEE6; font-size: .78rem; margin-top: .18rem; }
    .lp-live {
        display: inline-block; margin-top: .75rem; padding: .25rem .58rem;
        color: #C9F7DF; background: rgba(35, 178, 109, .16);
        border: 1px solid rgba(80, 220, 149, .28); border-radius: 99px; font-size: .72rem;
    }

    [data-testid="stFileUploader"] {
        background: #FFFFFF; border: 1px solid var(--lp-line); border-radius: 16px;
        padding: .35rem; box-shadow: var(--lp-shadow-card);
    }
    [data-testid="stFileUploaderDropzone"] {
        background: linear-gradient(145deg, #F8FAFF 0%, #F1F5FC 100%) !important;
        border: 1.5px dashed #9FB3CE !important;
        border-radius: 14px !important;
        padding: 1.35rem 1.2rem !important;
        transition: border-color .22s ease, background .22s ease, box-shadow .22s ease;
    }
    [data-testid="stFileUploaderDropzone"]:hover {
        background: linear-gradient(145deg, #F4F7FF 0%, #EEF4FF 100%) !important;
        border-color: #647FA5 !important;
        box-shadow: inset 0 0 0 1px rgba(37,99,235,.04), 0 8px 24px -16px rgba(37,99,235,.35);
    }
    [data-testid="stFileUploaderDropzone"] button,
    [data-testid="stFileUploaderDropzone"] [data-testid="baseButton-secondary"] {
        background: #FFFFFF !important;
        color: #172033 !important;
        border: 1px solid #B8C7DA !important;
        border-radius: 10px !important;
        box-shadow: 0 1px 2px rgba(15,23,42,.06), 0 3px 8px -4px rgba(15,23,42,.18) !important;
        font-weight: 700 !important;
    }
    [data-testid="stFileUploaderDropzone"] button:hover,
    [data-testid="stFileUploaderDropzone"] [data-testid="baseButton-secondary"]:hover {
        background: #EEF4FF !important;
        color: #1D4ED8 !important;
        border-color: #7FA6D9 !important;
    }
    [data-testid="stMetric"] {
        background: #FFFFFF; border: 1px solid var(--lp-line); border-radius: 14px;
        padding: 1rem 1.1rem; box-shadow: var(--lp-shadow-card);
    }
    [data-testid="stMetricValue"] { color: var(--lp-navy); font-weight: 760; }
    [data-testid="stVerticalBlockBorderWrapper"] {
        background: #FFFFFF; border-color: var(--lp-line) !important;
        border-radius: 16px; box-shadow: var(--lp-shadow-card);
    }
    .lp-lead-hero {
        display: flex; justify-content: space-between; align-items: center; gap: 1rem;
        background: #FFFFFF; border: 1px solid var(--lp-line); border-radius: 16px;
        padding: 1.15rem 1.3rem; margin-bottom: 1rem;
        box-shadow: 0 5px 18px rgba(20, 49, 82, .05);
    }
    .lp-company { color: var(--lp-navy); font-size: 1.35rem; font-weight: 760; }
    .lp-meta { color: var(--lp-muted); font-size: .86rem; margin-top: .25rem; }
    .lp-status {
        color: #174E37; background: #E7F7EF; border: 1px solid #B8E5CF;
        border-radius: 999px; padding: .35rem .7rem; font-size: .78rem;
        font-weight: 700; white-space: nowrap;
    }
    .lp-section-title {
        color: var(--lp-navy); font-size: 1.05rem; font-weight: 750;
        margin-bottom: .15rem;
    }
    .lp-section-copy { color: var(--lp-muted); font-size: .82rem; margin-bottom: .75rem; }
    .stButton > button {
        background: #FFFFFF;
        color: #1E293B;
        border-radius: 10px;
        border: 1px solid #CBD5E1;
        font-weight: 700;
        min-height: 2.65rem;
        box-shadow: 0 1px 2px rgba(15,23,42,.05);
        transition: transform .2s cubic-bezier(.2,.8,.2,1), box-shadow .2s cubic-bezier(.2,.8,.2,1), background-color .2s ease, border-color .2s ease, color .2s ease;
    }
    .stButton > button:hover {
        background: #F8FAFC;
        border-color: #93A9C3;
        color: #0F3F80;
        transform: translateY(-1px);
        box-shadow: 0 4px 6px -1px rgba(15,23,42,.08), 0 2px 4px -2px rgba(15,23,42,.06);
    }
    .stButton > button:active {
        transform: translateY(0) scale(.99);
        box-shadow: inset 0 1px 2px rgba(15,23,42,.10);
    }
    .stButton > button:focus-visible {
        outline: 3px solid rgba(96,165,250,.35) !important;
        outline-offset: 2px;
    }
    .stButton > button[kind="primary"] {
        background: var(--lp-accent);
        color: #FFFFFF;
        border-color: var(--lp-accent);
        box-shadow: var(--lp-shadow-button);
    }
    .stButton > button[kind="primary"]:hover {
        background: var(--lp-accent-hover);
        color: #FFFFFF;
        border-color: var(--lp-accent-hover);
        box-shadow: 0 6px 14px -4px rgba(37,99,235,.45);
    }
    .stButton > button[kind="primary"]:active {
        background: var(--lp-accent-active);
        border-color: var(--lp-accent-active);
        box-shadow: inset 0 2px 4px rgba(15,23,42,.18);
    }
    .stButton > button:disabled,
    .stButton > button[disabled],
    .stButton > button[kind="primary"]:disabled,
    .stButton > button[kind="primary"][disabled] {
        background: var(--lp-disabled-bg) !important;
        color: var(--lp-disabled-text) !important;
        border-color: transparent !important;
        box-shadow: none !important;
        cursor: not-allowed !important;
        opacity: 1 !important;
        transform: none !important;
    }
    .stTextArea textarea, .stTextInput input {
        background: #FFFFFF; border-color: #C9D8E8; border-radius: 10px;
        color: var(--lp-text);
        transition: border-color .18s ease, box-shadow .18s ease;
    }
    .stTextArea textarea:focus, .stTextInput input:focus {
        border-color: #60A5FA !important;
        box-shadow: 0 0 0 3px rgba(96,165,250,.18) !important;
    }
    [data-testid="stAlert"] { border-radius: 12px; border-width: 1px; }
    [data-testid="stExpander"] {
        background: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        overflow: hidden;
    }
    [data-testid="stTabs"] [data-baseweb="tab-list"] {
        gap: .35rem;
        border-bottom: 1px solid #E2E8F0;
    }
    [data-testid="stTabs"] [data-baseweb="tab"] {
        color: #64748B;
        font-weight: 700;
        border-radius: 9px 9px 0 0;
    }
    [data-testid="stTabs"] [aria-selected="true"] { color: #1D4ED8 !important; }
    hr { border-color: var(--lp-line); }

    @media (max-width: 760px) {
        .block-container { padding-top: 1.2rem; }
        .lp-page-head { padding: 1.25rem; border-radius: 14px; }
        .lp-page-title { font-size: 1.65rem; }
    }

    /* LeadPilot dark SaaS surface */
    .stApp { background: #080D17 !important; color: #E5E7EB !important; }
    [data-testid="stHeader"] {
        background: rgba(8,13,23,.88) !important;
        border-bottom: 1px solid rgba(148,163,184,.10);
    }
    .block-container { max-width: 1240px; }
    h1, h2, h3, h4, p, label,
    [data-testid="stMarkdownContainer"],
    [data-testid="stCaptionContainer"] { color: #E5E7EB !important; }
    [data-testid="stCaptionContainer"], .lp-section-copy, .lp-meta { color: #94A3B8 !important; }
    [data-testid="stVerticalBlockBorderWrapper"] {
        background: linear-gradient(145deg, #111827 0%, #0D1422 100%) !important;
        border: 1px solid #263247 !important;
        box-shadow: 0 18px 38px -28px rgba(0,0,0,.9) !important;
    }
    [data-testid="stMetric"] {
        background: linear-gradient(145deg, #151D2C 0%, #101725 100%) !important;
        border: 1px solid #2A374C !important;
    }
    [data-testid="stMetricLabel"] p { color: #94A3B8 !important; }
    [data-testid="stMetricValue"] { color: #F8FAFC !important; }
    .lp-lead-hero {
        background: linear-gradient(135deg, #121A29 0%, #0D1421 100%) !important;
        border-color: #2A374C !important;
    }
    .lp-company, .lp-section-title { color: #F8FAFC !important; }
    [data-testid="stFileUploader"] {
        background: #101725 !important;
        border-color: #2A374C !important;
    }
    [data-testid="stFileUploaderDropzone"] {
        background: linear-gradient(145deg, #171E2E 0%, #111827 100%) !important;
        border-color: #475569 !important;
    }
    [data-testid="stFileUploaderDropzone"]:hover {
        background: linear-gradient(145deg, #1A2440 0%, #121C32 100%) !important;
        border-color: #818CF8 !important;
    }
    [data-testid="stFileUploaderDropzone"] button,
    [data-testid="stFileUploaderDropzone"] [data-testid="baseButton-secondary"] {
        background: #242C3D !important;
        color: #F8FAFC !important;
        border-color: #526078 !important;
    }
    .stTextArea textarea, .stTextInput input {
        background: #0B1220 !important;
        color: #F8FAFC !important;
        border-color: #334155 !important;
    }
    [data-testid="stExpander"] {
        background: #101725 !important;
        border-color: #2A374C !important;
    }
    [data-testid="stExpander"] summary { background: #151D2C !important; }
    [data-testid="stTabs"] [data-baseweb="tab-list"] { border-color: #263247 !important; }
    [data-testid="stTabs"] [data-baseweb="tab"] { color: #94A3B8 !important; }
    [data-testid="stTabs"] [aria-selected="true"] { color: #A5B4FC !important; }
    [data-testid="stDataFrame"] { border: 1px solid #263247; border-radius: 12px; overflow: hidden; }

    /* Dark secondary controls: dashboard actions must never appear white */
    .stButton > button:not(:disabled):not([kind="primary"]),
    [data-testid="baseButton-secondary"]:not(:disabled) {
        background: linear-gradient(145deg, #1B2638 0%, #141D2C 100%) !important;
        color: #E2E8F0 !important;
        border: 1px solid #3A4961 !important;
        box-shadow: 0 6px 16px -10px rgba(0,0,0,.9) !important;
    }
    .stButton > button:not(:disabled):not([kind="primary"]):hover,
    [data-testid="baseButton-secondary"]:not(:disabled):hover {
        background: linear-gradient(145deg, #273653 0%, #1B2840 100%) !important;
        color: #FFFFFF !important;
        border-color: #6366F1 !important;
        box-shadow: 0 10px 24px -12px rgba(99,102,241,.75) !important;
    }
    .stButton > button[kind="primary"]:not(:disabled),
    [data-testid="baseButton-primary"]:not(:disabled) {
        background: linear-gradient(135deg, #6366F1 0%, #4F46E5 60%, #2563EB 100%) !important;
        color: #FFFFFF !important;
        border: 1px solid #818CF8 !important;
        box-shadow: 0 9px 22px -10px rgba(79,70,229,.9) !important;
    }
    .stButton > button[kind="primary"]:not(:disabled):hover,
    [data-testid="baseButton-primary"]:not(:disabled):hover {
        background: linear-gradient(135deg, #7C83FF 0%, #5B55EE 58%, #3478F6 100%) !important;
        transform: translateY(-1px);
    }

    /* Accessible disabled state for the dark interface */
    .stButton > button:disabled,
    .stButton > button[disabled],
    .stButton > button[kind="primary"]:disabled,
    .stButton > button[kind="primary"][disabled],
    [data-testid="baseButton-primary"]:disabled,
    [data-testid="baseButton-primary"][disabled] {
        background: #182131 !important;
        color: #718096 !important;
        border: 1px solid #2D3A4F !important;
        box-shadow: inset 0 1px 0 rgba(255,255,255,.025) !important;
        opacity: 1 !important;
        cursor: not-allowed !important;
        transform: none !important;
    }

    .stButton > button:disabled p,
    .stButton > button[disabled] p,
    [data-testid="baseButton-primary"]:disabled p {
        color: #718096 !important;
    }

    /* Always-visible sidebar open/close control */
    [data-testid="stSidebarCollapseButton"],
    [data-testid="stSidebarCollapsedControl"],
    [data-testid="collapsedControl"] {
        display: flex !important;
        visibility: visible !important;
        opacity: 1 !important;
        z-index: 999999 !important;
    }
    [data-testid="stSidebarCollapseButton"] button,
    [data-testid="stSidebarCollapsedControl"] button,
    [data-testid="collapsedControl"] button {
        background: #4F46E5 !important;
        color: #FFFFFF !important;
        border: 1px solid #818CF8 !important;
        border-radius: 10px !important;
        width: 2.35rem !important;
        height: 2.35rem !important;
        box-shadow: 0 8px 22px -8px rgba(79,70,229,.85) !important;
    }
    [data-testid="stSidebarCollapseButton"] svg,
    [data-testid="stSidebarCollapsedControl"] svg,
    [data-testid="collapsedControl"] svg {
        color: #FFFFFF !important;
        fill: #FFFFFF !important;
        stroke: #FFFFFF !important;
    }
    [data-testid="stSidebarCollapseButton"] button:hover,
    [data-testid="stSidebarCollapsedControl"] button:hover,
    [data-testid="collapsedControl"] button:hover {
        background: #6366F1 !important;
        transform: translateY(-1px) scale(1.03);
    }

    .lp-step-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: .9rem;
        margin: 1rem 0 1.35rem;
    }
    .lp-step-card {
        min-height: 150px;
        padding: 1.15rem;
        border-radius: 15px;
        background: linear-gradient(145deg, #141C2B 0%, #0E1522 100%);
        border: 1px solid #2A374C;
        box-shadow: 0 16px 30px -26px rgba(0,0,0,.95);
    }
    .lp-step-number { color: #818CF8; font-size: .75rem; font-weight: 800; letter-spacing: .1em; }
    .lp-step-title { color: #F8FAFC; font-size: 1rem; font-weight: 800; margin: .6rem 0 .38rem; }
    .lp-step-text { color: #94A3B8; font-size: .82rem; line-height: 1.55; }
    @media (max-width: 900px) { .lp-step-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
    @media (max-width: 580px) { .lp-step-grid { grid-template-columns: 1fr; } }
    </style>
    """,
    unsafe_allow_html=True,
)


def page_header(kicker: str, title: str, subtitle: str):
    st.markdown(
        f"""<div class="lp-page-head">
        <div class="lp-kicker">{kicker}</div>
        <div class="lp-page-title">{title}</div>
        <div class="lp-page-subtitle">{subtitle}</div>
        </div>""",
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------
if "selected_lead_id" not in st.session_state:
    st.session_state.selected_lead_id = None
if "page" not in st.session_state:
    st.session_state.page = "Overview"


# ---------------------------------------------------------------------------
# Small API helper layer
# All backend calls live here so the page functions stay simple, and so we
# have ONE place that handles connection errors / bad status codes.
# ---------------------------------------------------------------------------
class ApiError(Exception):
    """Raised when the backend call fails or returns a non-2xx response."""
    pass


def _handle_response(resp: requests.Response):
    if not resp.ok:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        raise ApiError(f"Backend returned {resp.status_code}: {detail}")
    if resp.content:
        return resp.json()
    return None


def api_get(path: str, params: dict | None = None):
    try:
        resp = requests.get(f"{BACKEND_URL}{path}", params=params, timeout=REQUEST_TIMEOUT)
    except requests.exceptions.RequestException as e:
        raise ApiError(f"Could not reach backend at {BACKEND_URL}. Is it running? ({e})")
    return _handle_response(resp)


def api_post_json(path: str, payload: dict):
    try:
        resp = requests.post(f"{BACKEND_URL}{path}", json=payload, timeout=REQUEST_TIMEOUT)
    except requests.exceptions.RequestException as e:
        raise ApiError(f"Could not reach backend at {BACKEND_URL}. Is it running? ({e})")
    return _handle_response(resp)


def api_post_files(path: str, files: list[tuple[str, tuple[str, bytes, str]]]):
    try:
        resp = requests.post(f"{BACKEND_URL}{path}", files=files, timeout=REQUEST_TIMEOUT)
    except requests.exceptions.RequestException as e:
        raise ApiError(f"Could not reach backend at {BACKEND_URL}. Is it running? ({e})")
    return _handle_response(resp)


@st.cache_data(ttl=60, show_spinner=False)
def get_ai_health():
    return api_get("/health/ai")


# ---------------------------------------------------------------------------
# Page: Overview
# ---------------------------------------------------------------------------
def page_overview():
    page_header(
        "AI-powered prospect intelligence",
        "Turn portfolio evidence into better opportunities",
        "Upload your work and prospect list. LeadPilot researches every company, explains fit, drafts personalized outreach, and keeps you in control.",
    )

    st.markdown(
        """<div class="lp-step-grid">
        <div class="lp-step-card"><div class="lp-step-number">01 · EVIDENCE</div><div class="lp-step-title">Upload portfolio</div><div class="lp-step-text">Add your CV and case studies so every recommendation is grounded in real experience.</div></div>
        <div class="lp-step-card"><div class="lp-step-number">02 · PROSPECTS</div><div class="lp-step-title">Import leads</div><div class="lp-step-text">Upload a clean CSV of companies, contacts, industries and websites.</div></div>
        <div class="lp-step-card"><div class="lp-step-number">03 · INTELLIGENCE</div><div class="lp-step-title">Analyze automatically</div><div class="lp-step-text">Research, portfolio retrieval, fit scoring and outreach generation run together.</div></div>
        <div class="lp-step-card"><div class="lp-step-number">04 · HUMAN GATE</div><div class="lp-step-title">Review and decide</div><div class="lp-step-text">Edit, approve or reject every draft. Nothing is sent automatically.</div></div>
        </div>""",
        unsafe_allow_html=True,
    )

    try:
        leads = api_get("/leads") or []
        portfolio = api_get("/portfolio") or []
    except ApiError:
        leads, portfolio = [], []

    metrics = st.columns(4)
    metrics[0].metric("Portfolio files", len(portfolio))
    metrics[1].metric("Total leads", len(leads))
    metrics[2].metric("Analyzed", sum(1 for lead in leads if lead.get("status") != "pending"))
    metrics[3].metric("High fit", sum(1 for lead in leads if lead.get("fit_score") == "High"))


# ---------------------------------------------------------------------------
# Page: Upload Portfolio
# ---------------------------------------------------------------------------
def page_upload_portfolio():
    page_header(
        "Step 1 · Build your evidence base", "Upload Portfolio",
        "Add your CV, case studies, or project write-ups. LeadPilot retrieves real evidence from them when scoring prospects and drafting outreach."
    )

    uploaded_files = st.file_uploader(
        "Choose portfolio files (PDF, DOCX, or TXT)",
        type=["pdf", "docx", "txt"],
        accept_multiple_files=True,
        help="You can select multiple files at once (hold Ctrl/Cmd while clicking).",
    )

    if st.button("Upload & Ingest", type="primary", disabled=not uploaded_files):
        with st.spinner("Uploading and processing your portfolio..."):
            try:
                files_payload = [
                    ("files", (f.name, f.getvalue(), f.type or "application/octet-stream"))
                    for f in uploaded_files
                ]
                result = api_post_files("/portfolio/upload", files_payload)
                count = (result or {}).get("ingested_count", len(uploaded_files))
                st.success(f"✅ Success! {count} portfolio item(s) were ingested.")
            except ApiError as e:
                st.error(f"⚠️ Upload failed: {e}")


# ---------------------------------------------------------------------------
# Page: Upload Leads
# ---------------------------------------------------------------------------
def page_upload_leads():
    page_header(
        "Step 2 · Add opportunities", "Upload Leads",
        "Import the companies you want LeadPilot to research, qualify, and prioritize."
    )

    with st.expander("ℹ️ Expected CSV format (click to see example)"):
        st.write("Your CSV must contain these columns:")
        st.code("company_name,website,industry", language="text")
        st.dataframe(
            {
                "company_name": ["Acme Corp", "Globex Inc"],
                "website": ["https://acme.com", "https://globex.com"],
                "industry": ["E-commerce", "Manufacturing"],
            },
            use_container_width=True,
        )

    uploaded_csv = st.file_uploader("Choose a leads CSV file", type=["csv"])

    if st.button("Upload Leads", type="primary", disabled=uploaded_csv is None):
        with st.spinner("Uploading leads..."):
            try:
                files_payload = [("file", (uploaded_csv.name, uploaded_csv.getvalue(), "text/csv"))]
                result = api_post_files("/leads/upload", files_payload)
                lead_ids = (result or {}).get("lead_ids", [])
                st.success(f"✅ Uploaded {len(lead_ids)} lead(s).")
                if lead_ids:
                    progress = st.progress(0, text="Starting automatic AI analysis...")
                    generated = 0
                    failed = []
                    for index, lead_id in enumerate(lead_ids, start=1):
                        progress.progress(
                            (index - 1) / len(lead_ids),
                            text=f"Generating research, fit score, email and LinkedIn draft for lead {index} of {len(lead_ids)}...",
                        )
                        try:
                            api_post_json(f"/leads/{lead_id}/analyze", {})
                            generated += 1
                        except ApiError:
                            failed.append(lead_id)
                        progress.progress(index / len(lead_ids))
                    progress.empty()
                    if generated:
                        st.success(f"✨ AI analysis and outreach drafts generated for {generated} lead(s).")
                    if failed:
                        st.warning(
                            f"{len(failed)} lead(s) could not be analyzed automatically. "
                            "Open them from the dashboard and select Analyze this lead to retry."
                        )
                    st.session_state.page = "Lead Dashboard"
                    if st.button("Open Lead Dashboard →", type="primary"):
                        st.rerun()
            except ApiError as e:
                st.error(
                    "⚠️ Upload failed: "
                    f"{e}\n\nDouble-check your CSV has the columns "
                    "`company_name, website, industry`."
                )


# ---------------------------------------------------------------------------
# Page: Lead Dashboard
# ---------------------------------------------------------------------------
FIT_SCORE_COLORS = {
    "High": "🟢 High",
    "Medium": "🟡 Medium",
    "Low": "🔴 Low",
}


def page_lead_dashboard():
    page_header(
        "Step 3 · Prioritize", "Lead Dashboard",
        "See every prospect in one place, compare fit, and open the strongest opportunities first."
    )

    if st.button("🔄 Refresh"):
        st.rerun()

    with st.spinner("Loading leads..."):
        try:
            leads = api_get("/leads") or []
        except ApiError as e:
            st.error(f"⚠️ Could not load leads: {e}")
            return

    if not leads:
        st.info("No leads yet. Go to **Upload Leads** to add some.")
        return

    high_count = sum(1 for lead in leads if lead.get("fit_score") == "High")
    analyzed_count = sum(1 for lead in leads if lead.get("status") != "pending")
    approved_count = sum(1 for lead in leads if lead.get("status") == "approved")
    metrics = st.columns(4)
    metrics[0].metric("Total Leads", len(leads))
    metrics[1].metric("High Fit", high_count)
    metrics[2].metric("Analyzed", analyzed_count)
    metrics[3].metric("Approved", approved_count)
    st.markdown("### Prospect pipeline")

    # Header row
    header_cols = st.columns([3, 2, 2, 2, 2])
    for col, label in zip(header_cols, ["Company", "Industry", "Fit Score", "Status", ""]):
        col.markdown(f"**{label}**")

    for lead in leads:
        with st.container(border=True):
            cols = st.columns([3, 2, 2, 2, 2])
            cols[0].markdown(f"**{lead.get('company_name', '—')}**")
            cols[1].write(lead.get("industry", "—"))
            fit_score = lead.get("fit_score")
            cols[2].write(FIT_SCORE_COLORS.get(fit_score, "⚪ Not scored"))
            cols[3].write((lead.get("status") or "pending").title())
            if cols[4].button("View Details →", key=f"view_{lead['id']}", type="primary", use_container_width=True):
                st.session_state.selected_lead_id = lead["id"]
                st.session_state.page = "Lead Detail & Approval"
                st.rerun()


# ---------------------------------------------------------------------------
# Page: Lead Detail & Approval
# ---------------------------------------------------------------------------
def page_lead_detail():
    page_header(
        "Step 4 · Human decision", "Lead Intelligence & Approval",
        "Review the evidence, refine the message, and keep final judgment in human hands."
    )

    lead_id = st.session_state.selected_lead_id
    if lead_id is None:
        st.info("No lead selected. Go to **Lead Dashboard** and click 'View Details' on a lead.")
        return

    with st.spinner("Loading lead details..."):
        try:
            lead = api_get(f"/leads/{lead_id}")
        except ApiError as e:
            st.error(f"⚠️ Could not load lead: {e}")
            return

    if lead is None:
        st.warning("Lead not found.")
        return

    company_name = lead.get("company_name", "Unknown company")
    industry = lead.get("industry") or "Industry not provided"
    status = (lead.get("status") or "pending").title()
    website = lead.get("website") or "No website provided"
    contact_name = lead.get("contact_name") or "No contact provided"
    st.markdown(
        f"""<div class="lp-lead-hero">
        <div><div class="lp-company">{company_name}</div>
        <div class="lp-meta">{industry} &nbsp;•&nbsp; {website} &nbsp;•&nbsp; {contact_name}</div></div>
        <div class="lp-status">{status}</div></div>""",
        unsafe_allow_html=True,
    )

    analyzed = bool(lead.get("research") or lead.get("fit_score"))

    if not analyzed:
        st.warning("This lead hasn't been analyzed yet.")
        if st.button("🤖 Analyze this lead", type="primary"):
            with st.spinner("Running research, fit scoring, and outreach drafting... this can take a moment."):
                try:
                    api_post_json(f"/leads/{lead_id}/analyze", {})
                    st.success("Analysis complete!")
                    st.rerun()
                except ApiError as e:
                    st.error(f"⚠️ Analysis failed: {e}")
        return

    action_left, action_right = st.columns([1, 3])
    with action_left:
        if st.button("✦ Regenerate AI analysis", use_container_width=True):
            with st.spinner("Refreshing research, fit score and outreach drafts..."):
                try:
                    api_post_json(f"/leads/{lead_id}/analyze", {})
                    get_ai_health.clear()
                    st.success("AI analysis and drafts regenerated.")
                    st.rerun()
                except ApiError as error:
                    st.error(f"AI generation failed: {error}")
    with action_right:
        st.caption("Use Regenerate after correcting the Groq key or updating portfolio evidence.")

    summary_col, fit_col = st.columns([1.15, 1], gap="large")
    with summary_col:
        with st.container(border=True):
            st.markdown('<div class="lp-section-title">🏢 Company research</div>', unsafe_allow_html=True)
            st.markdown('<div class="lp-section-copy">What the research agent learned about this prospect.</div>', unsafe_allow_html=True)
            st.write(lead.get("company_summary") or "No company summary was returned.")
            sources = lead.get("evidence_sources") or []
            if sources:
                st.markdown("**Research sources**")
                for source in sources:
                    st.write(f"• {source}")

    with fit_col:
        with st.container(border=True):
            st.markdown('<div class="lp-section-title">🎯 Fit assessment</div>', unsafe_allow_html=True)
            st.markdown('<div class="lp-section-copy">How strongly this prospect matches your experience.</div>', unsafe_allow_html=True)
            fit_score = lead.get("fit_score") or "Unknown"
            confidence = lead.get("confidence")
            metric_col, confidence_col = st.columns(2)
            metric_col.metric("Fit", FIT_SCORE_COLORS.get(fit_score, fit_score))
            confidence_text = f"{round(float(confidence) * 100)}%" if confidence is not None else "—"
            confidence_col.metric("Confidence", confidence_text)
            st.write(lead.get("fit_explanation") or "No fit explanation was returned.")
            matching_skills = lead.get("matching_skills") or []
            if matching_skills:
                st.markdown("**Matching skills**")
                st.write(" • ".join(matching_skills))

    with st.container(border=True):
        st.markdown('<div class="lp-section-title">📎 Portfolio evidence</div>', unsafe_allow_html=True)
        st.markdown('<div class="lp-section-copy">Actual portfolio excerpts used by the AI to score and personalize this lead.</div>', unsafe_allow_html=True)
        evidence = lead.get("portfolio_evidence") or []
        if evidence:
            for index, item in enumerate(evidence, start=1):
                with st.expander(f"Evidence {index}", expanded=False):
                    st.write(item)
        else:
            st.info("No portfolio evidence was found. Upload a portfolio, then analyze this lead again.")

    with st.container(border=True):
        st.markdown('<div class="lp-section-title">✉️ Outreach workspace</div>', unsafe_allow_html=True)
        st.markdown('<div class="lp-section-copy">Review and edit both drafts before making your decision.</div>', unsafe_allow_html=True)
        email_tab, linkedin_tab = st.tabs(["📧 Email", "💼 LinkedIn"])
        with email_tab:
            email_draft = st.text_area(
                "Email draft", value=lead.get("email_draft") or "", height=240,
                help="Edit this message before approval if needed.", key=f"email_{lead_id}",
            )
        with linkedin_tab:
            linkedin_draft = st.text_area(
                "LinkedIn message draft", value=lead.get("linkedin_draft") or "", height=180,
                help="Edit this message before approval if needed.", key=f"linkedin_{lead_id}",
            )

    with st.container(border=True):
        st.markdown('<div class="lp-section-title">✅ Final decision</div>', unsafe_allow_html=True)
        st.markdown('<div class="lp-section-copy">Nothing is sent automatically. You remain in control.</div>', unsafe_allow_html=True)
        decision = st.radio(
            "Decision", options=["Approve", "Edit", "Reject"], horizontal=True,
            help="Approve the drafts, save your edits, or reject the outreach.",
        )
        notes = st.text_area("Review notes (optional)", placeholder="Add context for your team...", key=f"notes_{lead_id}")

        if st.button("Save Decision", type="primary", use_container_width=True):
            with st.spinner("Saving your decision..."):
                try:
                    api_post_json(
                        "/approvals",
                        {
                            "lead_id": lead_id,
                            "decision": decision.lower(),
                            "email_draft": email_draft,
                            "linkedin_draft": linkedin_draft,
                            "notes": notes,
                        },
                    )
                    st.success(f"✅ Decision '{decision}' saved for {company_name}.")
                except ApiError as e:
                    st.error(f"⚠️ Could not save decision: {e}")


# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------
def main():
    try:
        backend_online = api_get("/").get("status") == "ok"
    except (ApiError, AttributeError):
        backend_online = False
    connection_label = "● Backend connected" if backend_online else "● Backend offline"
    st.sidebar.markdown(
        f"""<div class="lp-brand">
        <div class="lp-brand-lockup">
        <img class="lp-brand-mark" src="{LOGO_URI}" alt="LeadPilot AI" />
        <div><div class="lp-brand-title">LeadPilot <span class="lp-brand-ai">AI</span></div>
        <div class="lp-brand-copy">Evidence-based lead intelligence</div>
        </div></div>
        <div class="lp-live">{connection_label}</div>
        </div>""",
        unsafe_allow_html=True,
    )

    if backend_online:
        try:
            ai_health = get_ai_health()
            if ai_health.get("status") == "ok":
                st.sidebar.success(f"✦ AI ready · {ai_health.get('model', 'Groq')}")
            else:
                st.sidebar.error(f"AI unavailable: {ai_health.get('message', 'Check backend/.env')}")
        except ApiError as error:
            st.sidebar.error(f"AI check failed: {error}")

    pages = {
        "Overview": page_overview,
        "Upload Portfolio": page_upload_portfolio,
        "Upload Leads": page_upload_leads,
        "Lead Dashboard": page_lead_dashboard,
        "Lead Detail & Approval": page_lead_detail,
    }

    choice = st.sidebar.radio(
        "Navigate",
        list(pages.keys()),
        index=list(pages.keys()).index(st.session_state.page),
    )
    st.session_state.page = choice

    pages[choice]()


if __name__ == "__main__":
    main()
