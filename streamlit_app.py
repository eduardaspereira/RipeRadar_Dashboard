import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import random
import time
from datetime import datetime, timedelta
from influxdb_client import InfluxDBClient
from streamlit_autorefresh import st_autorefresh
import extra_streamlit_components as stx

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="RipeRadar OS", page_icon="🍎", layout="wide")

# --- 2. GESTOR DE COOKIES ---
@st.cache_resource
def get_manager():
    return stx.CookieManager()

cookie_manager = get_manager()
is_terminal = cookie_manager.get(cookie="terminal_loja") == "true"

# --- 3. CREDENCIAIS (Usando st.secrets) ---
try:
    INFLUX_URL    = st.secrets["INFLUX_URL"]
    INFLUX_TOKEN  = st.secrets["INFLUX_TOKEN"]
    INFLUX_ORG    = st.secrets["INFLUX_ORG"]
    INFLUX_BUCKET = st.secrets["INFLUX_BUCKET"]
except Exception as e:
    # Fallback local se os secrets não estiverem configurados no teste
    INFLUX_URL = "https://eu-central-1-1.aws.cloud2.influxdata.com"
    INFLUX_TOKEN = "TEU_TOKEN"
    INFLUX_ORG = "TUA_ORG"
    INFLUX_BUCKET = "TEU_BUCKET"

# --- 4. ESTADO DA SESSÃO ---
if 'logado' not in st.session_state:
    st.session_state.logado = False
    st.session_state.cargo = ""

def verificar_login_manual():
    """Validação para quando o login é feito via teclado"""
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
    """Consulta o InfluxDB para ver se houve login RFID nos últimos 5 segundos"""
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
    content: '';
    position: fixed; inset: 0;
    background-image:
        linear-gradient(rgba(0,229,180,0.015) 1px, transparent 1px),
        linear-gradient(90deg, rgba(0,229,180,0.015) 1px, transparent 1px);
    background-size: 40px 40px;
    pointer-events: none; z-index: 0;
}
#MainMenu, footer, header { visibility: hidden; }
h1,h2,h3,h4 { font-family: var(--sans); }

[data-testid="stSidebar"] { background: var(--surface) !important; border-right: 1px solid var(--border) !important; }
[data-testid="stSidebar"] > div { padding-top: 0 !important; }

.metric-card {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 12px; padding: 20px 22px;
    position: relative; overflow: hidden; transition: border-color 0.2s;
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
    border-radius: 14px; padding: 28px 32px;
    border: 1px solid var(--border); background: var(--surface2);
    position: relative; overflow: hidden;
}
.status-banner::before {
    content: ''; position: absolute; inset: 0;
    background: radial-gradient(ellipse at top left, rgba(0,229,180,0.06) 0%, transparent 60%);
    pointer-events: none;
}
.status-accent-bar { position: absolute; left: 0; top: 0; bottom: 0; width: 4px; border-radius: 14px 0 0 14px; }
.status-label  { font-family: var(--mono); font-size: 0.7rem; text-transform: uppercase; letter-spacing: 2px; color: var(--txt-muted); margin-bottom: 12px; }
.status-target { font-size: 0.95rem; color: var(--txt-sub); margin-bottom: 16px; font-weight: 500; }
.status-main   { font-family: var(--mono); font-size: 2.4rem; font-weight: 700; line-height: 1; margin-bottom: 16px; }
.status-action { display: inline-flex; align-items: center; gap: 8px; padding: 8px 18px; border-radius: 999px; font-family: var(--mono); font-size: 0.78rem; font-weight: 700; letter-spacing: 0.5px; border: 1px solid; }

.section-header { display: flex; align-items: center; gap: 12px; margin: 28px 0 16px; }
.section-header h3 { font-size: 1rem; font-weight: 600; color: var(--txt); margin: 0; letter-spacing: 0.3px; }
.section-divider { flex: 1; height: 1px; background: var(--border); }

.chart-wrap { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 20px 16px 8px; }

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
.sb-val { font-family: var(--mono); font-size: 0.82rem; color: var(--accent); font-weight: 700; }

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

.stProgress > div > div { background: var(--border) !important; border-radius: 4px !important; }
.stProgress > div > div > div { background: linear-gradient(90deg, var(--accent2), var(--accent)) !important; border-radius: 4px !important; }
.stSlider [data-testid="stThumbValue"] { color: var(--accent) !important; font-family: var(--mono) !important; }
.stSlider > div > div > div > div { background: var(--accent) !important; }
.stToggle [data-testid="stToggle"] > div[data-checked="true"] { background: var(--accent) !important; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
#  THRESHOLDS & FUNÇÕES BASE
# ══════════════════════════════════════════════════════════════
if 'thresholds' not in st.session_state:
    st.session_state.thresholds = {
        "clim_fresco": 13000, "clim_maduro": 17000,
        "nclim_firme": 13000, "nclim_risco": 16000
    }
thresholds = st.session_state.thresholds

def fetch_data():
    try:
        client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
        query  = (f'from(bucket: "{INFLUX_BUCKET}") |> range(start: -1h)'
                  f' |> filter(fn: (r) => r["_measurement"] == "mqtt_consumer")'
                  f' |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")')
        df = client.query_api().query_data_frame(query)
        if isinstance(df, list): df = pd.concat(df)
        return df if isinstance(df, pd.DataFrame) and not df.empty else pd.DataFrame()
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

@st.cache_data(ttl=600)
def gerar_historico_simulado(dias: int = 90):
    random.seed(42)
    np.random.seed(42)
    now    = datetime.now()
    frutas = ["Maca", "Banana", "Laranja"]
    secoes = {"Maca":"Sec. A — Frutas Frescas", "Banana":"Sec. A — Frutas Frescas", "Laranja":"Sec. B — Citrinos"}
    lotes_base = {"Maca":"LOT-MA", "Banana":"LOT-BA", "Laranja":"LOT-LA"}
    lote_cnt   = {"Maca": 1, "Banana": 1, "Laranja": 1}

    registos = []
    for fruta in frutas:
        for dia in range(dias, 0, -1):
            data_base = now - timedelta(days=dia)
            if data_base.weekday() == 0:
                lote_cnt[fruta] += 1
            lote_id = f"{lotes_base[fruta]}-{lote_cnt[fruta]:03d}"

            for turno_h in [8, 14, 20]:
                ts = data_base.replace(hour=turno_h, minute=random.randint(0, 30), second=0, microsecond=0)
                dias_lote = (now - ts).days % 7

                if fruta in ["Maca", "Banana"]:
                    voc = max(7500, 19500 - dias_lote * 950 + np.random.normal(0, 550))
                else:
                    voc = max(8500, 18500 - dias_lote * 720 + np.random.normal(0, 480))

                temp = round(np.random.normal(4.5, 0.5), 1)
                hum  = round(np.random.normal(87, 3), 1)
                conf = round(min(0.99, max(0.72, np.random.normal(0.91, 0.05))), 2)

                estado, cor_hex, acao, sev = processar_decisao(fruta, voc)

                registos.append({
                    "timestamp":  ts, "fruta": fruta, "lote": lote_id, "secao": secoes[fruta],
                    "voc_gas": round(voc), "temp": temp, "hum": hum, "confianca": conf,
                    "estado": estado, "cor": cor_hex, "acao": acao, "severidade": sev,
                    "turno": {8:"Manhã", 14:"Tarde", 20:"Noite"}[turno_h],
                })

    return pd.DataFrame(registos).sort_values("timestamp", ascending=False).reset_index(drop=True)

PLOT_LAYOUT = dict(
    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=10, r=10, t=24, b=10),
    hovermode="x unified", font=dict(family="DM Sans", color="#8BA0BC"),
    xaxis=dict(showgrid=False, color="#5A7090", tickfont=dict(family="Space Mono", size=10)),
    yaxis=dict(gridcolor='#1E2D45', color="#5A7090", zerolinecolor='#1E2D45', tickfont=dict(family="Space Mono", size=10)),
    legend=dict(font=dict(color='#8BA0BC', family='DM Sans'), bgcolor='rgba(0,0,0,0)', orientation='h', yanchor='bottom', y=1.02)
)

# ══════════════════════════════════════════════════════════════
#  ECRÃ LOGIN (UNIFICADO COM RFID)
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

        # Lógica Condicional do Terminal
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

        st.markdown("<div class='sb-section-title'>Diagnóstico de Sistema</div>", unsafe_allow_html=True)
        st.markdown("""<div class="sb-row"><span class="sb-lbl">CPU Edge Gateway</span><span class="sb-val">24%</span></div>""", unsafe_allow_html=True)
        st.progress(24)
        st.markdown("""<div class="sb-row" style="margin-top:12px;"><span class="sb-lbl">Sinal BLE Nicla</span><span class="sb-val">85%</span></div>""", unsafe_allow_html=True)
        st.progress(85)
        st.markdown("""
            <div class="sb-row" style="margin-top:14px;"><span class="sb-lbl">InfluxDB</span><span class="sb-val" style="color:#00E5B4;">ONLINE</span></div>
            <div class="sb-row"><span class="sb-lbl">MQTT Broker</span><span class="sb-val" style="color:#00E5B4;">ACTIVE</span></div>
            <div class="sb-row"><span class="sb-lbl">BME688</span><span class="sb-val" style="color:#00E5B4;">LINKED</span></div>
        """, unsafe_allow_html=True)
        st.markdown("<div class='sb-section-title' style='margin-top:20px;'>Telemetria</div>", unsafe_allow_html=True)
        auto_refresh = st.toggle("Live Refresh (5s)", value=True)

    # ── DADOS ─────────────────────────────────────────────────
    df_live = fetch_data()
    df_hist = gerar_historico_simulado(dias=90)

    # ── PAGE HEADER ───────────────────────────────────────────
    st.markdown("""
        <div class="page-header">
            <span class="page-title">Centro de Comando Analítico</span>
            <span class="page-badge">RipeRadar OS</span>
            <span style="flex:1;"></span>
            <span class="live-chip"><span class="live-dot"></span>LIVE</span>
        </div>
    """, unsafe_allow_html=True)

    # ── TABS ──────────────────────────────────────────────────
    if st.session_state.cargo == "Chefe de Loja":
        tab_dash, tab_time, tab_admin = st.tabs(["MONITORIZAÇÃO", "ANÁLISE HISTÓRICA", "CALIBRAÇÃO"])
    else:
        tab_dash, tab_admin = st.tabs(["MONITORIZAÇÃO", "CALIBRAÇÃO"])

    # ══════════════════════════════════════════════════════════
    #  TAB 1 — MONITORIZAÇÃO EM TEMPO REAL
    # ══════════════════════════════════════════════════════════
    with tab_dash:
        if not df_live.empty and '_time' in df_live.columns:
            latest = df_live.iloc[-1]
            voc    = float(latest.get('voc_gas', 0.0))
            fruta  = str(latest.get('classe_dominante', 'Desconhecido'))
            conf   = float(latest.get('confianca', 0.0))
            temp   = float(latest.get('temp', 0.0))
            hum    = float(latest.get('hum', 0.0))
        else:
            ultimo = df_hist.iloc[0]
            voc, fruta, conf = float(ultimo["voc_gas"]), ultimo["fruta"], float(ultimo["confianca"])
            temp, hum = float(ultimo["temp"]), float(ultimo["hum"])

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
                    <div class="status-target">🎯 {fruta.upper().replace('_',' ')} &nbsp;·&nbsp; Confiança: <span style="font-family:var(--mono);font-weight:700;color:{cor_hex};">{conf_d:.1f}%</span></div>
                    <div class="status-main" style="color:{cor_hex};">{estado}</div>
                    <span class="status-action" style="color:{cor_hex};border-color:{sev_bdr[sev]};background:rgba(0,0,0,0.2);">▶ {acao}</span>
                </div>
            """, unsafe_allow_html=True)

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
            st.markdown("<div class='chart-wrap' style='padding:8px 0 0;'>", unsafe_allow_html=True)
            st.plotly_chart(fig_gauge, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

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

        if not df_live.empty and 'voc_gas' in df_live.columns:
            df_plot = df_live.dropna(subset=['voc_gas']).sort_values('_time')
            x_col, y_col = '_time', 'voc_gas'
        else:
            df_plot = df_hist[df_hist["fruta"]==fruta].sort_values("timestamp").tail(48)
            x_col, y_col = 'timestamp', 'voc_gas'

        fig_line = go.Figure()
        fig_line.add_trace(go.Scatter(
            x=df_plot[x_col], y=df_plot[y_col],
            mode='lines+markers',
            line=dict(color='#00E5B4', width=2.5, shape='spline'),
            marker=dict(size=5, color='#080C14', line=dict(width=1.5, color='#00E5B4')),
            fill='tozeroy', fillcolor='rgba(0,229,180,0.06)',
            hovertemplate='<b>%{x|%d/%m %H:%M}</b><br>%{y:.0f} Ω<extra></extra>'
        ))
        fig_line.update_layout(**PLOT_LAYOUT, height=280, yaxis_title="Ohms")
        st.markdown("<div class='chart-wrap'>", unsafe_allow_html=True)
        st.plotly_chart(fig_line, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════
    #  TAB 2 — ANÁLISE HISTÓRICA (Chefe de Loja)
    # ══════════════════════════════════════════════════════════
    if st.session_state.cargo == "Chefe de Loja":
        with tab_time:
            col_f1, col_f2, col_f3 = st.columns([1, 1, 2])
            with col_f1:
                periodo = st.selectbox("Período", ["Últimos 7 dias","Últimos 30 dias","Últimos 90 dias"], index=1)
            with col_f2:
                fruta_filtro = st.selectbox("Produto", ["Todos","Maca","Banana","Laranja"])
            with col_f3:
                sev_filtro = st.multiselect(
                    "Mostrar estados",
                    ["success","warning","danger"],
                    default=["warning","danger"],
                    format_func=lambda x: {"success":"✅ Conforme","warning":"⚠️ Atenção","danger":"🔴 Crítico"}[x]
                )

            dias_map = {"Últimos 7 dias":7,"Últimos 30 dias":30,"Últimos 90 dias":90}
            corte    = datetime.now() - timedelta(days=dias_map[periodo])

            df_periodo = df_hist[df_hist["timestamp"] >= corte].copy()
            if fruta_filtro != "Todos":
                df_periodo = df_periodo[df_periodo["fruta"] == fruta_filtro]

            df_eventos = df_periodo[df_periodo["severidade"].isin(sev_filtro)].copy() if sev_filtro else df_periodo.copy()

            st.markdown("<br>", unsafe_allow_html=True)

            total          = len(df_periodo)
            n_criticos     = len(df_periodo[df_periodo["severidade"]=="danger"])
            n_atencao      = len(df_periodo[df_periodo["severidade"]=="warning"])
            n_ok           = len(df_periodo[df_periodo["severidade"]=="success"])
            pct_ok         = round(n_ok / total * 100, 1) if total > 0 else 0
            lotes_criticos = df_periodo[df_periodo["severidade"]=="danger"]["lote"].nunique()

            st.markdown(f"""
            <div class="kpi-row">
                <div class="kpi-card"><div class="kpi-num" style="color:#E8EEF8;">{total}</div><div class="kpi-lbl">Leituras Totais</div></div>
                <div class="kpi-card"><div class="kpi-num" style="color:#FF4455;">{n_criticos}</div><div class="kpi-lbl">Alertas Críticos</div></div>
                <div class="kpi-card"><div class="kpi-num" style="color:#FFB800;">{n_atencao}</div><div class="kpi-lbl">Em Atenção</div></div>
                <div class="kpi-card"><div class="kpi-num" style="color:#00E5B4;">{pct_ok}%</div><div class="kpi-lbl">Taxa Conformidade</div></div>
                <div class="kpi-card"><div class="kpi-num" style="color:#FF4455;">{lotes_criticos}</div><div class="kpi-lbl">Lotes Rejeitados</div></div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("""<div class="section-header"><h3>Evolução da Resistência VOC por Produto</h3><div class="section-divider"></div></div>""", unsafe_allow_html=True)

            palette = {"Maca":"#00E5B4","Banana":"#FFB800","Laranja":"#FF7A45"}
            df_daily = (
                df_periodo.assign(dia=lambda d: d["timestamp"].dt.date)
                .groupby(["dia","fruta"])["voc_gas"].mean().reset_index()
            )

            fig_voc = go.Figure()
            for f_nome in df_daily["fruta"].unique():
                dd = df_daily[df_daily["fruta"]==f_nome]
                fig_voc.add_trace(go.Scatter(
                    x=dd["dia"], y=dd["voc_gas"], mode='lines', name=f_nome,
                    line=dict(color=palette.get(f_nome,"#8BA0BC"), width=2.5, shape='spline'),
                    fill='tozeroy',
                    fillcolor="rgba(0,0,0,0)",
                    hovertemplate=f'<b>%{{x}}</b><br>{f_nome}: %{{y:.0f}} Ω<extra></extra>'
                ))

            fig_voc.add_hline(y=thresholds["clim_fresco"], line_dash="dot", line_color="rgba(255,184,0,0.35)", annotation_text="Limiar Maduro", annotation_font_color="#FFB800", annotation_font_size=10)
            fig_voc.add_hline(y=thresholds["clim_maduro"]*0.76, line_dash="dot", line_color="rgba(255,68,85,0.35)", annotation_text="Limiar Crítico", annotation_font_color="#FF4455", annotation_font_size=10)

            layout_voc = {**PLOT_LAYOUT, "height": 300, "yaxis_title": "Resistência (Ω)"}
            fig_voc.update_layout(**layout_voc)
            st.markdown("<div class='chart-wrap'>", unsafe_allow_html=True)
            st.plotly_chart(fig_voc, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            col_g2, col_g3 = st.columns([3, 2])

            with col_g2:
                st.markdown("""<div class="section-header"><h3>Alertas por Semana</h3><div class="section-divider"></div></div>""", unsafe_allow_html=True)

                df_sev_week = (
                    df_periodo
                    .assign(semana=lambda d: d["timestamp"].dt.to_period("W").apply(lambda p: str(p.start_time.date())))
                    .groupby(["semana","severidade"]).size().reset_index(name="n")
                )
                sev_colors = {"success":"#00E5B4","warning":"#FFB800","danger":"#FF4455"}
                sev_labels = {"success":"Conforme","warning":"Atenção","danger":"Crítico"}

                fig_bar = go.Figure()
                for s in ["success","warning","danger"]:
                    dd = df_sev_week[df_sev_week["severidade"]==s]
                    if not dd.empty:
                        fig_bar.add_trace(go.Bar(
                            x=dd["semana"], y=dd["n"], name=sev_labels[s],
                            marker_color=sev_colors[s], opacity=0.85,
                            hovertemplate='%{x}<br>' + sev_labels[s] + ': %{y}<extra></extra>'
                        ))
                layout_bar = {**PLOT_LAYOUT, "height":280, "barmode":"stack", "xaxis": {**PLOT_LAYOUT["xaxis"], "tickangle":-30}}
                fig_bar.update_layout(**layout_bar)
                st.markdown("<div class='chart-wrap'>", unsafe_allow_html=True)
                st.plotly_chart(fig_bar, use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)

            with col_g3:
                st.markdown("""<div class="section-header"><h3>Alertas por Produto</h3><div class="section-divider"></div></div>""", unsafe_allow_html=True)

                df_pie = (
                    df_periodo[df_periodo["severidade"].isin(["warning","danger"])]
                    .groupby("fruta").size().reset_index(name="n")
                )
                fig_pie = go.Figure(go.Pie(
                    labels=df_pie["fruta"], values=df_pie["n"], hole=0.6,
                    marker=dict(colors=["#00E5B4","#FFB800","#FF7A45"], line=dict(color="#080C14",width=2)),
                    textfont=dict(family='DM Sans', size=12, color='#E8EEF8'),
                    hovertemplate='<b>%{label}</b><br>%{value} alertas (%{percent})<extra></extra>'
                ))
                fig_pie.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)', margin=dict(l=10,r=10,t=24,b=10), height=280,
                    legend=dict(font=dict(color='#8BA0BC',family='DM Sans'),bgcolor='rgba(0,0,0,0)'),
                    annotations=[dict(text='Alertas', x=0.5, y=0.5, font_size=12, showarrow=False, font_color='#5A7090', font_family='Space Mono')]
                )
                st.markdown("<div class='chart-wrap'>", unsafe_allow_html=True)
                st.plotly_chart(fig_pie, use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("""<div class="section-header"><h3>Registo de Eventos de Qualidade</h3><div class="section-divider"></div></div>""", unsafe_allow_html=True)
            st.markdown("""
                <p style='font-size:0.85rem;color:var(--txt-muted);margin-bottom:20px;'>
                Eventos agrupados por <strong style='color:var(--txt-sub);'>dia e lote</strong>.
                Cada entrada representa um ciclo de monitorização completo (turnos Manhã/Tarde/Noite).
                </p>
            """, unsafe_allow_html=True)

            df_tl = df_eventos[df_eventos["severidade"].isin(["warning","danger"])].copy()

            if df_tl.empty:
                st.info("✅ Sem eventos de alerta para os filtros selecionados.")
            else:
                df_tl["dia_str"]  = df_tl["timestamp"].dt.strftime("%A, %d de %B de %Y")
                df_tl["dia_date"] = df_tl["timestamp"].dt.date
                dias_unicos = df_tl["dia_date"].drop_duplicates().sort_values(ascending=False).head(14)

                st.markdown('<div class="tl-wrap">', unsafe_allow_html=True)
                for dia_date in dias_unicos:
                    grupo_dia = df_tl[df_tl["dia_date"] == dia_date]
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
                                <span style="font-weight:700;color:{cor_dia};">{len(grupo_dia)} eventos</span>
                                {badge_html}
                            </div>
                    """, unsafe_allow_html=True)

                    for lote_id, g_lote in grupo_dia.groupby("lote"):
                        g_lote   = g_lote.sort_values("timestamp")
                        pior     = g_lote.sort_values("voc_gas").iloc[0]
                        turnos   = " · ".join(g_lote["turno"].unique())
                        voc_med  = g_lote["voc_gas"].mean()
                        temp_med = g_lote["temp"].mean()
                        cor_ev   = pior["cor"]
                        trend    = "↘ A degradar" if g_lote["voc_gas"].iloc[-1] < g_lote["voc_gas"].iloc[0] else "↗ Estável"
                        trend_c  = "#FF4455" if "degradar" in trend else "#00E5B4"

                        st.markdown(f"""
                        <div style="background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:14px 16px;margin-bottom:10px;">
                            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
                                <div>
                                    <span style="font-family:var(--mono);font-size:0.68rem;color:var(--txt-muted);">LOTE&nbsp;</span>
                                    <span style="font-family:var(--mono);font-size:0.82rem;color:var(--txt);font-weight:700;">{lote_id}</span>
                                    &nbsp;&nbsp;
                                    <span style="font-size:0.8rem;color:var(--txt-sub);">{pior['secao']}</span>
                                </div>
                                <span style="font-family:var(--mono);font-size:0.72rem;color:{trend_c};">{trend}</span>
                            </div>
                            <div style="display:flex;gap:12px;align-items:center;margin-bottom:8px;flex-wrap:wrap;">
                                <span style="font-weight:700;color:{cor_ev};font-size:0.95rem;">{pior['estado']}</span>
                                <span style="font-size:0.82rem;color:var(--txt-sub);">📦 {pior['fruta']}</span>
                                <span style="font-size:0.78rem;color:var(--txt-muted);">Turnos: {turnos}</span>
                            </div>
                            <div style="display:flex;gap:20px;font-size:0.82rem;color:var(--txt-muted);flex-wrap:wrap;">
                                <span>VOC médio: <span style="font-family:var(--mono);color:var(--txt);">{voc_med/1000:.2f} kΩ</span></span>
                                <span>Temp: <span style="font-family:var(--mono);color:var(--txt);">{temp_med:.1f} °C</span></span>
                                <span>Ação: <strong style="color:{cor_ev};">{pior['acao']}</strong></span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                    st.markdown("</div></div>", unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════
    #  TAB 3 — CALIBRAÇÃO E HARDWARE ADMIN
    # ══════════════════════════════════════════════════════════
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
                clim_f = st.slider("Verde → Maduro",  10000, 15000, thresholds["clim_fresco"])
                clim_m = st.slider("Maduro → Podre",  15000, 20000, thresholds["clim_maduro"])
            with col_b:
                st.markdown("<div class='calib-group-title'>🍊 Fenologia Não-Climatérica (Laranja)</div>", unsafe_allow_html=True)
                nclim_f = st.slider("Firme → Risco",     10000, 14000, thresholds["nclim_firme"])
                nclim_r = st.slider("Risco → Degradada", 14000, 18000, thresholds["nclim_risco"])
            st.markdown("<br>", unsafe_allow_html=True)
            submitted = st.form_submit_button("Aplicar Parâmetros →", use_container_width=True, type="primary")
            if submitted:
                st.session_state.thresholds = {
                    "clim_fresco": clim_f, "clim_maduro": clim_m,
                    "nclim_firme": nclim_f, "nclim_risco": nclim_r
                }
                st.cache_data.clear()
                st.success("✓ Parâmetros aplicados. Histórico recalculado.")
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        
        # Secção de Administração de Hardware (Apenas Chefes)
        if st.session_state.cargo == "Chefe de Loja":
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("<div class='calib-card'>", unsafe_allow_html=True)
            st.markdown("""
                <div class="calib-title">Configuração de Hardware RFID</div>
                <div class="calib-sub">Usa esta zona para autorizar este computador a escutar o Leitor RFID (EDGE Gateway).</div>
            """, unsafe_allow_html=True)
            
            if not is_terminal:
                if st.button("💻 Registar este PC como Terminal RFID Seguro"):
                    cookie_manager.set("terminal_loja", "true", max_age=31536000, key="set_term")
                    st.success("✅ PC registado! Faz Logout para testar a entrada por cartão.")
            else:
                st.info("✅ Este computador está atualmente configurado e autorizado como Terminal RFID.")
                if st.button("❌ Remover Registo RFID deste PC"):
                    cookie_manager.delete("terminal_loja", key="del_term")
                    st.warning("⚠️ Registo removido. O login passará a ser obrigatoriamente manual.")
            st.markdown("</div>", unsafe_allow_html=True)

    # ── AUTO REFRESH DASHBOARD ─────────────────────────────────
    if auto_refresh:
        time.sleep(5)
        st.rerun()
