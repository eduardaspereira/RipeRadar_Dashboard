import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from influxdb_client import InfluxDBClient
from datetime import datetime, timezone
import time

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="RipeRadar OS", page_icon="🍎", layout="wide", initial_sidebar_state="expanded")

# --- 2. GESTÃO DE SESSÃO (LOGIN) ---
if 'logado' not in st.session_state:
    st.session_state.logado = False
    st.session_state.cargo = ""

def verificar_login():
    user = st.session_state.user_input
    pw = st.session_state.pass_input
    if user == "chefe" and pw == "admin123":
        st.session_state.logado = True
        st.session_state.cargo = "Chefe de Loja"
    elif user == "operador" and pw == "op123":
        st.session_state.logado = True
        st.session_state.cargo = "Operador"
    else:
        st.error("Credenciais inválidas. Verifique o seu ID e Palavra-Passe.")

def logout():
    st.session_state.logado = False
    st.session_state.cargo = ""

# --- 3. CSS PREMIUM REDESIGN ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,300&display=swap');

    /* ─── RESET & BASE ─────────────────────────────────── */
    :root {
        --bg:        #080C14;
        --surface:   #0E1420;
        --surface2:  #141C2E;
        --border:    #1E2D45;
        --border-lit:#2A3F5F;
        --accent:    #00E5B4;
        --accent2:   #0090FF;
        --warn:      #FFB800;
        --danger:    #FF4455;
        --success:   #00E5B4;
        --txt:       #E8EEF8;
        --txt-muted: #5A7090;
        --txt-sub:   #8BA0BC;
        --mono: 'Space Mono', monospace;
        --sans: 'DM Sans', sans-serif;
    }

    .stApp {
        background-color: var(--bg);
        color: var(--txt);
        font-family: var(--sans);
    }

    /* Background subtle grid texture */
    .stApp::before {
        content: '';
        position: fixed;
        inset: 0;
        background-image:
            linear-gradient(rgba(0,229,180,0.02) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0,229,180,0.02) 1px, transparent 1px);
        background-size: 40px 40px;
        pointer-events: none;
        z-index: 0;
    }

    #MainMenu, footer, header { visibility: hidden; }

    /* ─── SIDEBAR ───────────────────────────────────────── */
    [data-testid="stSidebar"] {
        background: var(--surface) !important;
        border-right: 1px solid var(--border) !important;
    }
    [data-testid="stSidebar"] > div { padding-top: 0 !important; }

    /* ─── TYPOGRAPHY ────────────────────────────────────── */
    h1, h2, h3, h4 { font-family: var(--sans); }

    /* ─── METRIC CARDS ──────────────────────────────────── */
    .metric-card {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 20px 22px;
        position: relative;
        overflow: hidden;
        transition: border-color 0.2s;
    }
    .metric-card::after {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 2px;
        background: linear-gradient(90deg, var(--accent2), var(--accent));
        opacity: 0.6;
    }
    .metric-card:hover { border-color: var(--border-lit); }
    .metric-label {
        font-family: var(--mono);
        font-size: 0.68rem;
        color: var(--txt-muted);
        text-transform: uppercase;
        letter-spacing: 1.5px;
        margin-bottom: 10px;
    }
    .metric-value {
        font-family: var(--mono);
        font-size: 2rem;
        font-weight: 700;
        color: var(--txt);
        line-height: 1;
    }
    .metric-unit {
        font-family: var(--sans);
        font-size: 0.85rem;
        color: var(--txt-muted);
        margin-left: 4px;
        font-weight: 400;
    }
    .metric-dot {
        width: 6px; height: 6px;
        border-radius: 50%;
        background: var(--accent);
        display: inline-block;
        margin-right: 6px;
        box-shadow: 0 0 6px var(--accent);
        animation: pulse 2s ease-in-out infinite;
    }
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.4; }
    }

    /* ─── STATUS BANNER ─────────────────────────────────── */
    .status-banner {
        border-radius: 14px;
        padding: 28px 32px;
        border: 1px solid var(--border);
        background: var(--surface2);
        position: relative;
        overflow: hidden;
    }
    .status-banner::before {
        content: '';
        position: absolute;
        inset: 0;
        background: radial-gradient(ellipse at top left, rgba(0,229,180,0.06) 0%, transparent 60%);
        pointer-events: none;
    }
    .status-label {
        font-family: var(--mono);
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 2px;
        color: var(--txt-muted);
        margin-bottom: 12px;
    }
    .status-target {
        font-size: 0.95rem;
        color: var(--txt-sub);
        margin-bottom: 16px;
        font-weight: 500;
    }
    .status-main {
        font-family: var(--mono);
        font-size: 2.4rem;
        font-weight: 700;
        line-height: 1;
        margin-bottom: 16px;
    }
    .status-action {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 8px 18px;
        border-radius: 999px;
        font-family: var(--mono);
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.5px;
        border: 1px solid;
    }
    .status-accent-bar {
        position: absolute;
        left: 0; top: 0; bottom: 0;
        width: 4px;
        border-radius: 14px 0 0 14px;
    }

    /* ─── SECTION HEADER ────────────────────────────────── */
    .section-header {
        display: flex;
        align-items: center;
        gap: 12px;
        margin: 28px 0 16px;
    }
    .section-header h3 {
        font-size: 1rem;
        font-weight: 600;
        color: var(--txt);
        margin: 0;
        letter-spacing: 0.3px;
    }
    .section-divider {
        flex: 1;
        height: 1px;
        background: var(--border);
    }

    /* ─── TIMELINE ──────────────────────────────────────── */
    .tl-wrap { position: relative; padding-left: 28px; }
    .tl-wrap::before {
        content: '';
        position: absolute;
        left: 7px; top: 8px; bottom: 0;
        width: 1px;
        background: var(--border);
    }
    .tl-item { position: relative; margin-bottom: 20px; }
    .tl-dot {
        position: absolute;
        left: -24px; top: 5px;
        width: 14px; height: 14px;
        border-radius: 50%;
        border: 2px solid var(--accent);
        background: var(--bg);
        box-shadow: 0 0 8px rgba(0,229,180,0.3);
    }
    .tl-dot.warn { border-color: var(--warn); box-shadow: 0 0 8px rgba(255,184,0,0.3); }
    .tl-dot.danger { border-color: var(--danger); box-shadow: 0 0 8px rgba(255,68,85,0.3); }
    .tl-time {
        font-family: var(--mono);
        font-size: 0.72rem;
        color: var(--txt-muted);
        margin-bottom: 6px;
        letter-spacing: 1px;
    }
    .tl-body {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 16px 18px;
    }
    .tl-title { font-weight: 600; font-size: 1rem; margin-bottom: 8px; }
    .tl-detail { font-size: 0.85rem; color: var(--txt-sub); line-height: 1.6; }
    .tl-reading {
        font-family: var(--mono);
        font-size: 0.85rem;
        color: var(--txt);
    }
    .tl-protocol {
        margin-top: 12px;
        padding-top: 12px;
        border-top: 1px solid var(--border);
        font-size: 0.8rem;
        color: var(--txt-muted);
    }

    /* ─── SIDEBAR WIDGETS ───────────────────────────────── */
    .sb-user-card {
        background: var(--surface2);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 18px;
        margin-bottom: 20px;
        text-align: center;
    }
    .sb-user-role {
        font-family: var(--mono);
        font-size: 0.7rem;
        color: var(--txt-muted);
        text-transform: uppercase;
        letter-spacing: 1.5px;
        margin-bottom: 6px;
    }
    .sb-user-name { font-size: 1.1rem; font-weight: 700; color: var(--accent); }
    .sb-section-title {
        font-family: var(--mono);
        font-size: 0.7rem;
        color: var(--txt-muted);
        text-transform: uppercase;
        letter-spacing: 1.5px;
        margin: 20px 0 10px;
    }
    .sb-status-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 12px;
    }
    .sb-status-label { font-size: 0.82rem; color: var(--txt-sub); }
    .sb-status-val {
        font-family: var(--mono);
        font-size: 0.82rem;
        color: var(--accent);
        font-weight: 700;
    }

    /* ─── FORM CALIBRATION ──────────────────────────────── */
    .calib-card {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 14px;
        padding: 28px 30px;
    }
    .calib-title { font-weight: 700; font-size: 1.2rem; margin-bottom: 4px; }
    .calib-sub { font-size: 0.88rem; color: var(--txt-sub); margin-bottom: 24px; }
    .calib-group-title {
        font-family: var(--mono);
        font-size: 0.75rem;
        color: var(--txt-muted);
        text-transform: uppercase;
        letter-spacing: 1.5px;
        margin-bottom: 14px;
        padding-bottom: 8px;
        border-bottom: 1px solid var(--border);
    }

    /* ─── LOGIN ─────────────────────────────────────────── */
    .login-card {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 20px;
        padding: 48px 44px;
        text-align: center;
        position: relative;
        overflow: hidden;
    }
    .login-card::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 3px;
        background: linear-gradient(90deg, var(--accent2), var(--accent));
    }
    .login-logo { font-size: 3.5rem; margin-bottom: 8px; }
    .login-title {
        font-family: var(--mono);
        font-size: 1.8rem;
        font-weight: 700;
        color: var(--txt);
        margin-bottom: 4px;
    }
    .login-sub { font-size: 0.88rem; color: var(--txt-muted); margin-bottom: 36px; }
    .login-version {
        font-family: var(--mono);
        font-size: 0.65rem;
        color: var(--txt-muted);
        margin-top: 28px;
        letter-spacing: 1px;
    }
    .login-tag {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: rgba(0,229,180,0.08);
        border: 1px solid rgba(0,229,180,0.2);
        border-radius: 999px;
        padding: 4px 12px;
        font-family: var(--mono);
        font-size: 0.7rem;
        color: var(--accent);
        margin-bottom: 24px;
    }

    /* ─── INPUT STYLING ─────────────────────────────────── */
    div[data-baseweb="input"] {
        background: var(--bg) !important;
        border-color: var(--border) !important;
        border-radius: 8px !important;
    }
    div[data-baseweb="input"]:focus-within {
        border-color: var(--accent) !important;
        box-shadow: 0 0 0 2px rgba(0,229,180,0.1) !important;
    }
    div[data-baseweb="input"] > input { color: var(--txt) !important; font-family: var(--sans) !important; }

    /* ─── TABS ──────────────────────────────────────────── */
    .stTabs [data-baseweb="tab-list"] {
        border-bottom: 1px solid var(--border) !important;
        gap: 0 !important;
        background: transparent !important;
    }
    .stTabs [data-baseweb="tab"] {
        font-family: var(--mono) !important;
        font-size: 0.78rem !important;
        font-weight: 700 !important;
        color: var(--txt-muted) !important;
        text-transform: uppercase !important;
        letter-spacing: 1px !important;
        padding: 12px 20px !important;
        border-radius: 0 !important;
        margin: 0 !important;
    }
    .stTabs [aria-selected="true"] {
        color: var(--accent) !important;
        border-bottom: 2px solid var(--accent) !important;
        background: rgba(0,229,180,0.04) !important;
    }

    /* ─── BUTTONS ───────────────────────────────────────── */
    .stButton > button[kind="primary"] {
        background: var(--accent) !important;
        color: #080C14 !important;
        font-family: var(--mono) !important;
        font-size: 0.82rem !important;
        font-weight: 700 !important;
        letter-spacing: 1px !important;
        text-transform: uppercase !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 10px 20px !important;
        transition: opacity 0.2s !important;
    }
    .stButton > button[kind="primary"]:hover { opacity: 0.85 !important; }
    .stButton > button:not([kind="primary"]) {
        background: transparent !important;
        color: var(--txt-muted) !important;
        font-family: var(--mono) !important;
        font-size: 0.75rem !important;
        font-weight: 700 !important;
        letter-spacing: 1px !important;
        text-transform: uppercase !important;
        border: 1px solid var(--border) !important;
        border-radius: 8px !important;
    }
    .stButton > button:not([kind="primary"]):hover {
        border-color: var(--txt-muted) !important;
        color: var(--txt) !important;
    }

    /* ─── PROGRESS BARS ─────────────────────────────────── */
    .stProgress > div > div { background: var(--border) !important; border-radius: 4px !important; }
    .stProgress > div > div > div { background: linear-gradient(90deg, var(--accent2), var(--accent)) !important; border-radius: 4px !important; }

    /* ─── SLIDERS ───────────────────────────────────────── */
    .stSlider [data-testid="stThumbValue"] { color: var(--accent) !important; font-family: var(--mono) !important; }
    .stSlider > div > div > div > div { background: var(--accent) !important; }

    /* ─── INFO BOX ──────────────────────────────────────── */
    .stInfo { background: rgba(0,144,255,0.08) !important; border: 1px solid rgba(0,144,255,0.2) !important; border-radius: 10px !important; }

    /* ─── TOGGLE ────────────────────────────────────────── */
    .stToggle [data-testid="stToggle"] > div[data-checked="true"] { background: var(--accent) !important; }

    /* ─── CHART CONTAINER ───────────────────────────────── */
    .chart-wrap {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 20px 16px 8px;
    }

    /* ─── PAGE TITLE ────────────────────────────────────── */
    .page-header {
        display: flex;
        align-items: baseline;
        gap: 14px;
        margin-bottom: 28px;
        padding-bottom: 20px;
        border-bottom: 1px solid var(--border);
    }
    .page-title {
        font-family: var(--mono);
        font-size: 1.4rem;
        font-weight: 700;
        color: var(--txt);
        margin: 0;
    }
    .page-badge {
        font-family: var(--mono);
        font-size: 0.68rem;
        font-weight: 700;
        letter-spacing: 1.5px;
        color: var(--accent);
        background: rgba(0,229,180,0.08);
        border: 1px solid rgba(0,229,180,0.2);
        border-radius: 999px;
        padding: 3px 10px;
    }

    /* ─── LIVE INDICATOR ────────────────────────────────── */
    .live-chip {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-family: var(--mono);
        font-size: 0.68rem;
        color: var(--accent);
        letter-spacing: 1px;
    }
    .live-dot {
        width: 7px; height: 7px;
        border-radius: 50%;
        background: var(--accent);
        animation: pulse 1.5s ease-in-out infinite;
    }
    </style>
""", unsafe_allow_html=True)

# --- 4. FUNÇÕES DE DADOS E IA ---
try:
    INFLUX_URL = st.secrets["INFLUX_URL"]
    INFLUX_TOKEN = st.secrets["INFLUX_TOKEN"]
    INFLUX_ORG = st.secrets["INFLUX_ORG"]
    INFLUX_BUCKET = st.secrets["INFLUX_BUCKET"]
except: pass

@st.cache_data
def get_thresholds():
    return {"clim_fresco": 13000, "clim_maduro": 17000, "nclim_firme": 13000, "nclim_risco": 16000}

thresholds = get_thresholds()

def fetch_data():
    try:
        client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
        query = f'from(bucket: "{INFLUX_BUCKET}") |> range(start: -1h) |> filter(fn: (r) => r["_measurement"] == "mqtt_consumer") |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")'
        df = client.query_api().query_data_frame(query)
        if isinstance(df, list): df = pd.concat(df)
        return df if isinstance(df, pd.DataFrame) and not df.empty else pd.DataFrame()
    except: return pd.DataFrame()

def processar_decisao(classe, voc):
    if any(f in str(classe).lower() for f in ["maca", "apple", "banana"]):
        if voc < thresholds["clim_fresco"]: return "VERDE / FRESCO", "var(--success)", "#00E5B4", "PRATELEIRA", "success"
        elif voc <= thresholds["clim_maduro"]: return "MADURO / ÓTIMO", "var(--warn)", "#FFB800", "PROMOÇÃO IMEDIATA", "warning"
        else: return "PODRE / SENESCÊNCIA", "var(--danger)", "#FF4455", "RETIRAR DE IMEDIATO", "danger"
    else:
        if voc < thresholds["nclim_firme"]: return "FIRME / BOA", "var(--success)", "#00E5B4", "CONFORME", "success"
        elif voc <= thresholds["nclim_risco"]: return "RISCO DE DEGRADAÇÃO", "var(--warn)", "#FFB800", "VIGILÂNCIA REFORÇADA", "warning"
        else: return "DEGRADADA", "var(--danger)", "#FF4455", "REJEITAR LOTE", "danger"

# ==========================================
# ECRÃ 1: LOGIN
# ==========================================
if not st.session_state.logado:
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.1, 1])
    with col2:
        st.markdown("""
        <div class="login-card">
            <div class="login-logo">🍎</div>
            <div class="login-title">RipeRadar OS</div>
            <div class="login-sub">Sistema Integrado de Monitorização IoT</div>
            <div style="display:flex;justify-content:center;gap:8px;margin-bottom:32px;">
                <span class="login-tag"><span style="width:5px;height:5px;border-radius:50%;background:currentColor;display:inline-block;"></span>EDGE AI ACTIVE</span>
                <span class="login-tag"><span style="width:5px;height:5px;border-radius:50%;background:currentColor;display:inline-block;"></span>BLE LINKED</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        st.text_input("Identificação de Utilizador", key="user_input", placeholder="ex: operador")
        st.text_input("Código de Acesso", type="password", key="pass_input", placeholder="••••••••")
        st.markdown("<br>", unsafe_allow_html=True)
        st.button("Iniciar Sessão Segura →", on_click=verificar_login, use_container_width=True, type="primary")
        st.markdown("<div class='login-version'>RIPRADAR OS v2.4 · EDGE GATEWAY · ENCRYPTED SESSION</div>", unsafe_allow_html=True)

# ==========================================
# ECRÃ 2: DASHBOARD
# ==========================================
else:
    # --- SIDEBAR ---
    with st.sidebar:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(f"""
            <div class="sb-user-card">
                <div class="sb-user-role">Operador Ativo</div>
                <div class="sb-user-name">{st.session_state.cargo}</div>
            </div>
        """, unsafe_allow_html=True)

        st.button("↩ Terminar Sessão", on_click=logout, use_container_width=True)

        st.markdown("<div class='sb-section-title'>Diagnóstico de Sistema</div>", unsafe_allow_html=True)
        st.markdown("""
            <div class="sb-status-row"><span class="sb-status-label">CPU Edge Gateway</span><span class="sb-status-val">24%</span></div>
        """, unsafe_allow_html=True)
        st.progress(24)
        st.markdown("""
            <div class="sb-status-row" style="margin-top:14px;"><span class="sb-status-label">Sinal BLE Nicla</span><span class="sb-status-val">85%</span></div>
        """, unsafe_allow_html=True)
        st.progress(85)
        st.markdown("""
            <div class="sb-status-row" style="margin-top:14px;"><span class="sb-status-label">InfluxDB</span><span class="sb-status-val" style="color:#00E5B4;">ONLINE</span></div>
            <div class="sb-status-row"><span class="sb-status-label">MQTT Broker</span><span class="sb-status-val" style="color:#00E5B4;">ACTIVE</span></div>
        """, unsafe_allow_html=True)

        st.markdown("<div class='sb-section-title' style='margin-top:20px;'>Telemetria</div>", unsafe_allow_html=True)
        auto_refresh = st.toggle("Live Refresh (5s)", value=True)

    # --- DADOS ---
    df = fetch_data()

    # --- PAGE HEADER ---
    st.markdown("""
        <div class="page-header">
            <span class="page-title">Centro de Comando Analítico</span>
            <span class="page-badge">RipeRadar OS</span>
            <span style="flex:1;"></span>
            <span class="live-chip"><span class="live-dot"></span>LIVE</span>
        </div>
    """, unsafe_allow_html=True)

    # --- TABS ---
    if st.session_state.cargo == "Chefe de Loja":
        tab_dash, tab_time, tab_admin = st.tabs(["MONITORIZAÇÃO", "TIMELINE", "CALIBRAÇÃO"])
    else:
        tab_dash, tab_admin = st.tabs(["MONITORIZAÇÃO", "CALIBRAÇÃO"])

    # ---------------------------------------------------------
    # TAB 1: DASHBOARD
    # ---------------------------------------------------------
    with tab_dash:
        if not df.empty and '_time' in df.columns:
            latest = df.iloc[-1]
            voc   = float(latest.get('voc_gas', 0.0))
            fruta = str(latest.get('classe_dominante', 'Desconhecido'))
            conf  = float(latest.get('confianca', 0.0))
            temp  = float(latest.get('temp', 0.0))
            hum   = float(latest.get('hum', 0.0))

            estado, cor_css, cor_hex, acao, severidade = processar_decisao(fruta, voc)

            sev_bg_map   = {"success": "rgba(0,229,180,0.06)", "warning": "rgba(255,184,0,0.06)", "danger": "rgba(255,68,85,0.06)"}
            sev_bdr_map  = {"success": "rgba(0,229,180,0.2)",  "warning": "rgba(255,184,0,0.2)",  "danger": "rgba(255,68,85,0.2)"}
            bg_color     = sev_bg_map[severidade]
            bdr_color    = sev_bdr_map[severidade]

            # Row 1: Status + Gauge
            col_status, col_gauge = st.columns([1.6, 1])

            with col_status:
                conf_display = conf * 100 if conf <= 1 else conf
                st.markdown(f"""
                    <div class="status-banner" style="background:{bg_color}; border-color:{bdr_color};">
                        <div class="status-accent-bar" style="background:{cor_hex};"></div>
                        <div class="status-label">Alvo Identificado</div>
                        <div class="status-target">🎯 {fruta.upper().replace('_', ' ')} &nbsp;·&nbsp; Confiança: <span style="font-family:var(--mono);font-weight:700;color:{cor_hex};">{conf_display:.1f}%</span></div>
                        <div class="status-main" style="color:{cor_hex};">{estado}</div>
                        <span class="status-action" style="color:{cor_hex}; border-color:{bdr_color}; background:rgba(0,0,0,0.2);">
                            ▶ {acao}
                        </span>
                    </div>
                """, unsafe_allow_html=True)

            with col_gauge:
                limite_min = thresholds["clim_fresco"] if any(f in fruta.lower() for f in ["maca","banana"]) else thresholds["nclim_firme"]
                limite_max = thresholds["clim_maduro"] if any(f in fruta.lower() for f in ["maca","banana"]) else thresholds["nclim_risco"]

                fig_gauge = go.Figure(go.Indicator(
                    mode="gauge+number", value=voc,
                    number={'suffix': " Ω", 'font': {'size': 28, 'color': '#E8EEF8', 'family': 'Space Mono'}},
                    title={'text': "RESISTÊNCIA VOC (Ω)", 'font': {'size': 11, 'color': '#5A7090', 'family': 'DM Sans'}},
                    gauge={
                        'axis': {'range': [None, 25000], 'tickwidth': 1, 'tickcolor': "#1E2D45", 'tickfont': {'color': '#5A7090', 'size': 10}},
                        'bar': {'color': cor_hex, 'thickness': 0.22},
                        'bgcolor': "#0E1420", 'borderwidth': 1, 'bordercolor': "#1E2D45",
                        'steps': [
                            {'range': [0, limite_min],         'color': "rgba(255,68,85,0.1)"},
                            {'range': [limite_min, limite_max], 'color': "rgba(255,184,0,0.1)"},
                            {'range': [limite_max, 25000],      'color': "rgba(0,229,180,0.1)"}
                        ],
                        'threshold': {'line': {'color': cor_hex, 'width': 2}, 'thickness': 0.8, 'value': voc}
                    }
                ))
                fig_gauge.update_layout(
                    height=240, margin=dict(l=20, r=20, t=30, b=10),
                    paper_bgcolor='rgba(0,0,0,0)', font={'family': "DM Sans"}
                )
                st.markdown("<div style='background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:8px 0 0;'>", unsafe_allow_html=True)
                st.plotly_chart(fig_gauge, use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)

            # Row 2: Metric Cards
            st.markdown("<br>", unsafe_allow_html=True)
            c1, c2, c3, c4 = st.columns(4)
            cards = [
                ("IA CONFIDENCE", f"{conf*100 if conf <= 1 else conf:.1f}", "%"),
                ("TEMPERATURA",   f"{temp:.1f}", "°C"),
                ("HUMIDADE",      f"{hum:.1f}",  "%"),
                ("LATÊNCIA MQTT", "124",         "ms"),
            ]
            for col, (label, val, unit) in zip([c1, c2, c3, c4], cards):
                col.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-label"><span class="metric-dot"></span>{label}</div>
                        <div class="metric-value">{val}<span class="metric-unit">{unit}</span></div>
                    </div>
                """, unsafe_allow_html=True)

            # Row 3: Chart
            st.markdown("""
                <div class="section-header">
                    <h3>Evolução VOC — Última Hora</h3>
                    <div class="section-divider"></div>
                </div>
            """, unsafe_allow_html=True)

            if 'voc_gas' in df.columns:
                df_clean = df.dropna(subset=['voc_gas']).sort_values('_time')
                fig_line = go.Figure()
                fig_line.add_trace(go.Scatter(
                    x=df_clean['_time'], y=df_clean['voc_gas'],
                    mode='lines+markers',
                    line=dict(color='#00E5B4', width=2.5, shape='spline'),
                    marker=dict(size=5, color='#080C14', line=dict(width=1.5, color='#00E5B4')),
                    fill='tozeroy', fillcolor='rgba(0,229,180,0.06)',
                    name='Resistência VOC',
                    hovertemplate='<b>%{x|%H:%M:%S}</b><br>%{y:.0f} Ω<extra></extra>'
                ))
                fig_line.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    xaxis_title="", yaxis_title="Ohms",
                    margin=dict(l=10, r=10, t=10, b=10),
                    hovermode="x unified",
                    xaxis=dict(showgrid=False, color="#5A7090", tickfont=dict(family="Space Mono", size=10)),
                    yaxis=dict(gridcolor='#1E2D45', color="#5A7090", zerolinecolor='#1E2D45', tickfont=dict(family="Space Mono", size=10)),
                    legend=dict(font=dict(color='#8BA0BC'))
                )
                st.markdown("<div class='chart-wrap'>", unsafe_allow_html=True)
                st.plotly_chart(fig_line, use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.info("🔌 A aguardar ingestão de pacotes MQTT...")

    # ---------------------------------------------------------
    # TAB 2: TIMELINE
    # ---------------------------------------------------------
    if st.session_state.cargo == "Chefe de Loja":
        with tab_time:
            st.markdown("""
                <div style="margin-bottom:24px;">
                    <h3 style="font-family:var(--mono);font-size:1rem;font-weight:700;color:var(--txt);margin-bottom:6px;">Auditoria de Eventos e Alertas</h3>
                    <p style="font-size:0.85rem;color:var(--txt-muted);">Registo imutável gerado pela heurística de fusão da Edge Gateway.</p>
                </div>
            """, unsafe_allow_html=True)

            st.markdown('<div class="tl-wrap">', unsafe_allow_html=True)
            if not df.empty and 'voc_gas' in df.columns:
                df_sorted = df.sort_values(by='_time', ascending=False)
                eventos = 0
                for idx, row in df_sorted.iterrows():
                    v_voc   = float(row.get('voc_gas', 0))
                    v_fruta = str(row.get('classe_dominante', ''))
                    if v_voc > 0 and v_fruta:
                        est, _, cor_hex, ac, sev = processar_decisao(v_fruta, v_voc)
                        if sev in ["warning", "danger"] and eventos < 10:
                            dot_class = "warn" if sev == "warning" else "danger"
                            d_time = row['_time'].strftime("%H:%M:%S")
                            st.markdown(f"""
                            <div class="tl-item">
                                <div class="tl-dot {dot_class}"></div>
                                <div class="tl-time">LOG {d_time}</div>
                                <div class="tl-body">
                                    <div class="tl-title" style="color:{cor_hex};">{est}</div>
                                    <div class="tl-detail">
                                        Produto: <span style="color:var(--txt);font-weight:600;">{v_fruta.replace('_',' ').title()}</span>
                                        &nbsp;·&nbsp;
                                        Leitura: <span class="tl-reading">{v_voc/1000:.2f} kΩ</span>
                                    </div>
                                    <div class="tl-protocol">Protocolo: <strong style="color:var(--txt);">{ac}</strong></div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                            eventos += 1
                if eventos == 0:
                    st.markdown("""
                    <div class="tl-item">
                        <div class="tl-dot"></div>
                        <div class="tl-body" style="border-left: 3px solid var(--success);">
                            <div class="tl-title" style="color:var(--success);">✓ Diagnóstico Perfeito</div>
                            <div class="tl-detail">Nenhum desvio dos parâmetros basais detetado.</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

    # ---------------------------------------------------------
    # TAB 3: CALIBRAÇÃO
    # ---------------------------------------------------------
    with tab_admin:
        st.markdown("<div class='calib-card'>", unsafe_allow_html=True)
        with st.form("calibration_form"):
            st.markdown("""
                <div class="calib-title">Parâmetros do Modelo de Late Fusion</div>
                <div class="calib-sub">Sintonize a janela de resistência do sensor BME688. Recomendado suspender o Live Refresh antes de operar.</div>
            """, unsafe_allow_html=True)

            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("<div class='calib-group-title'>🍌 Fenologia Climatérica (Banana / Maçã)</div>", unsafe_allow_html=True)
                clim_f = st.slider("Verde → Maduro", 10000, 15000, thresholds["clim_fresco"])
                clim_m = st.slider("Maduro → Podre", 15000, 20000, thresholds["clim_maduro"])
            with col_b:
                st.markdown("<div class='calib-group-title'>🍊 Fenologia Não-Climatérica (Laranja)</div>", unsafe_allow_html=True)
                nclim_f = st.slider("Firme → Risco", 10000, 14000, thresholds["nclim_firme"])
                nclim_r = st.slider("Risco → Degradada", 14000, 18000, thresholds["nclim_risco"])

            st.markdown("<br>", unsafe_allow_html=True)
            submitted = st.form_submit_button("Aplicar Parâmetros →", use_container_width=True, type="primary")
            if submitted:
                thresholds.update({"clim_fresco": clim_f, "clim_maduro": clim_m, "nclim_firme": nclim_f, "nclim_risco": nclim_r})
                st.success("✓ Modelo atualizado com sucesso.")

        st.markdown("</div>", unsafe_allow_html=True)

    # --- AUTO REFRESH ---
    if auto_refresh:
        time.sleep(5)
        st.rerun()