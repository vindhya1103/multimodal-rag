"""
app.py — DocuChat Streamlit Frontend v3

Fixes applied:
  - Sidebar always visible — collapse button hidden via CSS
  - Dark chat input box — no more white/grey mismatch
  - Multi-session chat history in sidebar (ChatGPT-style)
  - Document memory persisted to doc_memory.json (7-day history)
  - Session navigation — click any past chat to restore messages
  - Full dark / light mode toggle
"""

import os
import json
import uuid
from datetime import datetime, timedelta
import streamlit as st
import requests

API              = os.getenv("DOCUCHAT_API_URL", "http://localhost:8888")
DOC_MEMORY_FILE  = os.path.join(os.path.dirname(__file__), "..", "backend", "doc_memory.json")
DOC_MEMORY_DAYS  = 7
MAX_DOC_MEMORY   = 20


# ══════════════════════════════════════════════════════════════════════════════
# PAGE CONFIG — must be first
# ══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="DocuChat",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ══════════════════════════════════════════════════════════════════════════════
# SESSION STATE DEFAULTS
# ══════════════════════════════════════════════════════════════════════════════

def _init_state():
    defaults = {
        "logged_in":      False,
        "username":       "",
        "theme":          "dark",
        "sessions":       {},          # {id: {title, messages, doc_stats, doc_loaded, created_at}}
        "active_session": None,        # currently selected chat session id
        "doc_loaded":     False,
        "doc_stats":      None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()


# ══════════════════════════════════════════════════════════════════════════════
# DOCUMENT MEMORY  (persisted to JSON across runs)
# ══════════════════════════════════════════════════════════════════════════════

def _load_doc_memory() -> list:
    try:
        if os.path.exists(DOC_MEMORY_FILE):
            with open(DOC_MEMORY_FILE, "r") as f:
                records = json.load(f)
            cutoff = (datetime.now() - timedelta(days=DOC_MEMORY_DAYS)).isoformat()
            return [r for r in records if r.get("uploaded_at", "") >= cutoff]
    except Exception:
        pass
    return []


def _save_doc_memory(records: list):
    try:
        os.makedirs(os.path.dirname(DOC_MEMORY_FILE), exist_ok=True)
        with open(DOC_MEMORY_FILE, "w") as f:
            json.dump(records[-MAX_DOC_MEMORY:], f, indent=2)
    except Exception:
        pass


def _add_doc_to_memory(stats: dict):
    records = _load_doc_memory()
    records.append({
        "filename":    stats.get("filename", "unknown"),
        "chunks":      stats.get("chunks", 0),
        "documents":   stats.get("documents", 0),
        "uploaded_at": datetime.now().isoformat(),
    })
    _save_doc_memory(records)


# ══════════════════════════════════════════════════════════════════════════════
# CHAT SESSION HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _new_session(title: str = "New Chat") -> str:
    sid = str(uuid.uuid4())[:8]
    st.session_state.sessions[sid] = {
        "id":         sid,
        "title":      title,
        "messages":   [],
        "doc_stats":  None,
        "doc_loaded": False,
        "created_at": datetime.now().isoformat(),
    }
    st.session_state.active_session = sid
    return sid


def _current_session() -> dict | None:
    sid = st.session_state.active_session
    return st.session_state.sessions.get(sid)


def _ensure_session():
    """Create a default session if none exists."""
    if not st.session_state.sessions or st.session_state.active_session not in st.session_state.sessions:
        _new_session("New Chat")


def _parse_error(resp) -> str:
    try:
        data = resp.json()
        if isinstance(data, dict):
            return data.get("detail") or data.get("message") or resp.text
        return resp.text
    except Exception:
        return resp.text or "<no response>"


# ══════════════════════════════════════════════════════════════════════════════
# CSS ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def inject_css(theme: str):
    dark = theme == "dark"

    bg          = "#111111"   if dark else "#f7f6f3"
    sidebar_bg  = "#0a0a0a"   if dark else "#efefeb"
    surface     = "#1c1c1c"   if dark else "#ffffff"
    surface2    = "#252525"   if dark else "#f0efe9"
    border      = "#2a2a2a"   if dark else "#dddbd4"
    border2     = "#333333"   if dark else "#ccc"
    text        = "#e8e8e8"   if dark else "#1a1a1a"
    muted       = "#666666"   if dark else "#888888"
    input_bg    = "#1c1c1c"   if dark else "#f0efe9"
    user_bubble = "#6d5ce7"
    bot_bubble  = "#1e1e1e"   if dark else "#ffffff"
    bot_border  = "#2a2a2a"   if dark else "#dddbd4"
    main_bg     = "#141414"   if dark else "#fafaf8"

    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');

    /* ── Reset & Global ── */
    html, body, .stApp, .main, [data-testid="stAppViewContainer"] {{
        background-color: {bg} !important;
        color: {text} !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
    }}
    .main .block-container {{
        background-color: {main_bg} !important;
        padding-top: 1rem !important;
        max-width: 100% !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
    }}

    /* ── Hide Streamlit chrome ── */
    #MainMenu, footer, .stDeployButton, header {{ display: none !important; }}

    /* ── SIDEBAR — always visible, no collapse ── */
    [data-testid="stSidebar"] {{
        background-color: {sidebar_bg} !important;
        border-right: 1px solid {border} !important;
        min-width: 268px !important;
        max-width: 268px !important;
    }}
    /* Hide the collapse arrow button completely */
    button[data-testid="stSidebarCollapseButton"],
    [data-testid="stSidebarCollapseButton"] {{
        display: none !important;
    }}
    /* Hide the expand arrow when collapsed */
    section[data-testid="stSidebarCollapsedControl"],
    [data-testid="collapsedControl"] {{
        display: none !important;
    }}
    /* Force sidebar to stay expanded */
    [data-testid="stSidebar"][aria-expanded="false"] {{
        display: block !important;
        transform: translateX(0) !important;
        min-width: 268px !important;
    }}
    [data-testid="stSidebar"] * {{
        color: {text} !important;
    }}
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] div {{
        color: {text} !important;
    }}

    /* ── Buttons ── */
    .stButton > button {{
        background: #6d5ce7 !important;
        color: white !important;
        border: none !important;
        border-radius: 10px !important;
        font-weight: 500 !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        transition: all 0.15s ease !important;
        width: 100% !important;
    }}
    .stButton > button:hover {{
        background: #8b7cf8 !important;
        transform: translateY(-1px) !important;
    }}
    .stButton > button:active {{
        transform: translateY(0) !important;
    }}

    /* ── Session nav buttons (flat style) ── */
    .session-btn > button {{
        background: transparent !important;
        color: {muted} !important;
        border: 1px solid {border} !important;
        border-radius: 8px !important;
        text-align: left !important;
        font-size: 12px !important;
        padding: 6px 10px !important;
        margin-bottom: 2px !important;
    }}
    .session-btn > button:hover {{
        background: {surface2} !important;
        color: {text} !important;
        transform: none !important;
    }}
    .session-btn-active > button {{
        background: {surface2} !important;
        color: {text} !important;
        border: 1px solid #6d5ce7 !important;
        border-radius: 8px !important;
        text-align: left !important;
        font-size: 12px !important;
        padding: 6px 10px !important;
        margin-bottom: 2px !important;
    }}

    /* ── Form submit buttons ── */
    .stFormSubmitButton > button {{
        background: #6d5ce7 !important;
        color: white !important;
        border: none !important;
        border-radius: 10px !important;
        width: 100% !important;
        padding: 10px 20px !important;
        font-size: 14px !important;
        font-weight: 600 !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
    }}
    .stFormSubmitButton > button:hover {{
        background: #8b7cf8 !important;
    }}

    /* ── Text inputs ── */
    .stTextInput > div > div > input {{
        background: {input_bg} !important;
        border: 1px solid {border2} !important;
        border-radius: 10px !important;
        color: {text} !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        padding: 10px 14px !important;
    }}
    .stTextInput > div > div > input:focus {{
        border-color: #6d5ce7 !important;
        box-shadow: 0 0 0 2px rgba(109,92,231,0.2) !important;
    }}
    .stTextInput > label {{ color: {muted} !important; font-size: 13px !important; }}

    /* ── CHAT INPUT BOX — force dark, single colour ── */
    [data-testid="stChatInput"],
    [data-testid="stChatInputContainer"],
    div[class*="stChatInput"],
    .stChatInput {{
        background-color: {input_bg} !important;
    }}
    [data-testid="stChatInput"] > div,
    [data-testid="stChatInput"] > div > div,
    [data-testid="stChatInputContainer"] > div {{
        background-color: {input_bg} !important;
        border: 1px solid {border2} !important;
        border-radius: 14px !important;
        box-shadow: none !important;
    }}
    [data-testid="stChatInput"] textarea,
    [data-testid="stChatInput"] input,
    [data-testid="stChatInputContainer"] textarea {{
        background-color: {input_bg} !important;
        color: {text} !important;
        caret-color: {text} !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: 14px !important;
        border: none !important;
        box-shadow: none !important;
    }}
    [data-testid="stChatInput"] textarea::placeholder {{
        color: {muted} !important;
    }}
    [data-testid="stChatInput"]:focus-within > div {{
        border-color: #6d5ce7 !important;
    }}
    /* Bottom area where chat input lives */
    [data-testid="stBottom"],
    [data-testid="stBottom"] > div {{
        background-color: {main_bg} !important;
    }}

    /* ── File uploader ── */
    [data-testid="stFileUploader"] > div {{
        background: {surface2} !important;
        border: 1px dashed {border2} !important;
        border-radius: 10px !important;
    }}

    /* ── Tabs ── */
    .stTabs [data-baseweb="tab-list"] {{
        background: transparent !important;
        border-bottom: 1px solid {border} !important;
    }}
    .stTabs [data-baseweb="tab"] {{
        background: transparent !important;
        color: {muted} !important;
        border: none !important;
        font-weight: 500 !important;
        padding: 8px 18px !important;
    }}
    .stTabs [aria-selected="true"] {{
        color: {text} !important;
        border-bottom: 2px solid #6d5ce7 !important;
    }}
    .stTabs [data-baseweb="tab-panel"] {{
        background: transparent !important;
        padding-top: 16px !important;
    }}

    /* ── Alerts ── */
    .stSuccess > div {{
        background: rgba(16,185,129,0.08) !important;
        border: 1px solid rgba(16,185,129,0.2) !important;
        color: #10b981 !important; border-radius: 8px !important;
    }}
    .stError > div {{
        background: rgba(239,68,68,0.08) !important;
        border: 1px solid rgba(239,68,68,0.2) !important;
        color: #f87171 !important; border-radius: 8px !important;
    }}
    .stInfo > div {{
        background: rgba(109,92,231,0.08) !important;
        border: 1px solid rgba(109,92,231,0.2) !important;
        color: #a78bfa !important; border-radius: 8px !important;
    }}
    .stSpinner > div {{ color: #6d5ce7 !important; }}

    /* ── Divider ── */
    hr {{ border-color: {border} !important; margin: 8px 0 !important; opacity: 1 !important; }}

    /* ── Message bubbles ── */
    .msg-user {{
        background: {user_bubble};
        color: white;
        border-radius: 18px 18px 4px 18px;
        padding: 11px 16px;
        max-width: 74%;
        margin-left: auto;
        font-size: 14px;
        line-height: 1.65;
        white-space: pre-wrap;
        word-break: break-word;
        animation: msgIn 0.18s ease;
    }}
    .msg-bot {{
        background: {bot_bubble};
        color: {text};
        border: 1px solid {bot_border};
        border-radius: 18px 18px 18px 4px;
        padding: 13px 17px;
        max-width: 78%;
        font-size: 14px;
        line-height: 1.65;
        white-space: pre-wrap;
        word-break: break-word;
        animation: msgIn 0.18s ease;
    }}
    .row-user {{ display:flex; justify-content:flex-end; margin: 5px 0; }}
    .row-bot  {{ display:flex; justify-content:flex-start; margin: 5px 0; }}
    @keyframes msgIn {{
        from {{ opacity:0; transform:translateY(6px); }}
        to   {{ opacity:1; transform:translateY(0); }}
    }}

    /* ── Source chips ── */
    .chip {{
        display: inline-block;
        background: rgba(109,92,231,0.10);
        color: #a78bfa;
        border: 1px solid rgba(109,92,231,0.22);
        border-radius: 20px;
        padding: 1px 9px;
        font-size: 11px;
        margin: 2px 2px 0 0;
        font-weight: 500;
    }}

    /* ── Stat card ── */
    .stat-card {{
        background: {surface};
        border: 1px solid {border};
        border-radius: 10px;
        padding: 10px 13px;
        margin-top: 6px;
    }}
    .s-row {{
        display: flex; justify-content: space-between;
        font-size: 11px; padding: 4px 0;
        border-bottom: 1px solid {border};
        color: {muted};
    }}
    .s-row:last-child {{ border: none; padding-bottom: 0; }}
    .s-val {{
        color: {text}; font-weight: 600; font-size: 11px;
        max-width: 130px; overflow: hidden;
        text-overflow: ellipsis; white-space: nowrap;
    }}

    /* ── Doc memory card ── */
    .doc-card {{
        background: {surface};
        border: 1px solid {border};
        border-radius: 8px;
        padding: 7px 10px;
        margin-bottom: 5px;
        font-size: 11px;
    }}
    .doc-card-name {{ color: {text}; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 180px; }}
    .doc-card-meta {{ color: {muted}; font-size: 10px; margin-top: 2px; }}

    /* ── Badges ── */
    .badge-purple {{ background:rgba(109,92,231,0.12); color:#a78bfa; border:1px solid rgba(109,92,231,0.25); border-radius:6px; padding:2px 7px; font-size:10px; font-family:monospace; font-weight:600; }}
    .badge-green  {{ background:rgba(16,185,129,0.10); color:#6ee7b7; border:1px solid rgba(16,185,129,0.2); border-radius:6px; padding:2px 7px; font-size:10px; font-family:monospace; font-weight:600; }}
    .badge-amber  {{ background:rgba(245,158,11,0.10); color:#fcd34d; border:1px solid rgba(245,158,11,0.2); border-radius:6px; padding:2px 7px; font-size:10px; font-family:monospace; font-weight:600; }}

    /* ── Welcome screen ── */
    .welcome {{
        text-align: center; padding: 60px 20px; opacity: 0.4;
    }}

    /* ── Section label ── */
    .sect-label {{
        font-size: 10px; font-weight: 700;
        letter-spacing: 0.08em; text-transform: uppercase;
        color: {muted}; margin: 10px 0 5px;
    }}
    </style>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# LOGIN PAGE
# ══════════════════════════════════════════════════════════════════════════════

def show_login():
    inject_css(st.session_state.theme)

    # Theme toggle
    c1, c2 = st.columns([8, 1])
    with c2:
        icon = "☀️" if st.session_state.theme == "dark" else "🌙"
        if st.button(icon, key="lt"):
            st.session_state.theme = "light" if st.session_state.theme == "dark" else "dark"
            st.rerun()

    _, center, _ = st.columns([1, 1.2, 1])
    with center:
        dark    = st.session_state.theme == "dark"
        surface = "#1c1c1c" if dark else "#ffffff"
        border  = "#2a2a2a" if dark else "#dddbd4"
        muted   = "#666666"
        text    = "#e8e8e8" if dark else "#1a1a1a"

        st.markdown(f"""
        <div style="background:{surface}; border:1px solid {border}; border-radius:20px;
                    padding:36px 32px; margin-top:30px; text-align:center; margin-bottom:20px;">
            <div style="font-size:48px; margin-bottom:12px;">📄</div>
            <div style="font-size:26px; font-weight:700; color:{text}; margin-bottom:4px;">DocuChat</div>
            <div style="font-size:13px; color:{muted};">AI-powered document analysis</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"<p style='font-size:11px; color:{muted}; text-align:center;'>Default login: <code>demo</code> / <code>demo123</code></p>",
                    unsafe_allow_html=True)

        backend_ok = True
        try:
            requests.get(f"{API}/health", timeout=3)
        except Exception:
            backend_ok = False
            st.error("⚠️ Cannot reach backend. Start it: `uvicorn main:app --reload --port 8888`")

        if backend_ok:
            tab1, tab2 = st.tabs(["Sign In", "Create Account"])

            with tab1:
                with st.form("login_form"):
                    username = st.text_input("Username", placeholder="Enter username")
                    password = st.text_input("Password", placeholder="••••••••", type="password")
                    if st.form_submit_button("Sign In →", use_container_width=True):
                        username = username.strip()
                        password = password.strip()
                        if not username or not password:
                            st.error("Please fill in both fields.")
                        else:
                            try:
                                r = requests.post(f"{API}/auth/login",
                                                  json={"username": username, "password": password},
                                                  timeout=5)
                                if r.status_code == 200:
                                    st.session_state.logged_in = True
                                    st.session_state.username  = username
                                    _ensure_session()
                                    st.rerun()
                                else:
                                    st.error(_parse_error(r) or "Login failed.")
                            except Exception as e:
                                st.error(f"Connection error: {e}")

            with tab2:
                with st.form("register_form"):
                    new_user = st.text_input("Username", placeholder="min. 3 characters")
                    new_pass = st.text_input("Password", placeholder="min. 6 characters", type="password")
                    confirm  = st.text_input("Confirm password", placeholder="repeat password", type="password")
                    if st.form_submit_button("Create Account →", use_container_width=True):
                        if not new_user or not new_pass:
                            st.error("Please fill in all fields.")
                        elif len(new_user) < 3:
                            st.error("Username must be at least 3 characters.")
                        elif len(new_pass) < 6:
                            st.error("Password must be at least 6 characters.")
                        elif new_pass != confirm:
                            st.error("Passwords do not match.")
                        else:
                            try:
                                r = requests.post(f"{API}/auth/register",
                                                  json={"username": new_user, "password": new_pass},
                                                  timeout=5)
                                if r.status_code == 200:
                                    st.success("✅ Account created! Sign in above.")
                                else:
                                    st.error(_parse_error(r) or "Registration failed.")
                            except Exception as e:
                                st.error(f"Connection error: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN CHAT PAGE
# ══════════════════════════════════════════════════════════════════════════════

def show_main():
    inject_css(st.session_state.theme)
    _ensure_session()

    dark   = st.session_state.theme == "dark"
    border = "#2a2a2a" if dark else "#dddbd4"
    muted  = "#666666" if dark else "#888888"
    text   = "#e8e8e8" if dark else "#1a1a1a"
    surf2  = "#1e1e1e" if dark else "#f0efe9"

    sess   = _current_session()

    # ── SIDEBAR ──────────────────────────────────────────────────────────────
    with st.sidebar:

        # Logo + user
        st.markdown(f"""
        <div style="display:flex; align-items:center; gap:9px;
                    padding-bottom:12px; border-bottom:1px solid {border};">
            <div style="width:32px; height:32px; background:#6d5ce7; border-radius:9px;
                        display:flex; align-items:center; justify-content:center;
                        font-size:15px; flex-shrink:0;">📄</div>
            <div>
                <div style="font-weight:700; font-size:14px; color:{text};">DocuChat</div>
                <div style="font-size:10px; color:{muted};">@{st.session_state.username}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Theme + New Chat row
        c1, c2 = st.columns([3, 1])
        with c1:
            if st.button("✏️  New Chat", key="new_chat", use_container_width=True):
                _new_session("New Chat")
                st.session_state.doc_loaded = False
                st.session_state.doc_stats  = None
                st.rerun()
        with c2:
            icon = "☀️" if dark else "🌙"
            if st.button(icon, key="theme_toggle"):
                st.session_state.theme = "light" if dark else "dark"
                st.rerun()

        st.markdown("<hr/>", unsafe_allow_html=True)

        # ── Chat sessions list ──────────────────────────────────────────────
        st.markdown(f"<div class='sect-label'>💬 Chats</div>", unsafe_allow_html=True)

        sessions_sorted = sorted(
            st.session_state.sessions.values(),
            key=lambda s: s["created_at"],
            reverse=True,
        )

        for s in sessions_sorted:
            is_active = s["id"] == st.session_state.active_session
            label     = s["title"][:30] + ("…" if len(s["title"]) > 30 else "")
            n_msgs    = len(s["messages"])
            btn_label = f"{'▶ ' if is_active else ''}{label}  ({n_msgs})"

            css_class = "session-btn-active" if is_active else "session-btn"
            with st.container():
                st.markdown(f"<div class='{css_class}'>", unsafe_allow_html=True)
                if st.button(btn_label, key=f"sess_{s['id']}"):
                    st.session_state.active_session = s["id"]
                    # Restore doc state from session
                    restored = st.session_state.sessions[s["id"]]
                    st.session_state.doc_loaded = restored.get("doc_loaded", False)
                    st.session_state.doc_stats  = restored.get("doc_stats", None)
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<hr/>", unsafe_allow_html=True)

        # ── Upload document ─────────────────────────────────────────────────
        st.markdown(f"<div class='sect-label'>📎 Upload Document</div>", unsafe_allow_html=True)
        st.markdown(f"<p style='font-size:10px; color:{muted}; margin:0 0 6px;'>PDF · PNG · JPG</p>",
                    unsafe_allow_html=True)

        uploaded = st.file_uploader("doc", type=["pdf", "png", "jpg", "jpeg"],
                                    label_visibility="collapsed", key="uploader")
        if uploaded:
            if st.button("⚡ Process", use_container_width=True, key="process_doc"):
                with st.spinner("Embedding..."):
                    try:
                        files = {"file": (uploaded.name, uploaded.getvalue(), uploaded.type)}
                        r = requests.post(f"{API}/upload", files=files, timeout=90)
                        if r.status_code == 200:
                            data  = r.json()
                            stats = data["stats"]
                            stats["filename"] = uploaded.name

                            # Update global + current session
                            st.session_state.doc_loaded = True
                            st.session_state.doc_stats  = stats
                            sess = _current_session()
                            if sess:
                                sess["doc_loaded"] = True
                                sess["doc_stats"]  = stats
                                sess["title"]      = uploaded.name[:28]

                            _add_doc_to_memory(stats)
                            st.success("✅ Ready!")
                            st.rerun()
                        else:
                            st.error(_parse_error(r) or "Upload failed.")
                    except requests.exceptions.Timeout:
                        st.error("Timeout. Try again.")
                    except Exception as e:
                        st.error(f"Error: {e}")

        # ── Current doc stats ───────────────────────────────────────────────
        if st.session_state.doc_stats:
            s_data = st.session_state.doc_stats
            st.markdown(f"""
            <div class="stat-card">
                <div class="s-row"><span>File</span><span class="s-val">{s_data.get("filename","")}</span></div>
                <div class="s-row"><span>Chunks</span><span class="s-val">{s_data.get("chunks",0)}</span></div>
                <div class="s-row"><span>Sections</span><span class="s-val">{s_data.get("documents",0)}</span></div>
            </div>
            <div style="margin-top:8px; display:flex; gap:4px; flex-wrap:wrap;">
                <span class="badge-purple">ChromaDB</span>
                <span class="badge-green">Gemini Embed 2</span>
                <span class="badge-amber">Groq LLM</span>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<hr/>", unsafe_allow_html=True)

        # ── Document memory (last 7 days) ───────────────────────────────────
        doc_memory = _load_doc_memory()
        if doc_memory:
            st.markdown(f"<div class='sect-label'>🕐 Recent Docs ({len(doc_memory)})</div>",
                        unsafe_allow_html=True)
            for rec in reversed(doc_memory[-6:]):
                ts  = rec.get("uploaded_at", "")[:16].replace("T", " ")
                fn  = rec.get("filename", "unknown")
                cks = rec.get("chunks", 0)
                st.markdown(f"""
                <div class="doc-card">
                    <div class="doc-card-name" title="{fn}">{fn}</div>
                    <div class="doc-card-meta">{cks} chunks · {ts}</div>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("<hr/>", unsafe_allow_html=True)

        # ── Session controls ────────────────────────────────────────────────
        sess_now = _current_session()
        if sess_now and sess_now["messages"]:
            n = len(sess_now["messages"])
            st.markdown(f"<p style='font-size:11px; color:{muted};'>💬 {n} message{'s' if n!=1 else ''}</p>",
                        unsafe_allow_html=True)
            if st.button("🗑️ Clear Chat", use_container_width=True, key="clear_chat"):
                sess_now["messages"] = []
                sess_now["title"]    = "New Chat"
                st.rerun()

        if st.button("← Sign Out", use_container_width=True, key="logout"):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

        st.markdown(f"""
        <div style="font-size:9px; color:{'#333' if dark else '#ccc'};
                    text-align:center; padding-top:10px; line-height:1.6;">
            LangChain · ChromaDB<br>Gemini Embed 2 · Groq LLM
        </div>
        """, unsafe_allow_html=True)

    # ── MAIN AREA ─────────────────────────────────────────────────────────────

    sess_now = _current_session()
    doc_name = st.session_state.doc_stats["filename"] if st.session_state.doc_stats else "No document loaded"

    # Top bar
    st.markdown(f"""
    <div style="display:flex; align-items:center; justify-content:space-between;
                padding-bottom:12px; border-bottom:1px solid {border}; margin-bottom:14px;">
        <div style="display:flex; align-items:center; gap:8px;">
            <span style="font-size:15px;">🧠</span>
            <span style="font-weight:600; font-size:14px; color:{text};">{doc_name}</span>
        </div>
        <div style="display:flex; align-items:center; gap:5px;">
            <span style="width:6px; height:6px; border-radius:50%;
                         background:#10b981; display:inline-block;"></span>
            <span style="font-size:10px; font-family:monospace;
                         color:{muted};">llama-3.1-8b-instant</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Messages
    messages = sess_now["messages"] if sess_now else []

    if not messages:
        st.markdown("""
        <div class="welcome">
            <div style="font-size:48px; margin-bottom:14px;">💬</div>
            <div style="font-size:18px; font-weight:700; margin-bottom:6px;">Start a conversation</div>
            <div style="font-size:13px;">Upload a document from the sidebar,<br>then ask anything about it.</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        for msg in messages:
            if msg["role"] == "user":
                st.markdown(
                    f'<div class="row-user"><div class="msg-user">{msg["content"]}</div></div>',
                    unsafe_allow_html=True,
                )
            else:
                sources = msg.get("sources", [])
                chips = ""
                if sources:
                    pages = sorted(set(
                        s["page"] for s in sources
                        if s.get("page") not in (None, "N/A")
                    ))
                    if pages:
                        chips = (
                            '<div style="margin-top:7px;">'
                            + "".join(f'<span class="chip">pg {p}</span>' for p in pages[:6])
                            + "</div>"
                        )
                st.markdown(
                    f'<div class="row-bot"><div class="msg-bot">{msg["content"]}{chips}</div></div>',
                    unsafe_allow_html=True,
                )

    # Chat input
    placeholder = (
        "Ask anything about your document..."
        if st.session_state.doc_loaded
        else "Upload a document to start chatting..."
    )

    if question := st.chat_input(placeholder, disabled=not st.session_state.doc_loaded):
        # Auto-title the session from first question
        if sess_now and sess_now["title"] in ("New Chat", "") and question:
            sess_now["title"] = question[:32]

        if sess_now:
            sess_now["messages"].append({"role": "user", "content": question})

        with st.spinner("Thinking..."):
            try:
                history = sess_now["messages"][:-1] if sess_now else []
                r = requests.post(
                    f"{API}/chat",
                    json={"question": question, "chat_history": history},
                    timeout=30,
                )
                if r.status_code == 200:
                    data = r.json()
                    if sess_now:
                        sess_now["messages"].append({
                            "role":    "bot",
                            "content": data["answer"],
                            "sources": data.get("sources", []),
                        })
                else:
                    if sess_now:
                        sess_now["messages"].append({
                            "role":    "bot",
                            "content": f"⚠️ {_parse_error(r) or 'Something went wrong.'}",
                            "sources": [],
                        })
            except requests.exceptions.Timeout:
                if sess_now:
                    sess_now["messages"].append({
                        "role":    "bot",
                        "content": "⚠️ Request timed out. The backend may be busy.",
                        "sources": [],
                    })
            except Exception as e:
                if sess_now:
                    sess_now["messages"].append({
                        "role":    "bot",
                        "content": f"⚠️ Connection error: {str(e)}",
                        "sources": [],
                    })
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# ROUTER
# ══════════════════════════════════════════════════════════════════════════════

if st.session_state.logged_in:
    show_main()
else:
    show_login()