import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from influxdb_client import InfluxDBClient
from datetime import datetime, timezone
import time

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="RipeRadar OS | Edge AI", page_icon="🍎", layout="wide", initial_sidebar_state="collapsed")

# --- CSS ACADÉMICO & GEOMÉTRICO (GLASSMORPHISM) ---
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
    
    /* Cartões Glassmorphism */
    div[data-testid="metric-container"] {
        background: rgba(15, 20, 35, 0.6);
        border-radius: 12px; padding: 20px; 
        border: 1px solid rgba(0, 210, 255, 0.1);
        border-left: 4px solid #00d2ff;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.4); 
        backdrop-filter: blur(12px);
        transition: all 0.3s ease;
    }
    div[data-testid="metric-container"]:hover {
        transform: translateY(-5px); 
        box-shadow: 0 12px 40px 0 rgba(0, 210, 255, 0.2); 
        border: 1px solid rgba(0, 210, 255, 0.4);
        border-left: 4px solid #00ffcc;
    }
    
    div[data-testid="stMetricValue"] { font-family: 'Orbitron', sans-serif; font-size: 2.2rem; color: #ffffff; text-shadow: 0 0 10px rgba(255,255,255,0.2); }
    div[data-testid="stMetricLabel"] { color: #8a92a6; font-weight: 600; letter-spacing: 1.5px; font-size: 0.85rem; text-transform: uppercase; }

    /* Cartão Central (Fusão) */
    .action-card {
        padding: 35px; border-radius: 15px; text-align: center; margin-bottom: 30px;
        border: 1px solid; box-shadow: 0 0 40px rgba(0,0,0,0.8) inset, 0 15px 35px rgba(0,0,0,0.6);
        background: linear-gradient(135deg, rgba(20,25,40,0.8) 0%, rgba(10,12,20,0.9) 100%);
        backdrop-filter: blur(15px);
    }
    
    /* Estilo das Abas Académicas */
    .stTabs [data-baseweb="tab-list"] { gap: 15px; background-color: transparent; border-bottom: 1px solid rgba(255,255,255,0.05); }
    .stTabs [data-baseweb="tab"] {
        background-color: transparent; border-radius: 0; border-bottom: 3px solid transparent; padding: 12px 25px;
        font-family: 'Orbitron', sans-serif; letter-spacing: 1px; color: #8a92a6;
    }
    .stTabs [aria-selected="true"] {
        background-color: rgba(0, 210, 255, 0.05) !important; border-bottom: 3px solid #00d2ff !important; color: #ffffff !important;
        text-shadow: 0 0 10px rgba(0, 210, 255, 0.4);
    }

    /* Status Pills */
    .status-pill {
        display: inline-flex; align-items: center; padding: 6px 14px; border-radius: 4px;
        font-family: 'Roboto Mono', monospace; font-size: 0.75rem; font-weight: 700; letter-spacing: 1px; margin-right: 12px;
        background: rgba(0,0,0,0.6); border: 1px solid; backdrop-filter: blur(5px);
    }
    .live-dot { height: 8px; width: 8px; border-radius: 50%; display: inline-block; margin-right: 8px; }
    .blink { animation: blinker 1.5s cubic-bezier(0.4, 0, 0.6, 1) infinite; }
    @keyframes blinker { 50% { opacity: 0.1; } }
    
    /* Paper Abstract Container */
    .paper-container {
        background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.1);
        padding: 40px; border-radius: 10px; margin-top: 20px;
    }
    .paper-title { font-size: 2rem; color: #ffffff; text-align: center; margin-bottom: 10px; }
    .paper-authors { text-align: center; color: #00d2ff; font-family: 'Inter', sans-serif; margin-bottom: 30px; font-size: 1.1rem; }
    .paper-affiliation { text-align: center; color: #8a92a6; font-size: 0.9rem; margin-top: -25px; margin-bottom: 40px; }
    .paper-abstract { font-family: 'Inter', serif; line-height: 1.8; color: #d0d0d0; text-align: justify; }
    
    .block-container { padding-bottom: 90px; }
    </style>
    """, unsafe_allow_html=True)

# --- CREDENCIAIS SEGURAS ---
try:
    INFLUX_URL = st.secrets["INFLUX_URL"]
    INFLUX_TOKEN = st.secrets["INFLUX_TOKEN"]
    INFLUX_ORG = st.secrets["INFLUX_ORG"]
    INFLUX_BUCKET = st.secrets["INFLUX_BUCKET"]
except Exception:
    st.error("⚠️ Configura os Secrets no Streamlit Cloud primeiro!")
    st.stop()

# --- ESTADO INICIAL ---
if 'thresholds' not in st.session_state:
    st.session_state.thresholds = {"clim_fresco": 13000, "clim_maduro": 17000, "nclim_firme": 13000, "nclim_risco": 16000}
if 'camera_mode' not in st.session_state:
    st.session_state.camera_mode = "Mock (Simulação)"

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

# --- ALGORITMO DE LATE FUSION ---
def processar_decisao(classe, voc):
    if any(f in str(classe).lower() for f in ["maca", "apple", "banana"]):
        if voc < st.session_state.thresholds["clim_fresco"]: return "VERDE / FRESCO", "#00ffcc", "ESTADO: PRATELEIRA"
        elif voc <= st.session_state.thresholds["clim_maduro"]: return "MADURO / ÓTIMO", "#ffcc00", "ESTADO: PROMOÇÃO IMEDIATA"
        else: return "PODRE / SENESCÊNCIA", "#ff4b4b", "ESTADO: RETIRAR DE IMEDIATO"
    else: 
        if voc < st.session_state.thresholds["nclim_firme"]: return "FIRME / BOA", "#00ffcc", "ESTADO: CONFORME"
        elif voc <= st.session_state.thresholds["nclim_risco"]: return "RISCO DE DEGRADAÇÃO", "#ff9900", "ESTADO: VIGILÂNCIA REFORÇADA"
        else: return "DEGRADADA", "#ff4b4b", "ESTADO: REJEITAR LOTE"

df = fetch_data()

# --- HEARTBEAT / DIAGNÓSTICO ---
nicla_status = "OFFLINE"; nicla_color = "#ff4b4b"; nicla_class = ""
if not df.empty and '_time' in df.columns:
    last_time = df.iloc[-1]['_time']
    segundos = (datetime.now(timezone.utc) - last_time).total_seconds()
    if segundos < 20:
        nicla_status = "ONLINE (BLE)"; nicla_color = "#00ffcc"; nicla_class = "blink"
    elif segundos < 120:
        nicla_status = "LATÊNCIA ALTA"; nicla_color = "#ffcc00"

if st.session_state.camera_mode == "Real OV7675": cam_color = "#00ffcc"; cam_status = "ONLINE (OV7675)"; cam_class = "blink"
elif st.session_state.camera_mode == "Mock (Simulação)": cam_color = "#ffcc00"; cam_status = "MOCK SIMULATOR"; cam_class = "blink"
else: cam_color = "#ff4b4b"; cam_status = "DESCONECTADA"; cam_class = ""

# --- CABEÇALHO ---
col_logo, col_title = st.columns([1, 9])
with col_logo:
    st.markdown("<h1 style='font-size: 3.5rem; margin-top: 5px;'>🍏</h1>", unsafe_allow_html=True)
with col_title:
    st.markdown("<h1>RipeRadar <span style='color: #00d2ff;'>Multi-Modal Edge Fusion</span></h1>", unsafe_allow_html=True)
    st.markdown(f"""
        <div style="margin-top: -10px;">
            <div class="status-pill" style="border-color: {nicla_color}; color: {nicla_color};">
                <span class="live-dot {nicla_class}" style="background-color: {nicla_color};"></span> NODE 1 (SENSE): {nicla_status}
            </div>
            <div class="status-pill" style="border-color: {cam_color}; color: {cam_color};">
                <span class="live-dot {cam_class}" style="background-color: {cam_color};"></span> NODE 2 (VISION): {cam_status}
            </div>
            <div class="status-pill" style="border-color: #00d2ff; color: #00d2ff;">
                <span class="live-dot blink" style="background-color: #00d2ff;"></span> GATEWAY: MQTT / INFLUXDB
            </div>
        </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# --- SISTEMA DE ABAS ---
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

        # 1. CARD DE LATE FUSION
        st.markdown(f"""
            <div class="action-card" style="border-color: {cor}44;">
                <p class="mono-text" style="margin-bottom: 5px; font-size: 0.9rem; letter-spacing: 2px;">ALGORITMO DE FUSÃO (VISION + OLFACTION)</p>
                <h3 style="color: #a0a5b5; font-family: 'Inter';">TINYML CLASSIFICATION: <span style="color: white; border-bottom: 2px solid #00d2ff;">{fruta.upper().replace('_', ' ')}</span></h3>
                <h1 style="color: {cor}; font-size: 4rem; margin: 5px 0; text-transform: uppercase; text-shadow: 0 0 20px {cor}44;">{estado}</h1>
                <h3 style="color: #ffffff; font-family: 'Roboto Mono'; font-weight: 400; font-size: 1.2rem;">{acao}</h3>
            </div>
            """, unsafe_allow_html=True)

        # 2. VETOR SENSORIAL (Métricas)
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("ÍNDICE VOC", f"{voc/1000:.1f} kΩ", delta="Resistência (MOS)", delta_color="off")
        c2.metric("CONFIANÇA (IA)", f"{conf:.1f}%", delta="CNN Inference", delta_color="normal")
        c3.metric("TEMPERATURA", f"{temp:.1f} ºC", delta="BME688", delta_color="off")
        c4.metric("HUMIDADE", f"{hum:.1f}%", delta="BME688", delta_color="off")
        c5.metric("PRESSÃO ATM.", f"{hpa:.1f} hPa", delta="BME688", delta_color="off")

        st.markdown("<br><br>", unsafe_allow_html=True)

        # 3. GRÁFICOS ACADÉMICOS
        col_l, col_r = st.columns([1.5, 1])
        
        with col_l:
            st.markdown("<h3 style='font-size: 1.2rem; margin-bottom: 15px; color: #ffffff;'>📈 Análise de Senescência (VOC Series)</h3>", unsafe_allow_html=True)
            if 'voc_gas' in df.columns:
                df_clean = df.dropna(subset=['voc_gas'])
                fig_voc = px.line(df_clean, x='_time', y='voc_gas', template="plotly_dark", color_discrete_sequence=[cor])
                fig_voc.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', 
                    margin=dict(l=0,r=0,t=10,b=0), xaxis_title="Tempo (UTC)", yaxis_title="Resistência VOC (Ω)",
                    font=dict(family="Inter", color="#a0a5b5"), hovermode="x unified",
                    xaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)'),
                    yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)')
                )
                fig_voc.update_traces(line=dict(width=2.5), fill='tozeroy', fillcolor=f"rgba({ '255, 75, 75' if cor == '#ff4b4b' else '0, 255, 204' if cor == '#00ffcc' else '255, 204, 0' }, 0.1)")
                st.plotly_chart(fig_voc, use_container_width=True)

        with col_r:
            st.markdown("<h3 style='font-size: 1.2rem; margin-bottom: 15px; color: #ffffff;'>🕸️ Assinatura Ambiental (Radar)</h3>", unsafe_allow_html=True)
            # Normalização geométrica para o Radar Chart
            radar_data = pd.DataFrame(dict(
                r=[temp * 3, hum, (hpa - 900) if hpa > 900 else 0, (voc / 200) if voc > 0 else 0, conf],
                theta=['Temp (Norm)', 'Hum (%)', 'Pressão (Rel)', 'VOC (Norm)', 'IA Conf (%)']
            ))
            fig_radar = px.line_polar(radar_data, r='r', theta='theta', line_close=True, template="plotly_dark")
            fig_radar.update_traces(fill='toself', fillcolor='rgba(0, 210, 255, 0.2)', line_color='#00d2ff', line_width=2)
            
            fig_radar.update_layout(
                paper_bgcolor='rgba(0,0,0,0)', 
                plot_bgcolor='rgba(0,0,0,0)',
                polar=dict(
                    bgcolor='rgba(0,0,0,0)', # Fundo transparente do radar
                    radialaxis=dict(visible=False, showticklabels=False), 
                    angularaxis=dict(
                        color="#a0a5b5", 
                        tickfont=dict(family="Inter", size=11) 
                    )
                ),
                margin=dict(l=40, r=40, t=20, b=20)
            )
            st.plotly_chart(fig_radar, use_container_width=True)
            
    else:
        st.error("⚠️ SINAL DE TELEMETRIA INEXISTENTE OU LATÊNCIA CRÍTICA. Verifique o nó BLE e o Gateway MQTT.")

with tab_admin:
    st.header("⚙️ Calibração de Limiares (Late Fusion)")
    st.markdown("<p style='color: #a0a5b5; font-family: Inter;'>Ajuste dinâmico dos parâmetros de inferência baseados na resposta do sensor semicondutor (MOS).</p>", unsafe_allow_html=True)
    
    st.markdown("<h3 style='font-size: 1.1rem; color: #00d2ff; margin-top: 20px;'>📷 Configuração do Sensor Ótico (Camada de Visão)</h3>", unsafe_allow_html=True)
    st.session_state.camera_mode = st.radio("Selecione o estado de input do pipeline visual:", ["Real OV7675", "Mock (Simulação)", "Desconectada"], horizontal=True)
    
    st.divider()
    
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("<h3 style='font-size: 1.1rem; color: #ffcc00;'>🍌 Curva de Senescência Climatérica</h3>", unsafe_allow_html=True)
        st.session_state.thresholds["clim_fresco"] = st.slider("Transição Verde ➡️ Maduro (VOC Ω)", 10000, 15000, st.session_state.thresholds["clim_fresco"])
        st.session_state.thresholds["clim_maduro"] = st.slider("Transição Maduro ➡️ Podre (VOC Ω)", 15000, 20000, st.session_state.thresholds["clim_maduro"])
    with col_b:
        st.markdown("<h3 style='font-size: 1.1rem; color: #ff9900;'>🍊 Curva de Degradação Não-Climatérica</h3>", unsafe_allow_html=True)
        st.session_state.thresholds["nclim_firme"] = st.slider("Transição Firme ➡️ Risco (VOC Ω)", 10000, 14000, st.session_state.thresholds["nclim_firme"])
        st.session_state.thresholds["nclim_risco"] = st.slider("Transição Risco ➡️ Degradada (VOC Ω)", 14000, 18000, st.session_state.thresholds["nclim_risco"])

with tab_paper:
    st.markdown("""
        <div class="paper-container">
            <h1 class="paper-title">RipeRadar: Multimodal Edge Fusion for Real-Time Fruit Spoilage Detection</h1>
            <p class="paper-authors">Eduarda Pereira, Gonçalo Ferreira, Gonçalo Magalhães</p>
            <p class="paper-affiliation">Department of Informatics, University of Minho, Braga, Portugal<br>
            <i>Projecto de Internet of Things - MEI 2025/2026</i></p>
            
            <hr style="border-color: rgba(255,255,255,0.1); margin: 30px 0;">
            
            <h3 style="color: #ffffff; text-align: center; text-transform: uppercase; font-size: 1rem; letter-spacing: 2px;">Abstract</h3>
            <p class="paper-abstract">
                A degradação da qualidade hortofrutícola durante a cadeia de abastecimento e no retalho representa um desafio logístico e económico significativo, contribuindo para elevados índices de desperdício alimentar. Para superar as limitações de infraestruturas centralizadas, propomos o <b>RipeRadar</b>, uma arquitetura <i>Internet of Things (IoT)</i> descentralizada para monitorização multimodal.
                <br><br>
                O RipeRadar transpõe o processamento analítico para a <i>Edge</i> da rede através de modelos <i>Tiny Machine Learning (TinyML)</i> executados diretamente em microcontroladores. A inovação central reside numa estratégia de <b>Late Fusion</b> (Decision-Level Fusion) que correlaciona inferências visuais de uma rede neuronal (via OV7675 no Arduino Nano 33 BLE) com leituras contínuas de compostos orgânicos voláteis (VOCs) extraídas do sensor BME688 (Arduino Nicla Sense ME). 
                <br><br>
                A orquestração assíncrona é mediada via Bluetooth Low Energy (BLE) por um <i>Edge Gateway</i> (Raspberry Pi 5) suportado por um broker MQTT, culminando nesta plataforma analítica baseada em InfluxDB. Este ecossistema garante autonomia operacional, latência residual e mitigação de falsos positivos face a ambiguidades visuais no retalho inteligente.
            </p>
            
            <br>
            <h3 style="color: #00d2ff; font-size: 1.1rem; border-bottom: 1px solid rgba(0, 210, 255, 0.2); padding-bottom: 5px;">Arquitetura do Sistema</h3>
            <ul style="color: #a0a5b5; font-family: Inter; line-height: 1.8;">
                <li><b>Camada de Perceção (Periphery):</b> Arduino Nano 33 BLE (Visão / CNN) + Arduino Nicla Sense ME (Olfação Digital / BME688).</li>
                <li><b>Camada de Comunicação:</b> Bluetooth Low Energy (BLE) para eficiência energética e MQTT para transporte assíncrono.</li>
                <li><b>Camada de Processamento (Edge Gateway):</b> Raspberry Pi 5 atuando como agregador (Eclipse Mosquitto) e motor de fusão de dados.</li>
                <li><b>Camada de Aplicação:</b> Base de dados temporal (InfluxDB) e interface analítica em tempo real (Streamlit).</li>
            </ul>
        </div>
    """, unsafe_allow_html=True)

# Auto-refresh a cada 5 segundos
time.sleep(5)
st.rerun()