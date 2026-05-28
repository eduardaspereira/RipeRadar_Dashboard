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

def fetch_ultima_reposicao():
    try:
        client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
        query = f'''
        from(bucket: "{INFLUX_BUCKET}")
          |> range(start: -30d)
          |> filter(fn: (r) => r["_measurement"] == "rfid_operacoes")
          |> filter(fn: (r) => r["_field"] == "acao")
          |> filter(fn: (r) => r["_value"] == "carga_climaterica" or r["_value"] == "carga_nao_climaterica")
          |> last()
        '''
        result = client.query_api().query(query)
        for table in result:
            for record in table.records:
                return record.get_time()
        return None
    except:
        return None

def fetch_logs_operadores():
    try:
        client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
        query = f'''
        from(bucket: "{INFLUX_BUCKET}")
          |> range(start: -7d)
          |> filter(fn: (r) => r["_measurement"] == "rfid_login" or r["_measurement"] == "rfid_operacoes")
          |> keep(columns: ["_time", "_measurement", "_value", "_field"])
          |> group() 
          |> sort(columns: ["_time"], desc: true)
        '''
        df = client.query_api().query_data_frame(query)
        if isinstance(df, list): 
            df = pd.concat(df, ignore_index=True)
            
        if isinstance(df, pd.DataFrame) and not df.empty:
            df = df.sort_values('_time', ascending=False)
            df['_time'] = pd.to_datetime(df['_time']).dt.tz_convert('Europe/Lisbon')
            return df
        return pd.DataFrame()
    except:
        return pd.DataFrame()
    
def logout():
    st.session_state.logado = False
    st.session_state.cargo = ""

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
.metric-value { font-family: var(--mono); font-size: 1.8rem; font-weight: 700; color: var(--txt); line-height: 1.2; }
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

.notif-card { display: flex; align-items: center; background: var(--surface2); border: 1px solid var(--border); border-radius: 12px; padding: 16px 20px; margin-bottom: 12px; transition: border-color 0.2s, transform 0.2s; }
.notif-card:hover { border-color: var(--border-lit); transform: translateY(-2px); }
.notif-icon { font-size: 1.6rem; margin-right: 18px; display: flex; align-items: center; justify-content: center; width: 50px; height: 50px; background: var(--surface); border: 1px solid var(--border); border-radius: 50%; }
.notif-content { flex: 1; }
.notif-title { font-size: 1.05rem; font-weight: 700; color: var(--txt); margin-bottom: 4px; }
.notif-sub { font-family: var(--mono); font-size: 0.85rem; color: var(--txt-muted); }
.notif-meta { text-align: right; }
.notif-time { font-family: var(--mono); font-size: 0.75rem; color: var(--txt-sub); margin-bottom: 8px; font-weight: 700; }
.notif-badge { display: inline-block; padding: 4px 10px; border-radius: 6px; font-family: var(--mono); font-size: 0.65rem; font-weight: 700; letter-spacing: 1px; border: 1px solid; }

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
#  THRESHOLDS & FUNÇÕES BASE (Lógica de Atualização Forçada)
# ══════════════════════════════════════════════════════════════
def carregar_calibracao():
    limites_predefinidos = {
        "clim_limiar": 28500,
        "nclim_limiar": 28500
    }
    
    if os.path.exists("calibracao.json"):
        try:
            with open("calibracao.json", "r") as f:
                dados = json.load(f)
                if "clim_limiar" in dados:
                    return dados
        except Exception:
            pass
            
    return limites_predefinidos

def guardar_calibracao(limites):
    with open("calibracao.json", "w") as f:
        json.dump(limites, f)

if 'thresholds' not in st.session_state:
    st.session_state.thresholds = carregar_calibracao()
else:
    if "clim_limiar" not in st.session_state.thresholds:
        st.session_state.thresholds = carregar_calibracao()

thresholds = st.session_state.thresholds

def formatar_nome(raw_name):
    """Limpa nomes para o display visual"""
    if raw_name == "Todos": return "Todos os Produtos"
    return str(raw_name).replace('_', ' ').title()

def obter_cor_estado(raw_name):
    nome_min = str(raw_name).lower()
    if any(x in nome_min for x in ["fresc"]): return "#00E5B4"
    if any(x in nome_min for x in ["podr", "senesc"]): return "#FF4455"
    return "#8BA0BC"

meses_pt = {1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril", 5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto", 9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"}

# ── FUNÇÕES DE LATE FUSION LOCAL (PARA OS SLIDERS FUNCIONAREM) ──
def calcular_late_fusion_local(row_or_dict):
    """Refaz a Late Fusion baseando-se nos valores brutos e na Calibração atual do Dashboard. Apenas suporta Fruta Climatérica / Não Climatérica em estado Fresca ou Senescência, retendo a fruta."""
    label = str(row_or_dict.get('label_camara', row_or_dict.get('classe_dominante', 'desconhecido'))).lower()
    conf = float(row_or_dict.get('confianca', 1.0))
    voc = float(row_or_dict.get('voc_gas', 0.0))
    
    fruto_especifico = "desconhecido"
    categoria = "desconhecido"
    
    # Identificar fruta específica e categoria fenomenológica
    if "banana" in label:
        fruto_especifico = "banana"
        categoria = "climaterica"
    elif any(x in label for x in ["maca", "macã", "apple"]):
        fruto_especifico = "maçã"
        categoria = "climaterica"
    elif "laranja" in label:
        fruto_especifico = "laranja"
        categoria = "nao_climaterica"
            
    t = st.session_state.thresholds
    clim_limiar = t.get("clim_limiar", 28500)
    nclim_limiar = t.get("nclim_limiar", 28500)
    
    nicla_state = "desconhecido"
    if categoria == "climaterica":
        if voc > clim_limiar: nicla_state = "fresca"
        else: nicla_state = "senescência"
    elif categoria == "nao_climaterica":
        if voc > nclim_limiar: nicla_state = "fresca"
        else: nicla_state = "senescência"
        
    classe_final = f"{fruto_especifico}_{nicla_state}" if fruto_especifico != "desconhecido" else "desconhecido"

    if conf < 0.60 and fruto_especifico != "desconhecido":
        return classe_final, "VOC OVERRIDE"
    else:
        return classe_final, "VISÃO + VOC"

def processar_decisao(classe_fused):
    """
    Retorna os textos e cores FINAIS da interface baseando-se no binómio fresca/senescência.
    """
    c = str(classe_fused).lower()
    if "desconhecido" in c:
        return ("DESCONHECIDO", "#8BA0BC", "AGUARDAR DADOS", "warning")
        
    is_clim = any(f in c for f in ["maçã", "maca", "banana", "apple"])
    
    if "fresc" in c:
        return ("FRESCA", "#00E5B4", "PRATELEIRA", "success")
    elif "senescência" in c or "podre" in c:
        return ("SENESCÊNCIA / PODRE", "#FF4455", "RETIRAR DE IMEDIATO" if is_clim else "REJEITAR LOTE", "danger")
    else:
        return ("DESCONHECIDO", "#8BA0BC", "AGUARDAR DADOS", "warning")

# ── LEITURA REAL DA BASE DE DADOS (INFLUXDB) ──
def fetch_live_data():
    try:
        client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
        query  = (f'from(bucket: "{INFLUX_BUCKET}") |> range(start: -2h)'
                  f' |> filter(fn: (r) => r["_measurement"] == "mqtt_consumer")'
                  f' |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")')
        df = client.query_api().query_data_frame(query)
        
        if isinstance(df, list): df = pd.concat(df, ignore_index=True)
        
        if isinstance(df, pd.DataFrame) and not df.empty:
            df['_time'] = pd.to_datetime(df['_time']).dt.tz_convert('Europe/Lisbon')
            df = df.sort_values(by='_time', ascending=True).reset_index(drop=True)
            return df
        return pd.DataFrame()
    except:
        return pd.DataFrame()

@st.cache_data(ttl=300)
def fetch_history_data(time_range):
    try:
        client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
        query  = (f'from(bucket: "{INFLUX_BUCKET}") |> range(start: -{time_range})'
                  f' |> filter(fn: (r) => r["_measurement"] == "mqtt_consumer")'
                  f' |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")')
        df = client.query_api().query_data_frame(query)
        
        if isinstance(df, list): df = pd.concat(df, ignore_index=True)
        
        if isinstance(df, pd.DataFrame) and not df.empty:
            df['_time'] = pd.to_datetime(df['_time']).dt.tz_convert('Europe/Lisbon')
            df = df.sort_values(by='_time', ascending=True).reset_index(drop=True)
            return df
        return pd.DataFrame()
    except:
        return pd.DataFrame()

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
    # ── VERIFICAÇÃO DE TELEMETRIA RECENTE (ÚLTIMOS 5 MIN) ─────
    df_live = fetch_live_data()
    agora_pt = pd.Timestamp.utcnow().tz_convert('Europe/Lisbon')
    limite_tolerancia = agora_pt - pd.Timedelta(minutes=5)
    
    is_live = False
    influx_online = False
    nicla_online = False
    vision_online = False
    
    if not df_live.empty and '_time' in df_live.columns:
        influx_online = True
        if df_live['_time'].max() >= limite_tolerancia:
            is_live = True
            
        if 'voc_gas' in df_live.columns:
            voc_times = df_live.dropna(subset=['voc_gas'])['_time']
            if not voc_times.empty and voc_times.max() >= limite_tolerancia:
                nicla_online = True
                
        vision_col = 'classe_dominante' if 'classe_dominante' in df_live.columns else ('confianca' if 'confianca' in df_live.columns else None)
        if vision_col:
            vision_times = df_live.dropna(subset=[vision_col])['_time']
            if not vision_times.empty and vision_times.max() >= limite_tolerancia:
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
        chip_html = '<span class="offline-chip"><span class="offline-dot"></span>OFFLINE</span>'

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
            
        lote_html = f"<div style='background:rgba(0,144,255,0.1); border:1px solid rgba(0,144,255,0.3); color:#0090FF; padding:4px 12px; border-radius:999px; font-family:var(--mono); font-size:0.7rem; font-weight:700; letter-spacing:0.5px;'> Fruta Revista {tempo_str}</div>"

    st.markdown(f"""
        <div class="page-header" style="align-items: center;">
            <span class="page-title">Centro de Comando Analítico</span>
            <span class="page-badge">RipeRadar OS</span>
            {lote_html}
            <span style="flex:1;"></span>
            {chip_html}
        </div>
    """, unsafe_allow_html=True)

    # ── TABS ──────────────────────────────────────────────────
    if st.session_state.cargo == "Chefe de Loja":
        tab_dash, tab_time, tab_admin, tab_logs = st.tabs(["MONITORIZAÇÃO", "ANÁLISE HISTÓRICA", "CALIBRAÇÃO", "LOGS DOS OPERADORES"])
    else:
        tab_dash, tab_admin = st.tabs(["MONITORIZAÇÃO", "CALIBRAÇÃO"])

    with tab_dash:
        if is_live:
            latest = df_live.iloc[-1].to_dict()
            voc    = float(latest.get('voc_gas', 0.0))
            conf   = float(latest.get('confianca', 1.0))
            temp   = float(latest.get('temp', 0.0))
            hum    = float(latest.get('hum', 0.0))

            # 1. Faz a fusão calculando localmente
            decisao_final, fusion_mode = calcular_late_fusion_local(latest)
            
            # 2. Constrói o texto e cor grandes
            estado, cor_hex, acao, sev = processar_decisao(decisao_final)
            
            sev_bg  = {"success":"rgba(0,229,180,0.06)", "warning":"rgba(255,184,0,0.06)", "danger":"rgba(255,68,85,0.06)"}
            sev_bdr = {"success":"rgba(0,229,180,0.2)",  "warning":"rgba(255,184,0,0.2)",  "danger":"rgba(255,68,85,0.2)"}

            # 3. Lógica para as Cores de Fusão
            conf_percent = conf * 100 if conf <= 1 else conf
            fusion_color = "#FFB800" if "OVERRIDE" in fusion_mode else "#00E5B4"
            system_conf_display = "99.9%" if "OVERRIDE" in fusion_mode else f"{conf_percent:.1f}%"

            col_s, col_g = st.columns([1.6, 1])
            with col_s:
                st.markdown(f"""
                    <div class="status-banner" style="background:{sev_bg.get(sev, 'rgba(139,160,188,0.06)')};border-color:{sev_bdr.get(sev, 'rgba(139,160,188,0.2)')};">
                        <div class="status-accent-bar" style="background:{cor_hex};"></div>
                        <div class="status-label">Fruta Identificada</div>
                        <div class="status-target">{formatar_nome(decisao_final)} &nbsp;·&nbsp; Confiança do Sistema: <span style="font-family:var(--mono);font-weight:700;color:{cor_hex};">{conf_percent:.1f}%</span></div>
                        <div class="status-main" style="color:{cor_hex};">{estado}</div>
                        <span class="status-action" style="color:{cor_hex};border-color:{sev_bdr.get(sev, 'rgba(139,160,188,0.2)')};background:rgba(0,0,0,0.2);">▶ {acao}</span>
                    </div>
                """, unsafe_allow_html=True)

            with col_g:
                is_clim = any(f in decisao_final.lower() for f in ["maçã", "maca", "banana", "apple"])
                limiar_atual = thresholds.get("clim_limiar", 28500) if is_clim else thresholds.get("nclim_limiar", 28500)

                # Gráfico ajustado (19kohm a 40kohm), fresca/senescência apenas
                fig_gauge = go.Figure(go.Indicator(
                    mode="gauge+number", value=voc,
                    number={'suffix':" Ω",'font':{'size':28,'color':'#E8EEF8','family':'Space Mono'}},
                    title={'text':"RESISTÊNCIA VOC (Ω)",'font':{'size':11,'color':'#5A7090','family':'DM Sans'}},
                    gauge={
                        'axis':{'range':[19000, 40000],'tickwidth':1,'tickcolor':"#1E2D45",'tickfont':{'color':'#5A7090','size':10}},
                        'bar':{'color':cor_hex,'thickness':0.22},
                        'bgcolor':"#0E1420",'borderwidth':1,'bordercolor':"#1E2D45",
                        'steps':[
                            {'range':[19000, limiar_atual],  'color':"rgba(255,68,85,0.15)"},  # Senescência (Baixa resistência = mais gás)
                            {'range':[limiar_atual, 40000],  'color':"rgba(0,229,180,0.15)"}   # Fresca
                        ],
                        'threshold':{'line':{'color':cor_hex,'width':2},'thickness':0.8,'value':voc}
                    }
                ))
                fig_gauge.update_layout(height=240, margin=dict(l=20,r=20,t=30,b=10), paper_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_gauge, use_container_width=True)

            st.markdown("<br>", unsafe_allow_html=True)
            c1,c2,c3,c4 = st.columns(4)
            for col, (lbl, val, unit, color) in zip([c1,c2,c3,c4], [
                ("CONFIANÇA SISTEMA", system_conf_display, "", "#E8EEF8"),
                ("MODO DE FUSÃO",     fusion_mode,         "", fusion_color),
                ("TEMPERATURA",       f"{temp:.1f}",       "°C", "#E8EEF8"),
                ("HUMIDADE",          f"{hum:.1f}",        "%", "#E8EEF8"),
            ]):
                col.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-label"><span class="metric-dot"></span>{lbl}</div>
                        <div class="metric-value" style="color:{color}; font-size:1.5rem;">{val}<span class="metric-unit">{unit}</span></div>
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
                        Sem pacotes de dados recebidos nos últimos 5 minutos.<br><br>
                        Verifique a ligação de rede do <span style="color:var(--txt);">EDGE Gateway</span> e a alimentação dos dispositivos <span style="color:var(--txt);">Nicla Sense ME</span> e <span style="color:var(--txt);">Arduino BLE 33 SENSE</span>.
                    </p>
                </div>
            """, unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════
    #  TAB 2 — ANÁLISE HISTÓRICA (APENAS DADOS REAIS DO INFLUX)
    # ══════════════════════════════════════════════════════════════
    if st.session_state.cargo == "Chefe de Loja":
        with tab_time:
            col_f1, col_f2, col_f3 = st.columns([1, 1, 2])
            
            with col_f1:
                periodo = st.selectbox("Período", ["Últimas 12 horas", "Últimas 24 horas", "Últimos 7 dias", "Últimos 30 dias", "Últ
