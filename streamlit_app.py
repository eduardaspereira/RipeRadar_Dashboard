import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from influxdb_client import InfluxDBClient
from datetime import datetime, timezone
import time

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="RipeRadar OS | Edge AI", page_icon="🍎", layout="wide", initial_sidebar_state="collapsed")

# --- CSS ACADÉMICO & GEOMÉTRICO ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Inter:wght@300;400;600&family=Roboto+Mono:wght@400;700&display=swap');
    
    .stApp { 
        background: radial-gradient(circle at 50% 0%, #1e213a 0%, #0a0b10 80%); 
        color: #e0e0e0;
        background-image: linear-gradient(rgba(0, 210, 255, 0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(0, 210, 255, 0.03) 1px, transparent 1px);
        background-size: 40px 40px;
    }
    
    h1, h2, h3 { font-family: 'Orbitron', sans-serif; }
    p, span, div { font-family: 'Inter', sans-serif; }
    .mono-text { font-family: 'Roboto Mono', monospace; color: #00d2ff; }
    
    div[data-testid="metric-container"] {
        background: rgba(15, 20, 35, 0.6);
        border-radius: 12px; padding: 20px; 
        border: 1px solid rgba(0, 210, 255, 0.1);
        border-left: 4px solid #00d2ff;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.4); 
        backdrop-filter: blur(12px);
    }
    div[data-testid="stMetricValue"] { font-family: 'Orbitron', sans-serif; font-size: 2.2rem; color: #ffffff; }
    div[data-testid="stMetricLabel"] { color: #8a92a6; font-weight: 600; letter-spacing: 1px; font-size: 0.85rem; }

    .action-card {
        padding: 35px; border-radius: 15px; text-align: center; margin-bottom: 30px;
        border: 1px solid; box-shadow: 0 0 40px rgba(0,0,0,0.8) inset, 0 15px 35px rgba(0,0,0,0.6);
        background: linear-gradient(135deg, rgba(20,25,40,0.8) 0%, rgba(10,12,20,0.9) 100%);
    }
    
    .stTabs [data-baseweb="tab-list"] { gap: 15px; border-bottom: 1px solid rgba(255,255,255,0.05); }
    .stTabs [data-baseweb="tab"] { padding: 12px 25px; font-family: 'Orbitron', sans-serif; color: #8a92a6; }
    .stTabs [aria-selected="true"] { border-bottom: 3px solid #00d2ff !important; color: #ffffff !important; }

    .status-pill {
        display: inline-flex; align-items: center; padding: 6px 14px; border-radius: 4px;
        font-family: 'Roboto Mono', monospace; font-size: 0.75rem; font-weight: 700; margin-right: 12px;
        background: rgba(0,0,0,0.6); border: 1px solid;
    }
    .live-dot { height: 8px; width: 8px; border-radius: 50%; display: inline-block; margin-right: 8px; }
    .blink { animation: blinker 1.5s cubic-bezier(0.4, 0, 0.6, 1) infinite; }
    @keyframes blinker { 50% { opacity: 0.1; } }
    
    /* Paper Styling */
    .paper-box { background: #fdfdfd; color: #111; padding: 50px; border-radius: 8px; font-family: "Times New Roman", serif; }
    .paper-title { font-size: 24px; text-align: center; font-weight: bold; margin-bottom: 5px; }
    .paper-authors { text-align: center; font-style: italic; margin-bottom: 20px; font-size: 16px; }
    .paper-abstract-title { font-weight: bold; text-align: center; text-transform: uppercase; font-size: 14px; margin-bottom: 10px; }
    .paper-text { text-align: justify; line-height: 1.6; font-size: 15px; }
    </style>
    """, unsafe_allow_html=True)

# --- CREDENCIAIS ---
try:
    INFLUX_URL = st.secrets["INFLUX_URL"]
    INFLUX_TOKEN = st.secrets["INFLUX_TOKEN"]
    INFLUX_ORG = st.secrets["INFLUX_ORG"]
    INFLUX_BUCKET = st.secrets["INFLUX_BUCKET"]
except Exception:
    st.error("⚠️ Configura os Secrets no Streamlit Cloud primeiro!")
    st.stop()

# --- ESTADO PERSISTENTE (THRESHOLDS) ---
# Em vez de session_state que reseta no rerun local, usamos uma cache persistente
@st.cache_data
def get_thresholds():
    return {
        "clim_fresco": 13000, "clim_maduro": 17000, 
        "nclim_firme": 13000, "nclim_risco": 16000,
        "camera_mode": "Mock (Simulação)"
    }

thresholds = get_thresholds()

# --- INFLUXDB FETCH ---
def fetch_data():
    client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    query = f"""
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: -10m)
      |> filter(fn: (r) => r["_measurement"] == "mqtt_consumer")
      |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
    """
    try:
        df = client.query_api().query_data_frame(query)
        if isinstance(df, list): df = pd.concat(df)
        return df if isinstance(df, pd.DataFrame) and not df.empty else pd.DataFrame()
    except: return pd.DataFrame()

def processar_decisao(classe, voc):
    if any(f in str(classe).lower() for f in ["maca", "apple", "banana"]):
        if voc < thresholds["clim_fresco"]: return "VERDE / FRESCO", "#00ffcc", "ESTADO: PRATELEIRA"
        elif voc <= thresholds["clim_maduro"]: return "MADURO / ÓTIMO", "#ffcc00", "ESTADO: PROMOÇÃO IMEDIATA"
        else: return "PODRE / SENESCÊNCIA", "#ff4b4b", "ESTADO: RETIRAR DE IMEDIATO"
    else: 
        if voc < thresholds["nclim_firme"]: return "FIRME / BOA", "#00ffcc", "ESTADO: CONFORME"
        elif voc <= thresholds["nclim_risco"]: return "RISCO DE DEGRADAÇÃO", "#ff9900", "ESTADO: VIGILÂNCIA REFORÇADA"
        else: return "DEGRADADA", "#ff4b4b", "ESTADO: REJEITAR LOTE"

df = fetch_data()

# --- HEARTBEAT ---
nicla_status = "OFFLINE"; nicla_color = "#ff4b4b"; nicla_class = ""
if not df.empty and '_time' in df.columns:
    last_time = df.iloc[-1]['_time']
    segundos = (datetime.now(timezone.utc) - last_time).total_seconds()
    if segundos < 20: nicla_status = "ONLINE (BLE)"; nicla_color = "#00ffcc"; nicla_class = "blink"
    elif segundos < 120: nicla_status = "LATÊNCIA ALTA"; nicla_color = "#ffcc00"

if thresholds["camera_mode"] == "Real OV7675": cam_color = "#00ffcc"; cam_status = "ONLINE (OV7675)"; cam_class = "blink"
elif thresholds["camera_mode"] == "Mock (Simulação)": cam_color = "#ffcc00"; cam_status = "MOCK SIMULATOR"; cam_class = "blink"
else: cam_color = "#ff4b4b"; cam_status = "DESCONECTADA"; cam_class = ""

# --- CABEÇALHO ---
col_logo, col_title = st.columns([1, 9])
with col_logo: st.markdown("<h1 style='font-size: 3.5rem;'>🍏</h1>", unsafe_allow_html=True)
with col_title:
    st.markdown("<h1>RipeRadar <span style='color: #00d2ff;'>Multi-Modal Edge Fusion</span></h1>", unsafe_allow_html=True)
    st.markdown(f"""
        <div style="margin-top: -10px;">
            <div class="status-pill" style="border-color: {nicla_color}; color: {nicla_color};"><span class="live-dot {nicla_class}" style="background-color: {nicla_color};"></span> NODE 1 (SENSE): {nicla_status}</div>
            <div class="status-pill" style="border-color: {cam_color}; color: {cam_color};"><span class="live-dot {cam_class}" style="background-color: {cam_color};"></span> NODE 2 (VISION): {cam_status}</div>
            <div class="status-pill" style="border-color: #00d2ff; color: #00d2ff;"><span class="live-dot blink" style="background-color: #00d2ff;"></span> GATEWAY: INFLUXDB</div>
        </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# --- ABAS ---
tab_dash, tab_admin, tab_paper = st.tabs(["📊 DASHBOARD TELEMETRIA", "⚙️ CALIBRAÇÃO DE FUSÃO", "📄 PUBLICAÇÃO CIENTÍFICA"])

with tab_dash:
    if not df.empty and nicla_status != "OFFLINE":
        latest = df.iloc[-1]
        voc = float(latest['voc_gas']) if 'voc_gas' in latest else 0.0
        fruta = str(latest['classe_dominante']) if 'classe_dominante' in latest else 'Desconhecido'
        conf = float(latest['confianca']) if 'confianca' in latest else 0.0
        temp = float(latest['temp']) if 'temp' in latest else 0.0
        hum = float(latest['hum']) if 'hum' in latest else 0.0
        hpa = float(latest['hPa']) if 'hPa' in latest else 0.0
        
        estado, cor, acao = processar_decisao(fruta, voc)

        st.markdown(f"""
            <div class="action-card" style="border-color: {cor}44;">
                <p class="mono-text" style="margin-bottom: 5px; font-size: 0.9rem;">ALGORITMO DE FUSÃO (VISION + OLFACTION)</p>
                <h3 style="color: #a0a5b5;">TINYML CLASSIFICATION: <span style="color: white; border-bottom: 2px solid #00d2ff;">{fruta.upper().replace('_', ' ')}</span></h3>
                <h1 style="color: {cor}; font-size: 4rem; margin: 5px 0;">{estado}</h1>
                <h3 style="color: #ffffff; font-weight: 400;">{acao}</h3>
            </div>
            """, unsafe_allow_html=True)

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("ÍNDICE VOC", f"{voc/1000:.1f} kΩ")
        c2.metric("CONFIANÇA (IA)", f"{conf:.1f}%")
        c3.metric("TEMPERATURA", f"{temp:.1f} ºC")
        c4.metric("HUMIDADE", f"{hum:.1f}%")
        c5.metric("PRESSÃO ATM.", f"{hpa:.1f} hPa")

        st.markdown("<br>", unsafe_allow_html=True)
        col_l, col_r = st.columns([1.5, 1])
        
        with col_l:
            st.markdown("<h3 style='font-size: 1.2rem; color: #ffffff;'>📈 Análise de Senescência (VOC)</h3>", unsafe_allow_html=True)
            if 'voc_gas' in df.columns:
                df_clean = df.dropna(subset=['voc_gas'])
                fig_voc = px.line(df_clean, x='_time', y='voc_gas', template="plotly_dark", color_discrete_sequence=[cor])
                fig_voc.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=0,r=0,t=10,b=0))
                st.plotly_chart(fig_voc, use_container_width=True)

        with col_r:
            st.markdown("<h3 style='font-size: 1.2rem; color: #ffffff;'>🕸️ Assinatura Ambiental</h3>", unsafe_allow_html=True)
            radar_data = pd.DataFrame(dict(
                r=[temp * 3, hum, (hpa - 900) if hpa > 900 else 0, (voc / 200) if voc > 0 else 0, conf],
                theta=['Temp (Norm)', 'Hum (%)', 'Pressão (Rel)', 'VOC (Norm)', 'IA Conf (%)']
            ))
            fig_radar = px.line_polar(radar_data, r='r', theta='theta', line_close=True, template="plotly_dark")
            fig_radar.update_traces(fill='toself', fillcolor='rgba(0, 210, 255, 0.2)', line_color='#00d2ff')
            fig_radar.update_layout(
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                polar=dict(bgcolor='rgba(0,0,0,0)', radialaxis=dict(visible=False, showticklabels=False), angularaxis=dict(color="#a0a5b5", tickfont=dict(family="Inter", size=11))),
                margin=dict(l=40, r=40, t=20, b=20)
            )
            st.plotly_chart(fig_radar, use_container_width=True)
    else:
        st.error("⚠️ A aguardar telemetria da Edge Gateway.")

with tab_admin:
    st.header("⚙️ Calibração de Limiares")
    
    with st.form("calibration_form"):
        st.markdown("### Configuração do Sensor Ótico")
        novo_modo = st.radio("Câmara:", ["Real OV7675", "Mock (Simulação)", "Desconectada"], index=["Real OV7675", "Mock (Simulação)", "Desconectada"].index(thresholds["camera_mode"]))
        
        st.divider()
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("### 🍌 Frutos Climatéricos")
            clim_f = st.slider("Verde ➡️ Maduro (VOC Ω)", 10000, 15000, thresholds["clim_fresco"])
            clim_m = st.slider("Maduro ➡️ Podre (VOC Ω)", 15000, 20000, thresholds["clim_maduro"])
        with col_b:
            st.markdown("### 🍊 Não-Climatéricos")
            nclim_f = st.slider("Firme ➡️ Risco (VOC Ω)", 10000, 14000, thresholds["nclim_firme"])
            nclim_r = st.slider("Risco ➡️ Degradada (VOC Ω)", 14000, 18000, thresholds["nclim_risco"])
            
        submitted = st.form_submit_button("Guardar Calibração")
        if submitted:
            # Atualiza a cache com os novos valores. Não os perde no rerun!
            get_thresholds.clear()
            def get_thresholds(): return {"clim_fresco": clim_f, "clim_maduro": clim_m, "nclim_firme": nclim_f, "nclim_risco": nclim_r, "camera_mode": novo_modo}
            thresholds = get_thresholds()
            st.success("Configurações atualizadas!")

with tab_paper:
    st.markdown("""
        <div class="paper-box">
            <div class="paper-title">RipeRadar: Multimodal Edge Fusion for Real-Time Fruit Spoilage Detection</div>
            <div class="paper-authors">Eduarda Pereira, Gonçalo Ferreira, Gonçalo Magalhães<br>
            Department of Informatics, University of Minho, Braga, Portugal</div>
            
            <div class="paper-abstract-title">Abstract</div>
            <p class="paper-text">
                A degradação da qualidade hortofrutícola durante a cadeia de abastecimento e no retalho representa um desafio logístico e económico significativo, contribuindo para elevados índices de desperdício alimentar. Para superar as limitações de infraestruturas centralizadas, propomos o <b>RipeRadar</b>, uma arquitetura <i>Internet of Things (IoT)</i> descentralizada para monitorização multimodal.
            </p>
            <p class="paper-text">
                O RipeRadar transpõe o processamento analítico para a <i>Edge</i> da rede através de modelos <i>Tiny Machine Learning (TinyML)</i> executados diretamente em microcontroladores. A inovação central reside numa estratégia de <b>Late Fusion</b> (Decision-Level Fusion) que correlaciona inferências visuais de uma rede neuronal (via OV7675 no Arduino Nano 33 BLE) com leituras contínuas de compostos orgânicos voláteis (VOCs) extraídas do sensor BME688 (Arduino Nicla Sense ME).
            </p>
            <p class="paper-text">
                A orquestração assíncrona é mediada via Bluetooth Low Energy (BLE) por um <i>Edge Gateway</i> (Raspberry Pi 5), culminando nesta plataforma analítica baseada em InfluxDB. Este ecossistema garante autonomia operacional, latência residual e mitigação de falsos positivos face a ambiguidades visuais no retalho inteligente.
            </p>
            
            <hr style="margin: 30px 0; border: 1px solid #ccc;">
            
            <h3 style="font-size: 18px; margin-bottom: 10px;">System Architecture</h3>
            <ul style="font-size: 15px; line-height: 1.6; text-align: justify;">
                <li><b>Camada de Perceção (Periphery):</b> Arduino Nano 33 BLE (Visão / CNN) e Arduino Nicla Sense ME (Olfação Digital / BME688).</li>
                <li><b>Camada de Comunicação:</b> Bluetooth Low Energy (BLE) para aquisição de dados do sensor olfativo.</li>
                <li><b>Camada de Processamento (Edge Gateway):</b> Raspberry Pi 5 atuando como agregador e ponte para a Cloud.</li>
                <li><b>Camada de Aplicação:</b> Base de dados temporal (InfluxDB) e interface analítica em tempo real (Streamlit).</li>
            </ul>
        </div>
    """, unsafe_allow_html=True)

# Loop de refresh que não quebra formulários
time.sleep(5)
st.rerun()