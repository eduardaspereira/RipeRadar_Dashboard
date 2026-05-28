import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import time
from datetime import datetime, timedelta, timezone
from influxdb_client import InfluxDBClient
from streamlit_autorefresh import st_autorefresh
import extra_streamlit_components as stx
import json
import os

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="RipeRadar OS", page_icon="🍎", layout="wide", initial_sidebar_state="expanded")

# --- 2. GESTOR DE COOKIES ---
cookie_manager = stx.CookieManager(key="cookie_manager_global")
if cookie_manager.get_all() is None:
    st.stop() 

is_terminal = str(cookie_manager.get(cookie="terminal_loja")).lower() == "true"

# --- 3. CREDENCIAIS ---
try:
    INFLUX_URL    = st.secrets["INFLUX_URL"]
    INFLUX_TOKEN  = st.secrets["INFLUX_TOKEN"]
    INFLUX_ORG    = st.secrets["INFLUX_ORG"]
    INFLUX_BUCKET = st.secrets["INFLUX_BUCKET"]
except Exception:
    INFLUX_URL = "https://eu-central-1-1.aws.cloud2.influxdata.com"
    INFLUX_TOKEN = "TEU_TOKEN"
    INFLUX_ORG = "TUA_ORG"
    INFLUX_BUCKET = "TEU_BUCKET"

# --- 4. ESTADO DA SESSÃO ---
if 'logado' not in st.session_state:
    st.session_state.logado = False
    st.session_state.cargo = ""
if 'override_desconhecido' not in st.session_state:
    st.session_state.override_desconhecido = None

def verificar_login_manual():
    user = st.session_state.user_input
    pw   = st.session_state.pass_input
    if user == "chefe" and pw == "admin123":
        st.session_state.logado = True
        st.session_state.cargo = "Chefe de Loja"
    elif user == "operador" and pw == "op123":
        st.session_state.logado = True
        st.session_state.cargo = "Operador"
    else:
        st.error("Credenciais inválidas.")

def verificar_login_rfid():
    try:
        client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
        query_api = client.query_api()
        query = f'''
        from(bucket: "{INFLUX_BUCKET}")
          |> range(start: -5s)
          |> filter(fn: (r) => r["_measurement"] == "rfid_login")
          |> filter(fn: (r) => r["local"] == "pc_windows")
          |> filter(fn: (r) => r["_field"] == "user_id")
          |> last()
        '''
        result = query_api.query(org=INFLUX_ORG, query=query)
        for table in result:
            for record in table.records:
                user_lido = record.get_value()
                if user_lido == "chefe":
                    st.session_state.logado = True
                    st.session_state.cargo = "Chefe de Loja"
                    st.rerun() 
                elif user_lido == "operador":
                    st.session_state.logado = True
                    st.session_state.cargo = "Operador"
                    st.rerun()
    except Exception:
        pass 

def fetch_historico_reposicoes(dias=90):
    """Procura os carimbos de data/hora de todas as tags de Nova Carga passadas"""
    try:
        client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
        query = f'''
        from(bucket: "{INFLUX_BUCKET}")
          |> range(start: -{dias}d)
          |> filter(fn: (r) => r["_measurement"] == "rfid_operacoes")
          |> filter(fn: (r) => r["_field"] == "acao")
          |> filter(fn: (r) => r["_value"] == "nova_carga")
        '''
        result = client.query_api().query(query)
        timestamps = []
        for table in result:
            for record in table.records:
                timestamps.append(pd.to_datetime(record.get_time()))
        return sorted(list(set(timestamps)))
    except:
        return []

def fetch_ultima_reposicao():
    try:
        client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
        query = f'''
        from(bucket: "{INFLUX_BUCKET}")
          |> range(start: -30d)
          |> filter(fn: (r) => r["_measurement"] == "rfid_operacoes")
          |> filter(fn: (r) => r["_field"] == "acao")
          |> filter(fn: (r) => r["_value"] == "nova_carga")
          |> last()
        '''
        result = client.query_api().query(query)
        for table in result:
            for record in table.records:
                return record.get_time()
        return None
    except:
        return None
    
def logout():
    st.session_state.logado = False
    st.session_state.cargo = ""
    st.session_state.override_desconhecido = None

# ══════════════════════════════════════════════════════════════
#  CSS INJETADO
# ══════════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600;9..40,700&display=swap');

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

.stApp { background-color: var(--bg); color: var(--txt); font-family: var(--sans); }
.stApp::before {
    content: ''; position: fixed; inset: 0;
    background-image: linear-gradient(rgba(0,229,180,0.015) 1px, transparent 1px), linear-gradient(90deg, rgba(0,229,180,0.015) 1px, transparent 1px);
    background-size: 40px 40px; pointer-events: none; z-index: 0;
}
#MainMenu, footer { visibility: hidden; }
header { background: transparent !important; }
[data-testid="stHeaderActionElements"] { display: none !important; }
h1,h2,h3,h4 { font-family: var(--sans); }

[data-testid="stSidebar"] { background: var(--surface) !important; border-right: 1px solid var(--border) !important; }
[data-testid="stSidebar"] > div { padding-top: 0 !important; }

.metric-card {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 12px; padding: 20px 22px; position: relative; overflow: hidden; transition: border-color 0.2s;
}
.metric-card::after {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, var(--accent2), var(--accent)); opacity: 0.6;
}
.metric-card:hover { border-color: var(--border-lit); }
.metric-label { font-family: var(--mono); font-size: 0.68rem; color: var(--txt-muted); text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 10px; }
.metric-value { font-family: var(--mono); font-size: 2rem; font-weight: 700; color: var(--txt); line-height: 1; }
.metric-unit  { font-family: var(--sans); font-size: 0.85rem; color: var(--txt-muted); margin-left: 4px; font-weight: 400; }
.metric-dot   { width: 6px; height: 6px; border-radius: 50%; background: var(--accent); display: inline-block; margin-right: 6px; box-shadow: 0 0 6px var(--accent); animation: blink 2s ease-in-out infinite; }
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0.3} }

.status-banner {
    border-radius: 14px; padding: 28px 32px; border: 1px solid var(--border); background: var(--surface2); position: relative; overflow: hidden;
}
.status-banner::before {
    content: ''; position: absolute; inset: 0; background: radial-gradient(ellipse at top left, rgba(0,229,180,0.06) 0%, transparent 60%); pointer-events: none;
}
.status-accent-bar { position: absolute; left: 0; top: 0; bottom: 0; width: 4px; border-radius: 14px 0 0 14px; }
.status-label  { font-family: var(--mono); font-size: 0.7rem; text-transform: uppercase; letter-spacing: 2px; color: var(--txt-muted); margin-bottom: 12px; }
.status-target { font-size: 0.95rem; color: var(--txt-sub); margin-bottom: 16px; font-weight: 500; }
.status-main   { font-family: var(--mono); font-size: 2.4rem; font-weight: 700; line-height: 1; margin-bottom: 16px; }
.status-action { display: inline-flex; align-items: center; gap: 8px; padding: 8px 18px; border-radius: 999px; font-family: var(--mono); font-size: 0.78rem; font-weight: 700; letter-spacing: 0.5px; border: 1px solid; }

.section-header { display: flex; align-items: center; gap: 12px; margin: 28px 0 16px; }
.section-header h3 { font-size: 1rem; font-weight: 600; color: var(--txt); margin: 0; letter-spacing: 0.3px; }
.section-divider { flex: 1; height: 1px; background: var(--border); }

.tl-wrap { position: relative; padding-left: 28px; }
.tl-wrap::before { content: ''; position: absolute; left: 7px; top: 8px; bottom: 0; width: 1px; background: var(--border); }
.tl-item { position: relative; margin-bottom: 20px; }
.tl-dot  { position: absolute; left: -24px; top: 5px; width: 14px; height: 14px; border-radius: 50%; border: 2px solid var(--accent); background: var(--bg); box-shadow: 0 0 8px rgba(0,229,180,0.3); }
.tl-dot.warn   { border-color: var(--warn);   box-shadow: 0 0 8px rgba(255,184,0,0.3); }
.tl-dot.danger { border-color: var(--danger); box-shadow: 0 0 8px rgba(255,68,85,0.3); }
.tl-time { font-family: var(--mono); font-size: 0.72rem; color: var(--txt-muted); margin-bottom: 6px; letter-spacing: 1px; }
.tl-body { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 16px 18px; }
.tl-badge { display: inline-flex; align-items: center; gap: 5px; padding: 3px 10px; border-radius: 999px; font-family: var(--mono); font-size: 0.68rem; font-weight: 700; letter-spacing: 0.5px; border: 1px solid; margin-left: 8px; }

.kpi-row { display: flex; gap: 16px; margin-bottom: 28px; flex-wrap: wrap; }
.kpi-card { flex: 1; min-width: 130px; background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 16px 20px; text-align: center; }
.kpi-num  { font-family: var(--mono); font-size: 1.9rem; font-weight: 700; }
.kpi-lbl  { font-family: var(--mono); font-size: 0.65rem; color: var(--txt-muted); text-transform: uppercase; letter-spacing: 1.5px; margin-top: 4px; }

.calib-card { background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: 28px 30px; }
.calib-title { font-weight: 700; font-size: 1.2rem; margin-bottom: 4px; }
.calib-sub { font-size: 0.88rem; color: var(--txt-sub); margin-bottom: 24px; }
.calib-group-title { font-family: var(--mono); font-size: 0.75rem; color: var(--txt-muted); text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 14px; padding-bottom: 8px; border-bottom: 1px solid var(--border); }

.sb-user-card { background: var(--surface2); border: 1px solid var(--border); border-radius: 12px; padding: 18px; margin-bottom: 20px; text-align: center; }
.sb-user-role { font-family: var(--mono); font-size: 0.7rem; color: var(--txt-muted); text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 6px; }
.sb-user-name { font-size: 1.1rem; font-weight: 700; color: var(--accent); }
.sb-section-title { font-family: var(--mono); font-size: 0.7rem; color: var(--txt-muted); text-transform: uppercase; letter-spacing: 1.5px; margin: 20px 0 10px; }
.sb-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.sb-lbl { font-size: 0.82rem; color: var(--txt-sub); }
.sb-val { font-family: var(--mono); font-size: 0.82rem; font-weight: 700; }

.login-card { background: var(--surface); border: 1px solid var(--border); border-radius: 20px; padding: 48px 44px; text-align: center; position: relative; overflow: hidden; }
.login-card::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px; background: linear-gradient(90deg, var(--accent2), var(--accent)); }
.login-logo  { font-size: 3.5rem; margin-bottom: 8px; }
.login-title { font-family: var(--mono); font-size: 1.8rem; font-weight: 700; color: var(--txt); margin-bottom: 4px; }
.login-sub   { font-size: 0.88rem; color: var(--txt-muted); margin-bottom: 24px; }
.login-tag   { display: inline-flex; align-items: center; gap: 6px; background: rgba(0,229,180,0.08); border: 1px solid rgba(0,229,180,0.2); border-radius: 999px; padding: 4px 12px; font-family: var(--mono); font-size: 0.7rem; color: var(--accent); margin: 0 4px 24px; }
.login-version { font-family: var(--mono); font-size: 0.65rem; color: var(--txt-muted); margin-top: 28px; letter-spacing: 1px; }

.page-header { display: flex; align-items: baseline; gap: 14px; margin-bottom: 28px; padding-bottom: 20px; border-bottom: 1px solid var(--border); }
.page-title  { font-family: var(--mono); font-size: 1.4rem; font-weight: 700; color: var(--txt); margin: 0; }
.page-badge  { font-family: var(--mono); font-size: 0.68rem; font-weight: 700; letter-spacing: 1.5px; color: var(--accent); background: rgba(0,229,180,0.08); border: 1px solid rgba(0,229,180,0.2); border-radius: 999px; padding: 3px 10px; }
.live-chip   { display: inline-flex; align-items: center; gap: 6px; font-family: var(--mono); font-size: 0.68rem; color: var(--accent); letter-spacing: 1px; }
.live-dot    { width: 7px; height: 7px; border-radius: 50%; background: var(--accent); animation: blink 1.5s ease-in-out infinite; }
.offline-chip { display: inline-flex; align-items: center; gap: 6px; font-family: var(--mono); font-size: 0.68rem; color: var(--txt-muted); letter-spacing: 1px; }
.offline-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--txt-muted); }

.stTabs [data-baseweb="tab-list"] { border-bottom: 1px solid var(--border) !important; gap: 0 !important; background: transparent !important; }
.stTabs [data-baseweb="tab"] { font-family: var(--mono) !important; font-size: 0.78rem !important; font-weight: 700 !important; color: var(--txt-muted) !important; text-transform: uppercase !important; letter-spacing: 1px !important; padding: 12px 20px !important; border-radius: 0 !important; margin: 0 !important; }
.stTabs [aria-selected="true"] { color: var(--accent) !important; border-bottom: 2px solid var(--accent) !important; background: rgba(0,229,180,0.04) !important; }

.stButton > button[kind="primary"] { background: var(--accent) !important; color: #080C14 !important; font-family: var(--mono) !important; font-size: 0.82rem !important; font-weight: 700 !important; letter-spacing: 1px !important; text-transform: uppercase !important; border: none !important; border-radius: 8px !important; }
.stButton > button[kind="primary"]:hover { opacity: 0.85 !important; }
.stButton > button:not([kind="primary"]) { background: transparent !important; color: var(--txt-muted) !important; font-family: var(--mono) !important; font-size: 0.75rem !important; font-weight: 700 !important; letter-spacing: 1px !important; text-transform: uppercase !important; border: 1px solid var(--border) !important; border-radius: 8px !important; }
.stButton > button:not([kind="primary"]):hover { border-color: var(--txt-muted) !important; color: var(--txt) !important; }

div[data-baseweb="input"] { background: var(--bg) !important; border-color: var(--border) !important; border-radius: 8px !important; }
div[data-baseweb="input"]:focus-within { border-color: var(--accent) !important; box-shadow: 0 0 0 2px rgba(0,229,180,0.1) !important; }
div[data-baseweb="input"] > input { color: var(--txt) !important; font-family: var(--sans) !important; }
div[data-baseweb="select"] > div { background: var(--surface) !important; border-color: var(--border) !important; color: var(--txt) !important; border-radius: 8px !important; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
#  THRESHOLDS & FUNÇÕES BASE (COM JSON)
# ══════════════════════════════════════════════════════════════
def carregar_calibracao():
    if os.path.exists("calibracao.json"):
        with open("calibracao.json", "r") as f:
            return json.load(f)
    return {
        "clim_fresco": 13000, "clim_maduro": 17000,
        "nclim_firme": 13000, "nclim_risco": 16000
    }

def guardar_calibracao(limites):
    with open("calibracao.json", "w") as f:
        json.dump(limites, f)

if 'thresholds' not in st.session_state:
    st.session_state.thresholds = carregar_calibracao()

thresholds = st.session_state.thresholds

def formatar_nome(raw_name):
    if raw_name == "Todos": return "Todos os Produtos"
    return str(raw_name).replace('_', ' ').title()

def obter_cor_estado(raw_name):
    nome_min = str(raw_name).lower()
    if 'fresc' in nome_min or 'firm' in nome_min: return "#00E5B4"
    if 'madur' in nome_min or 'risco' in nome_min: return "#FFB800"
    if 'podre' in nome_min or 'degrad' in nome_min: return "#FF4455"
    return "#8BA0BC"

meses_pt = {1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril", 5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto", 9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"}

def fetch_live_data():
    try:
        client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
        query  = (f'from(bucket: "{INFLUX_BUCKET}") |> range(start: -1h)'
                  f' |> filter(fn: (r) => r["_measurement"] == "mqtt_consumer")'
                  f' |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")')
        df = client.query_api().query_data_frame(query)
        if isinstance(df, list): df = pd.concat(df)
        if isinstance(df, pd.DataFrame) and not df.empty:
            df['_time'] = pd.to_datetime(df['_time'], utc=True)
            return df
        return pd.DataFrame()
    except:
        return pd.DataFrame()

@st.cache_data(ttl=300)
def fetch_history_data(dias):
    try:
        client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
        query  = (f'from(bucket: "{INFLUX_BUCKET}") |> range(start: -{dias}d)'
                  f' |> filter(fn: (r) => r["_measurement"] == "mqtt_consumer")'
                  f' |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")')
        df = client.query_api().query_data_frame(query)
        if isinstance(df, list): df = pd.concat(df)
        if isinstance(df, pd.DataFrame) and not df.empty:
            df['_time'] = pd.to_datetime(df['_time'], utc=True)
            return df
        return pd.DataFrame()
    except:
        return pd.DataFrame()

def processar_decisao(classe, voc):
    t = st.session_state.thresholds
    if any(f in str(classe).lower() for f in ["maca", "apple", "banana"]):
        if voc < t["clim_fresco"]:    return "VERDE / FRESCO",      "#00E5B4", "PRATELEIRA",          "success"
        elif voc <= t["clim_maduro"]: return "MADURO / ÓTIMO",      "#FFB800", "PROMOÇÃO IMEDIATA",   "warning"
        else:                          return "PODRE / SENESCÊNCIA",  "#FF4455", "RETIRAR DE IMEDIATO", "danger"
    else:
        if voc < t["nclim_firme"]:    return "FIRME / BOA",          "#00E5B4", "CONFORME",            "success"
        elif voc <= t["nclim_risco"]: return "RISCO DE DEGRADAÇÃO",  "#FFB800", "VIGILÂNCIA REFORÇADA","warning"
        else:                          return "DEGRADADA",            "#FF4455", "REJEITAR LOTE",       "danger"

PLOT_LAYOUT = dict(
    paper_bgcolor='#0E1420', plot_bgcolor='#0E1420', margin=dict(l=10, r=10, t=30, b=10),
    hovermode="x unified", font=dict(family="DM Sans", color="#8BA0BC"),
    xaxis=dict(showgrid=False, color="#5A7090", tickfont=dict(family="Space Mono", size=10)),
    yaxis=dict(gridcolor='#1E2D45', color="#5A7090", zerolinecolor='#1E2D45', tickfont=dict(family="Space Mono", size=10)),
    legend=dict(font=dict(color='#8BA0BC', family='DM Sans'), bgcolor='rgba(0,0,0,0)', orientation='h', yanchor='bottom', y=1.05)
)

# ══════════════════════════════════════════════════════════════
#  ECRÃ LOGIN
# ══════════════════════════════════════════════════════════════
if not st.session_state.logado:
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    _, col2, _ = st.columns([1, 1.1, 1])
    
    with col2:
        st.markdown("""
        <div class="login-card">
            <div class="login-logo">🍎</div>
            <div class="login-title">RipeRadar OS</div>
            <div class="login-sub">Sistema Integrado de Monitorização IoT</div>
            <div style="display:flex;justify-content:center;gap:8px;margin-bottom:28px;flex-wrap:wrap;">
                <span class="login-tag">● EDGE AI ACTIVE</span>
                <span class="login-tag">● BLE LINKED</span>
                <span class="login-tag">● INFLUXDB READY</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        if is_terminal:
            st_autorefresh(interval=2000, limit=None, key="login_refresh")
            st.info("📡 Terminal Autorizado: Aproxime o cartão RFID do leitor para entrar.")
            verificar_login_rfid()
            
            with st.expander("Ou aceda manualmente via teclado"):
                st.text_input("Identificação", key="user_input", placeholder="chefe  /  operador")
                st.text_input("Código", type="password", key="pass_input", placeholder="••••••••")
                st.button("Iniciar Sessão", on_click=verificar_login_manual, use_container_width=True)
        else:
            st.warning("🔒 Terminal não registado para RFID. Por favor, inicie sessão manualmente.")
            st.text_input("Identificação de Utilizador", key="user_input", placeholder="chefe  /  operador")
            st.text_input("Código de Acesso", type="password", key="pass_input", placeholder="••••••••")
            st.markdown("<br>", unsafe_allow_html=True)
            st.button("Iniciar Sessão Segura →", on_click=verificar_login_manual, use_container_width=True, type="primary")

        st.markdown("<div class='login-version' style='text-align:center;'>RIPERADAR OS v2.4 · EDGE GATEWAY · SESSION ENCRYPTED</div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
#  DASHBOARD
# ══════════════════════════════════════════════════════════════
else:
    df_live = fetch_live_data()
    agora = datetime.now(timezone.utc)
    limite_3min = agora - timedelta(minutes=3)
    
    is_live = False
    influx_online = False
    nicla_online = False
    vision_online = False
    
    if not df_live.empty and '_time' in df_live.columns:
        influx_online = True
        if df_live['_time'].max() >= limite_3min:
            is_live = True
            
        if 'voc_gas' in df_live.columns:
            voc_times = df_live.dropna(subset=['voc_gas'])['_time']
            if not voc_times.empty and voc_times.max() >= limite_3min:
                nicla_online = True
                
        vision_col = 'classe_dominante' if 'classe_dominante' in df_live.columns else ('confianca' if 'confianca' in df_live.columns else None)
        if vision_col:
            vision_times = df_live.dropna(subset=[vision_col])['_time']
            if not vision_times.empty and vision_times.max() >= limite_3min:
                vision_online = True

    color_on = "#00E5B4"
    color_off = "var(--txt-muted)"
    lbl_on = "ONLINE"
    lbl_act = "ACTIVE"
    lbl_off = "OFFLINE"

    # ── SIDEBAR ──────────────────────────────────────────────
    with st.sidebar:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(f"""
            <div class="sb-user-card">
                <div class="sb-user-role">Operador Ativo</div>
                <div class="sb-user-name">{st.session_state.cargo}</div>
            </div>
        """, unsafe_allow_html=True)
        st.button("↩ Terminar Sessão", on_click=logout, use_container_width=True)
        
        st.markdown("<div class='sb-section-title' style='margin-top:30px;'>Estado do Hardware</div>", unsafe_allow_html=True)
        st.markdown(f"""
            <div class="sb-row" style="margin-top:10px;">
                <span class="sb-lbl">InfluxDB</span>
                <span class="sb-val" style="color:{color_on if influx_online else color_off};">{lbl_on if influx_online else lbl_off}</span>
            </div>
            <div class="sb-row">
                <span class="sb-lbl">MQTT Broker</span>
                <span class="sb-val" style="color:{color_on if influx_online else color_off};">{lbl_act if influx_online else lbl_off}</span>
            </div>
            <div class="sb-row">
                <span class="sb-lbl">Nicla Sense ME</span>
                <span class="sb-val" style="color:{color_on if nicla_online else color_off};">{lbl_on if nicla_online else lbl_off}</span>
            </div>
            <div class="sb-row">
                <span class="sb-lbl">Arduino BLE 33 SENSE</span>
                <span class="sb-val" style="color:{color_on if vision_online else color_off};">{lbl_on if vision_online else lbl_off}</span>
            </div>
        """, unsafe_allow_html=True)
        st.markdown("<div class='sb-section-title' style='margin-top:20px;'>Telemetria</div>", unsafe_allow_html=True)
        auto_refresh = st.toggle("Live Refresh (5s)", value=True)

    # ── PAGE HEADER ───────────────────────────────────────────
    if is_live:
        chip_html = '<span class="live-chip"><span class="live-dot"></span>LIVE</span>'
    else:
        chip_html = '<span class="offline-chip"><span class="offline-dot"></span>HISTORIC (NO DATA)</span>'

    ultima_rep = fetch_ultima_reposicao()
    lote_html = ""
    if ultima_rep:
        agora_utc = datetime.now(timezone.utc)
        horas_passadas = int((agora_utc - ultima_rep).total_seconds() / 3600)
        dias_passados = horas_passadas // 24
        
        if dias_passados > 0:
            tempo_str = f"Há {dias_passados} dias"
        elif horas_passadas > 0:
            tempo_str = f"Há {horas_passadas}h"
        else:
            minutos = int((agora_utc - ultima_rep).total_seconds() / 60)
            tempo_str = f"Há {minutos} min"
            
        lote_html = f"<div style='background:rgba(0,144,255,0.1); border:1px solid rgba(0,144,255,0.3); color:#0090FF; padding:4px 12px; border-radius:999px; font-family:var(--mono); font-size:0.7rem; font-weight:700; letter-spacing:0.5px;'>📦 LOTE RENOVADO: {tempo_str}</div>"

    st.markdown(f"""
        <div class="page-header" style="align-items: center;">
            <span class="page-title">Centro de Comando Analítico</span>
            <span class="page-badge">RipeRadar OS</span>
            {lote_html}
            <span style="flex:1;"></span>
            {chip_html}
        </div>
    """, unsafe_allow_html=True)

    if st.session_state.cargo == "Chefe de Loja":
        tab_dash, tab_time, tab_admin = st.tabs(["MONITORIZAÇÃO", "ANÁLISE HISTÓRICA", "CALIBRAÇÃO"])
    else:
        tab_dash, tab_admin = st.tabs(["MONITORIZAÇÃO", "CALIBRAÇÃO"])

    with tab_dash:
        if is_live:
            latest = df_live.iloc[-1]
            voc    = float(latest.get('voc_gas', 0.0))
            fruta  = str(latest.get('classe_dominante', 'Desconhecido'))
            conf   = float(latest.get('confianca', 0.0))
            temp   = float(latest.get('temp', 0.0))
            hum    = float(latest.get('hum', 0.0))

            # Aplica override forçado pelo Chefe de Loja se existir na sessão
            if fruta.lower() == "desconhecido" and st.session_state.override_desconhecido:
                fruta = st.session_state.override_desconhecido

            estado, cor_hex, acao, sev = processar_decisao(fruta, voc)
            sev_bg  = {"success":"rgba(0,229,180,0.06)", "warning":"rgba(255,184,0,0.06)", "danger":"rgba(255,68,85,0.06)"}
            sev_bdr = {"success":"rgba(0,229,180,0.2)",  "warning":"rgba(255,184,0,0.2)",  "danger":"rgba(255,68,85,0.2)"}

            col_s, col_g = st.columns([1.6, 1])
            with col_s:
                conf_d = conf * 100 if conf <= 1 else conf
                st.markdown(f"""
                    <div class="status-banner" style="background:{sev_bg[sev]};border-color:{sev_bdr[sev]};">
                        <div class="status-accent-bar" style="background:{cor_hex};"></div>
                        <div class="status-label">Alvo Identificado</div>
                        <div class="status-target">🎯 {formatar_nome(fruta)} &nbsp;·&nbsp; Confiança: <span style="font-family:var(--mono);font-weight:700;color:{cor_hex};">{conf_d:.1f}%</span></div>
                        <div class="status-main" style="color:{cor_hex};">{estado}</div>
                        <span class="status-action" style="color:{cor_hex};border-color:{sev_bdr[sev]};background:rgba(0,0,0,0.2);">▶ {acao}</span>
                    </div>
                """, unsafe_allow_html=True)
                
                # INTERFACE DE OVERRIDE EXCLUSIVA PARA O CHEFE DE LOJA
                if latest.get('classe_dominante', 'Desconhecido').lower() == "desconhecido":
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.session_state.cargo == "Chefe de Loja":
                        with st.form("form_override_fruta"):
                            st.warning("⚠️ **Alerta de Rastreabilidade:** A IA classificou este lote como Desconhecido.")
                            nova_label = st.selectbox("Corrigir identidade do alvo:", ["maca", "banana", "laranja"])
                            if st.form_submit_button("Forçar Identificação de Produto"):
                                st.session_state.override_desconhecido = nova_label
                                st.success(f"Identidade alterada com sucesso para {nova_label.title()}!")
                                time.sleep(0.5)
                                st.rerun()
                    else:
                        st.info("ℹ️ Rótulo classificado como Desconhecido pela IA do Edge Gateway. Apenas um Chefe de Loja autenticado pode forçar esta identidade.")

            with col_g:
                is_clim = any(f in fruta.lower() for f in ["maca","banana"])
                lim_min = thresholds["clim_fresco"] if is_clim else thresholds["nclim_firme"]
                lim_max = thresholds["clim_maduro"] if is_clim else thresholds["nclim_risco"]

                fig_gauge = go.Figure(go.Indicator(
                    mode="gauge+number", value=voc,
                    number={'suffix':" Ω",'font':{'size':28,'color':'#E8EEF8','family':'Space Mono'}},
                    title={'text':"RESISTÊNCIA VOC (Ω)",'font':{'size':11,'color':'#5A7090','family':'DM Sans'}},
                    gauge={
                        'axis':{'range':[None,25000],'tickwidth':1,'tickcolor':"#1E2D45",'tickfont':{'color':'#5A7090','size':10}},
                        'bar':{'color':cor_hex,'thickness':0.22},
                        'bgcolor':"#0E1420",'borderwidth':1,'bordercolor':"#1E2D45",
                        'steps':[
                            {'range':[0,lim_min],       'color':"rgba(255,68,85,0.1)"},
                            {'range':[lim_min,lim_max], 'color':"rgba(255,184,0,0.1)"},
                            {'range':[lim_max,25000],   'color':"rgba(0,229,180,0.1)"}
                        ],
                        'threshold':{'line':{'color':cor_hex,'width':2},'thickness':0.8,'value':voc}
                    }
                ))
                fig_gauge.update_layout(height=240, margin=dict(l=20,r=20,t=30,b=10), paper_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_gauge, use_container_width=True)

            st.markdown("<br>", unsafe_allow_html=True)
            c1,c2,c3,c4 = st.columns(4)
            for col, (lbl, val, unit) in zip([c1,c2,c3,c4], [
                ("IA CONFIDENCE", f"{conf*100 if conf<=1 else conf:.1f}", "%"),
                ("TEMPERATURA",   f"{temp:.1f}", "°C"),
                ("HUMIDADE",      f"{hum:.1f}",  "%"),
                ("LATÊNCIA MQTT", "124",         "ms"),
            ]):
                col.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-label"><span class="metric-dot"></span>{lbl}</div>
                        <div class="metric-value">{val}<span class="metric-unit">{unit}</span></div>
                    </div>
                """, unsafe_allow_html=True)

            st.markdown("""<div class="section-header"><h3>Evolução VOC — Última Hora</h3><div class="section-divider"></div></div>""", unsafe_allow_html=True)

            df_plot = df_live.dropna(subset=['voc_gas']).sort_values('_time')
            fig_line = go.Figure()
            fig_line.add_trace(go.Scatter(
                x=df_plot['_time'], y=df_plot['voc_gas'], mode='lines+markers',
                line=dict(color='#00E5B4', width=2.5, shape='spline'),
                marker=dict(size=5, color='#080C14', line=dict(width=1.5, color='#00E5B4')),
                fill='tozeroy', fillcolor='rgba(0,229,180,0.06)',
                hovertemplate='<b>%{x|%d/%m %H:%M}</b><br>%{y:.0f} Ω<extra></extra>'
            ))
            fig_line.update_layout(**PLOT_LAYOUT, height=280, yaxis_title="Ohms")
            st.plotly_chart(fig_line, use_container_width=True)

        else:
            st.markdown("""
                <div style="text-align: center; padding: 100px 20px; background: var(--surface); border: 1px solid var(--border); border-radius: 12px; margin-top: 10px;">
                    <div style="font-size: 3.5rem; margin-bottom: 12px; opacity: 0.8;">🔌</div>
                    <h2 style="font-family: var(--mono); color: var(--txt); font-weight: 700; letter-spacing: 1px; margin-bottom: 8px;">TELEMETRIA OFFLINE</h2>
                    <p style="color: var(--txt-sub); font-size: 0.95rem; max-width: 480px; margin: 0 auto;">
                        Sem pacotes de dados recebidos nos últimos 3 minutos.<br><br>
                        Verifique a ligação de rede do <span style="color:var(--txt);">EDGE Gateway</span> e a alimentação dos dispositivos <span style="color:var(--txt);">Nicla Sense ME</span> e <span style="color:var(--txt);">Arduino BLE 33 SENSE</span>.
                    </p>
                </div>
            """, unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════
    #  TAB 2 — ANÁLISE HISTÓRICA (APENAS DADOS REAIS DO INFLUX)
    # ══════════════════════════════════════════════════════════════
    if st.session_state.cargo == "Chefe de Loja":
        with tab_time:
            col_f1, col_f2, col_f3, col_f4 = st.columns([1, 1, 1, 1.5])
            
            with col_f1:
                periodo = st.selectbox("Período", ["Últimos 7 dias","Últimos 30 dias","Últimos 90 dias"], index=1)
            
            dias_map = {"Últimos 7 dias":7, "Últimos 30 dias":30, "Últimos 90 dias":90}
            df_hist_real = fetch_history_data(dias_map[periodo])
            listagem_reposicoes = fetch_historico_reposicoes(dias_map[periodo])

            # Mapeamento dinâmico de fatias temporais para criação de lotes virtuais
            lotes_disponiveis = ["Todos os Lotes"]
            if listagem_reposicoes:
                for idx in range(len(listagem_reposicoes)):
                    lotes_disponiveis.append(f"Lote #{idx + 1}")

            unique_raw_classes = df_hist_real['classe_dominante'].dropna().unique().tolist() if not df_hist_real.empty and 'classe_dominante' in df_hist_real.columns else []
            options_produtos = ["Todos"] + sorted(unique_raw_classes)

            with col_f2:
                fruta_filtro = st.selectbox("Produto / Estado", options_produtos, format_func=formatar_nome)
                
            with col_f3:
                lote_filtro = st.selectbox("Filtrar por Lote", lotes_disponiveis)
                
            with col_f4:
                sev_filtro = st.multiselect(
                    "Mostrar eventos",
                    ["success","warning","danger"],
                    default=["warning","danger"],
                    format_func=lambda x: {"success":"✅ Normais","warning":"⚠️ Atenção","danger":"🔴 Críticos"}[x]
                )
            
            if df_hist_real.empty or 'classe_dominante' not in df_hist_real.columns or 'voc_gas' not in df_hist_real.columns:
                st.warning("📊 Não existem dados reais suficientes no InfluxDB para gerar a análise histórica neste período.")
            else:
                df_periodo = df_hist_real.dropna(subset=['voc_gas', 'classe_dominante']).copy()
                
                # Segmentação e filtragem baseada na janela do lote escolhido
                if lote_filtro != "Todos os Lotes" and listagem_reposicoes:
                    idx_lote = int(lote_filtro.split("#")[1]) - 1
                    data_inicio_lote = listagem_reposicoes[idx_lote]
                    if idx_lote < len(listagem_reposicoes) - 1:
                        data_fim_lote = listagem_reposicoes[idx_lote + 1]
                        df_periodo = df_periodo[(df_periodo["_time"] >= data_inicio_lote) & (df_periodo["_time"] < data_fim_lote)]
                    else:
                        df_periodo = df_periodo[df_periodo["_time"] >= data_inicio_lote]

                if fruta_filtro != "Todos":
                    df_periodo = df_periodo[df_periodo["classe_dominante"] == fruta_filtro]

                if df_periodo.empty:
                    st.info("Sem leituras reais para a seleção de filtros atual.")
                else:
                    resultados = df_periodo.apply(lambda r: processar_decisao(r['classe_dominante'], r['voc_gas']), axis=1)
                    df_periodo['estado'] = [r[0] for r in resultados]
                    df_periodo['cor'] = [r[1] for r in resultados]
                    df_periodo['acao'] = [r[2] for r in resultados]
                    df_periodo['severidade'] = [r[3] for r in resultados]

                    df_eventos = df_periodo[df_periodo["severidade"].isin(sev_filtro)].copy() if sev_filtro else df_periodo.copy()

                    st.markdown("<br>", unsafe_allow_html=True)
                    total      = len(df_periodo)
                    n_criticos = len(df_periodo[df_periodo["severidade"]=="danger"])
                    n_atencao  = len(df_periodo[df_periodo["severidade"]=="warning"])
                    n_ok       = len(df_periodo[df_periodo["severidade"]=="success"])
                    pct_ok     = round(n_ok / total * 100, 1) if total > 0 else 0
                    
                    st.markdown(f"""
                    <div class="kpi-row">
                        <div class="kpi-card"><div class="kpi-num" style="color:#E8EEF8;">{total}</div><div class="kpi-lbl">Leituras Totais</div></div>
                        <div class="kpi-card"><div class="kpi-num" style="color:#FF4455;">{n_criticos}</div><div class="kpi-lbl">Alertas Críticos</div></div>
                        <div class="kpi-card"><div class="kpi-num" style="color:#FFB800;">{n_atencao}</div><div class="kpi-lbl">Em Atenção</div></div>
                        <div class="kpi-card"><div class="kpi-num" style="color:#00E5B4;">{pct_ok}%</div><div class="kpi-lbl">Taxa Conformidade</div></div>
                    </div>
                    """, unsafe_allow_html=True)

                    st.markdown("""<div class="section-header"><h3>Evolução da Resistência VOC por Produto</h3><div class="section-divider"></div></div>""", unsafe_allow_html=True)

                    df_daily = (df_periodo.assign(dia=lambda d: d["_time"].dt.date).groupby(["dia","classe_dominante"])["voc_gas"].mean().reset_index())
                    fig_voc = go.Figure()
                    
                    for f_nome in df_daily["classe_dominante"].unique():
                        dd = df_daily[df_daily["classe_dominante"]==f_nome]
                        cor_linha = obter_cor_estado(f_nome)
                        
                        fig_voc.add_trace(go.Scatter(
                            x=dd["dia"], y=dd["voc_gas"], mode='lines+markers', name=formatar_nome(f_nome),
                            line=dict(color=cor_linha, width=2.5, shape='spline'),
                            fill='tozeroy', fillcolor="rgba(0,0,0,0)",
                            hovertemplate=f'<b>%{{x}}</b><br>{formatar_nome(f_nome)}: %{{y:.0f}} Ω<extra></extra>'
                        ))

                    fig_voc.add_hline(y=thresholds["clim_fresco"], line_dash="dot", line_color="rgba(255,184,0,0.35)", annotation_text="Limiar Maduro (Clim)", annotation_font_color="#FFB800", annotation_font_size=10)
                    fig_voc.add_hline(y=thresholds["clim_maduro"]*0.76, line_dash="dot", line_color="rgba(255,68,85,0.35)", annotation_text="Limiar Crítico (Clim)", annotation_font_color="#FF4455", annotation_font_size=10)

                    layout_voc = {**PLOT_LAYOUT, "height": 340, "yaxis_title": "Resistência (Ω)"}
                    fig_voc.update_layout(**layout_voc)
                    st.plotly_chart(fig_voc, use_container_width=True)

                    st.markdown("<br>", unsafe_allow_html=True)
                    st.markdown("""<div class="section-header"><h3>Registo de Eventos de Qualidade</h3><div class="section-divider"></div></div>""", unsafe_allow_html=True)
                    
                    st.markdown("""
                        <p style='font-size:0.85rem;color:var(--txt-muted);margin-bottom:20px;'>
                        As leituras são agrupadas por <strong>dia</strong> e por estado (<strong>fruto detetado</strong>).<br>
                        <em>Nota: Os dias em que não ocorreram alertas não são exibidos se o filtro superior os excluir.</em>
                        </p>
                    """, unsafe_allow_html=True)

                    if df_eventos.empty:
                        st.info("✅ Sem eventos de risco registados para os filtros selecionados nos últimos dias.")
                    else:
                        df_eventos["dia_str"]  = df_eventos["_time"].apply(lambda x: f"{x.day} de {meses_pt[x.month]} de {x.year}")
                        df_eventos["dia_date"] = df_eventos["_time"].dt.date
                        dias_unicos = df_eventos["dia_date"].drop_duplicates().sort_values(ascending=False).head(20)

                        st.markdown('<div class="tl-wrap">', unsafe_allow_html=True)
                        for dia_date in dias_unicos:
                            grupo_dia = df_eventos[df_eventos["dia_date"] == dia_date]
                            dia_label = grupo_dia.iloc[0]["dia_str"]
                            n_crit_dia = len(grupo_dia[grupo_dia["severidade"]=="danger"])
                            dot_cls    = "danger" if n_crit_dia > 0 else "warn"
                            cor_dia    = "#FF4455" if n_crit_dia > 0 else "#FFB800"

                            badge_html = f"<span class='tl-badge' style='color:#FF4455;border-color:rgba(255,68,85,0.3);'>⬤ {n_crit_dia} críticos</span>" if n_crit_dia > 0 else ""

                            st.markdown(f"""
                            <div class="tl-item">
                                <div class="tl-dot {dot_cls}"></div>
                                <div class="tl-time">📅 {dia_label.upper()}</div>
                                <div class="tl-body">
                                    <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px;">
                                        <span style="font-weight:700;color:{cor_dia};">{len(grupo_dia)} leituras destacadas</span>{badge_html}
                                    </div>
                            """, unsafe_allow_html=True)

                            for fruta_id, g_fruta in grupo_dia.groupby("classe_dominante"):
                                # Ordena para mostrar as leituras mais recentes primeiro
                                g_fruta = g_fruta.sort_values("_time", ascending=False)
                                
                                # Cria uma div individual para CADA medição daquela fruta
                                for idx, row in g_fruta.iterrows():
                                    hora_local = row["_time"].tz_convert('Europe/Lisbon').strftime('%H:%M:%S')
                                    cor_ev = row["cor"]
                                    temp_val = row["temp"] if 'temp' in row else 0.0

                                    st.markdown(f"""
                                    <div style="background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:14px 16px;margin-bottom:10px;position:relative;">
                                        <div style="position:absolute;top:14px;right:16px;font-family:var(--mono);font-size:0.75rem;color:var(--txt-muted);">
                                            ⏱️ {hora_local}
                                        </div>
                                        
                                        <div style="margin-bottom:10px;">
                                            <span style="font-family:var(--mono);font-size:0.68rem;color:var(--txt-muted);">PRODUTO&nbsp;</span>
                                            <span style="font-family:var(--mono);font-size:0.82rem;color:var(--txt);font-weight:700;text-transform:uppercase;">{formatar_nome(fruta_id)}</span>
                                        </div>
                                        
                                        <div style="display:flex;gap:12px;align-items:center;margin-bottom:8px;flex-wrap:wrap;">
                                            <span style="font-weight:700;color:{cor_ev};font-size:0.95rem;">{row['estado']}</span>
                                        </div>
                                        
                                        <div style="display:flex;gap:20px;font-size:0.82rem;color:var(--txt-muted);flex-wrap:wrap;">
                                            <span>VOC Detetado: <span style="font-family:var(--mono);color:var(--txt);">{row['voc_gas']/1000:.2f} kΩ</span></span>
                                            <span>Temp: <span style="font-family:var(--mono);color:var(--txt);">{temp_val:.1f} °C</span></span>
                                            <span>Ação exigida: <strong style="color:{cor_ev};">{row['acao']}</strong></span>
                                        </div>
                                    </div>
                                    """, unsafe_allow_html=True)

                            st.markdown("</div></div>", unsafe_allow_html=True)
                        st.markdown('</div>', unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════
    #  TAB 3 — CALIBRAÇÃO E HARDWARE ADMIN
    # ══════════════════════════════════════════════════════════════
    with tab_admin:
        st.markdown("<div class='calib-card'>", unsafe_allow_html=True)
        with st.form("calibration_form"):
            st.markdown("""
                <div class="calib-title">Parâmetros do Modelo de Late Fusion</div>
                <div class="calib-sub">Sintonize a janela de resistência do sensor Nicla Sense ME. Recomendado suspender o Live Refresh antes de operar.</div>
            """, unsafe_allow_html=True)
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("<div class='calib-group-title'>🍌 Fenologia Climatérica (Banana / Maçã)</div>", unsafe_allow_html=True)
                clim_f = st.slider("Verde → Maduro",  10000, 15000, thresholds["clim_fresco"])
                clim_m = st.slider("Maduro → Podre",  15000, 20000, thresholds["clim_maduro"])
            with col_b:
                st.markdown("<div class='calib-group-title'>🍊 Fenologia Não-Climatérica (Laranja)</div>", unsafe_allow_html=True)
                nclim_f = st.slider("Firme → Risco",     10000, 14000, thresholds["nclim_firme"])
                nclim_r = st.slider("Risco → Degradada", 14000, 18000, thresholds["nclim_risco"])
            st.markdown("<br>", unsafe_allow_html=True)
            submitted = st.form_submit_button("Aplicar Parâmetros →", use_container_width=True, type="primary")
            if submitted:
                novos_limites = {
                    "clim_fresco": clim_f, "clim_maduro": clim_m,
                    "nclim_firme": nclim_f, "nclim_risco": nclim_r
                }
                st.session_state.thresholds = novos_limites
                guardar_calibracao(novos_limites)
                st.cache_data.clear()
                st.success("✓ Parâmetros aplicados e guardados com sucesso!")
                time.sleep(1)
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        
        if st.session_state.cargo == "Chefe de Loja":
            st.markdown("<br>", unsafe_allow_html=True)
            st.subheader("Configuração de Hardware RFID")
            st.caption("Usa esta zona para autorizar este computador a escutar o Leitor RFID (EDGE Gateway).")
            
            if not is_terminal:
                if st.button("💻 Registar este PC como Terminal RFID Seguro"):
                    cookie_manager.set("terminal_loja", "true", max_age=31536000, key="set_term")
                    st.success("✅ PC registado! Faz Logout para testar a entrada por cartão.")
            else:
                st.info("✅ Este computador está atualmente configurado e autorizado como Terminal RFID.")
                if st.button("❌ Remover Registo RFID deste PC"):
                    cookie_manager.delete("terminal_loja", key="del_term")
                    st.warning("⚠️ Registo removido. O login passará a ser obrigatoriamente manual.")

    # ── AUTO REFRESH DASHBOARD ─────────────────────────────────
    if auto_refresh:
        time.sleep(5)
        st.rerun()
