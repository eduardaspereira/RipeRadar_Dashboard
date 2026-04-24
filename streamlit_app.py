import streamlit as st
import paho.mqtt.client as mqtt
import json
import pandas as pd
import plotly.express as px
from datetime import datetime
import time

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="RipeRadar OS v2.6", page_icon="🍎", layout="wide")

# --- CSS FUTURISTA (GLASSMORPHISM & INDUSTRIAL DESIGN) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Inter:wght@300;500;700&display=swap');
    
    .main { background: linear-gradient(135deg, #0f0c29, #1b1b2f, #16213e); color: white; }
    
    /* Cartões Glassmorphism */
    div[data-testid="stMetric"] {
        background: rgba(255, 255, 255, 0.03);
        border-radius: 12px;
        padding: 15px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(10px);
    }

    h1, h2, h3 { font-family: 'Orbitron', sans-serif; text-shadow: 0 0 8px rgba(0,210,255,0.4); }
    
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        background-color: rgba(255, 255, 255, 0.05);
        border-radius: 5px;
        color: white;
        padding: 10px 20px;
    }
    
    .action-card {
        padding: 25px;
        border-radius: 15px;
        text-align: center;
        margin-bottom: 20px;
        border: 2px solid;
        box-shadow: 0 0 20px rgba(0,0,0,0.5);
    }
    </style>
    """, unsafe_allow_html=True)

# --- INICIALIZAÇÃO DE ESTADO (THRESHOLDS DO PDF) ---
if 'thresholds' not in st.session_state:
    st.session_state.thresholds = {
        "clim_fresco": 300,      # Banana/Maçã
        "clim_maduro": 700,      # Banana/Maçã
        "nclim_firme": 150,      # Laranja
        "nclim_risco": 400       # Laranja
    }

if 'historico' not in st.session_state:
    st.session_state.historico = []

# --- LÓGICA MQTT (OTIMIZADA PARA CLOUD) ---
MQTT_BROKER = "04f11400208444d287dcce716d5d4823.s1.eu.hivemq.cloud"
MQTT_PORT = 8883
MQTT_TOPIC = "riperadar/telemetry"

# Uso de Secrets para segurança no GitHub. 
# Se testares localmente sem secrets configurados, ele usa os valores de fallback
MQTT_USER = st.secrets.get("MQTT_USER", "dashboard_user")
MQTT_PASS = st.secrets.get("MQTT_PASS", "SUBSTITUI_AQUI_PELA_TUA_PASS")

@st.cache_resource
def get_mqtt_manager():
    return {"client": None, "buffer": []}

mqtt_manager = get_mqtt_manager()

def on_message(client, userdata, message):
    try:
        payload = json.loads(message.payload.decode("utf-8"))
        payload['received_at'] = datetime.now()
        mqtt_manager["buffer"].append(payload)
    except: pass

# Inicialização limpa e única do cliente
if mqtt_manager["client"] is None:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_message = on_message
    
    # Segurança TLS exigida pelo HiveMQ
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.tls_set() 
    
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.subscribe(MQTT_TOPIC)
        client.loop_start()
        mqtt_manager["client"] = client
    except Exception as e:
        st.error(f"Erro ao ligar ao HiveMQ Cloud: {e}")

# Esvaziar buffer para o histórico local
while mqtt_manager["buffer"]:
    st.session_state.historico.append(mqtt_manager["buffer"].pop(0))
    if len(st.session_state.historico) > 50: st.session_state.historico.pop(0)

# --- FUNÇÃO DE DECISÃO (LATE FUSION) ---
def processar_decisao(classe, voc):
    if any(f in classe.lower() for f in ["maca", "apple", "banana"]):
        if voc < st.session_state.thresholds["clim_fresco"]:
            return "VERDE / FRESCO", "#00ffcc", "MANTER EM PRATELEIRA"
        elif voc <= st.session_state.thresholds["clim_maduro"]:
            return "MADURO / ÓTIMO", "#ffcc00", "PROMOÇÃO (VENDA RÁPIDA)"
        else:
            return "PODRE / SENESCÊNCIA", "#ff4b4b", "RETIRAR IMEDIATAMENTE"
    else: 
        if voc < st.session_state.thresholds["nclim_firme"]:
            return "FIRME / BOA", "#00ffcc", "CONFORME"
        elif voc <= st.session_state.thresholds["nclim_risco"]:
            return "RISCO DE DEGRADAÇÃO", "#ff9900", "VIGILÂNCIA REFORÇADA"
        else:
            return "DEGRADADA", "#ff4b4b", "REJEITAR LOTE"

# --- INTERFACE POR ABAS ---
tab_dash, tab_admin = st.tabs(["📊 DASHBOARD OPERACIONAL", "⚙️ CONFIGURAÇÕES ADMIN"])

with tab_dash:
    if st.session_state.historico:
        df = pd.json_normalize(st.session_state.historico)
        latest = st.session_state.historico[-1]
        
        env = latest.get('environment', {})
        dec = latest.get('final_decision', {})
        voc = env.get('gas_resistance_ohms', 0)
        fruta = dec.get('class', 'Desconhecido')
        
        estado, cor, acao = processar_decisao(fruta, voc)

        # 1. CARD DE AÇÃO 
        st.markdown(f"""
            <div class="action-card" style="background: rgba({ '255, 75, 75' if cor == "#ff4b4b" else '0, 255, 204' if cor == "#00ffcc" else '255, 204, 0' }, 0.1); border-color: {cor};">
                <h3 style="color: white; margin:0;">DETETADO: {fruta.upper().replace('_', ' ')}</h3>
                <h1 style="color: {cor}; font-size: 3.5rem; margin: 10px 0;">{estado}</h1>
                <h2 style="color: white; letter-spacing: 2px;">{acao}</h2>
            </div>
            """, unsafe_allow_html=True)

        # 2. MÉTRICAS RÁPIDAS
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("ÍNDICE VOC", f"{voc:.0f} Ω")
        c2.metric("CONFIANÇA FUSÃO", f"{dec.get('confidence', 0)}%")
        c3.metric("TEMP. AMBIENTE", f"{env.get('temperature_c', 0)} ºC")
        c4.metric("HUMIDADE", f"{env.get('humidity_percent', 0)}%")

        st.divider()

        # 3. GRÁFICOS
        col_l, col_r = st.columns(2)
        with col_l:
            st.subheader("📈 Tendência Olfativa (VOC)")
            fig_voc = px.line(df, x='received_at', y='environment.gas_resistance_ohms', template="plotly_dark", color_discrete_sequence=[cor])
            fig_voc.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=0,r=0,t=20,b=0))
            st.plotly_chart(fig_voc, width="stretch")

        with col_r:
            st.subheader("🧠 Estabilidade Vision (TinyML)")
            fig_conf = px.area(df, x='received_at', y='final_decision.confidence', template="plotly_dark", color_discrete_sequence=["#00d2ff"])
            fig_conf.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=0,r=0,t=20,b=0))
            st.plotly_chart(fig_conf, width="stretch")

    else:
        st.warning("🔭 À procura de sinal da Edge Gateway... Garante que o Mosquitto e o simulador estão ativos.")

with tab_admin:
    st.header("🛠️ Ajuste de Thresholds (Late Fusion)")
    st.info("Estes valores substituem as definições base da literatura para calibração local.")
    
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.subheader("🍌 Frutos Climatéricos")
        st.session_state.thresholds["clim_fresco"] = st.slider("Limite Verde -> Maduro (VOC)", 100, 500, st.session_state.thresholds["clim_fresco"])
        st.session_state.thresholds["clim_maduro"] = st.slider("Limite Maduro -> Podre (VOC)", 500, 1500, st.session_state.thresholds["clim_maduro"])
    
    with col_b:
        st.subheader("🍊 Frutos Não-Climatéricos")
        st.session_state.thresholds["nclim_firme"] = st.slider("Limite Firme -> Risco (VOC)", 50, 300, st.session_state.thresholds["nclim_firme"])
        st.session_state.thresholds["nclim_risco"] = st.slider("Limite Risco -> Degradada (VOC)", 300, 1000, st.session_state.thresholds["nclim_risco"])
    
    if st.button("♻️ REPOR VALORES DO ARTIGO (UMinho)"):
        st.session_state.thresholds = {"clim_fresco": 300, "clim_maduro": 700, "nclim_firme": 150, "nclim_risco": 400}
        st.rerun()

# --- FOOTER ---
st.markdown("---")
st.caption("RipeRadar v2.6 | Universidade do Minho | Laboratório de IoT & Edge Computing")

time.sleep(2.5)
st.rerun()