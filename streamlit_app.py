import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from influxdb_client import InfluxDBClient
from datetime import datetime
import time

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="RipeRadar OS | Cloud", page_icon="🍎", layout="wide", initial_sidebar_state="collapsed")

# --- CSS FUTURISTA PREMIUM (GLASSMORPHISM & CYBER-INDUSTRIAL) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Inter:wght@300;400;600&display=swap');
    
    /* Fundo Escuro com grelha subtil para aspeto técnico */
    .stApp { 
        background: radial-gradient(circle at 50% 0%, #1e213a 0%, #0f0c29 70%, #050510 100%); 
        color: #e0e0e0;
        background-image: linear-gradient(rgba(255, 255, 255, 0.02) 1px, transparent 1px), linear-gradient(90deg, rgba(255, 255, 255, 0.02) 1px, transparent 1px);
        background-size: 30px 30px;
    }
    
    h1, h2, h3 { font-family: 'Orbitron', sans-serif; text-shadow: 0 0 10px rgba(0,210,255,0.3); }
    p, span, div { font-family: 'Inter', sans-serif; }
    
    /* Cartões Glassmorphism para as Métricas */
    div[data-testid="metric-container"] {
        background: rgba(20, 25, 45, 0.6);
        border-radius: 15px;
        padding: 20px;
        border: 1px solid rgba(255, 255, 255, 0.05);
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        transition: transform 0.3s ease, box-shadow 0.3s ease;
    }
    div[data-testid="metric-container"]:hover {
        transform: translateY(-5px);
        box-shadow: 0 12px 40px 0 rgba(0, 210, 255, 0.15);
        border: 1px solid rgba(0, 210, 255, 0.3);
    }
    
    /* Estilo das Métricas (Texto) */
    div[data-testid="stMetricValue"] { font-family: 'Orbitron', sans-serif; font-size: 2rem; color: #ffffff; }
    div[data-testid="stMetricLabel"] { color: #a0a5b5; font-weight: 600; letter-spacing: 1px; font-size: 0.9rem; }

    /* Cartão de Ação Central */
    .action-card {
        padding: 30px;
        border-radius: 20px;
        text-align: center;
        margin-bottom: 30px;
        border: 2px solid;
        box-shadow: 0 0 30px rgba(0,0,0,0.6) inset, 0 10px 30px rgba(0,0,0,0.5);
        backdrop-filter: blur(10px);
        animation: pulse-glow 2s infinite alternate;
    }
    
    /* Tabs Premium */
    .stTabs [data-baseweb="tab-list"] { gap: 20px; background-color: transparent; }
    .stTabs [data-baseweb="tab"] {
        background-color: rgba(255, 255, 255, 0.03);
        border-radius: 8px 8px 0 0;
        border-bottom: 2px solid transparent;
        padding: 10px 25px;
    }
    .stTabs [aria-selected="true"] {
        background-color: rgba(0, 210, 255, 0.1) !important;
        border-bottom: 2px solid #00d2ff !important;
        color: #00d2ff !important;
        text-shadow: 0 0 8px rgba(0, 210, 255, 0.5);
    }

    /* Ponto a piscar para indicar LIVE DATA */
    .live-dot {
        height: 12px; width: 12px;
        background-color: #00ffcc;
        border-radius: 50%;
        display: inline-block;
        box-shadow: 0 0 10px #00ffcc;
        animation: blinker 1.5s linear infinite;
        margin-right: 10px;
    }
    @keyframes blinker { 50% { opacity: 0.2; box-shadow: 0 0 2px #00ffcc; } }
    
    /* Footer Fixo e Elegante */
    .footer-container {
        position: fixed; left: 0; bottom: 0; width: 100%;
        background: rgba(10, 12, 25, 0.85);
        backdrop-filter: blur(10px);
        border-top: 1px solid rgba(255, 255, 255, 0.1);
        text-align: center; padding: 15px 0; z-index: 999;
    }
    .footer-text {
        font-family: 'Inter', sans-serif; font-size: 0.9rem; color: #8a92a6; margin: 0;
    }
    .footer-names {
        font-weight: 600; color: #00d2ff;
    }
    
    /* Esconder o padding final do streamlit para o footer encaixar */
    .block-container { padding-bottom: 80px; }
    </style>
    """, unsafe_allow_html=True)

# --- CREDENCIAIS SEGURAS DO INFLUXDB ---
try:
    INFLUX_URL = st.secrets["INFLUX_URL"]
    INFLUX_TOKEN = st.secrets["INFLUX_TOKEN"]
    INFLUX_ORG = st.secrets["INFLUX_ORG"]
    INFLUX_BUCKET = st.secrets["INFLUX_BUCKET"]
except Exception:
    st.error("⚠️ Configura os Secrets no Streamlit Cloud primeiro!")
    st.stop()

# --- INICIALIZAÇÃO DE ESTADO (THRESHOLDS) ---
if 'thresholds' not in st.session_state:
    st.session_state.thresholds = {
        "clim_fresco": 13000, "clim_maduro": 17000, 
        "nclim_firme": 13000, "nclim_risco": 16000 
    }

# --- LÓGICA DE DADOS (INFLUXDB) ---
def fetch_data():
    client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    query_api = client.query_api()
    
    # Busca os últimos 5 minutos
    query = f"""
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: -5m)
      |> filter(fn: (r) => r["_measurement"] == "mqtt_consumer")
      |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
    """
    try:
        df = query_api.query_data_frame(query)
        if isinstance(df, list): df = pd.concat(df) # Caso retorne múltiplas tabelas
        return df if isinstance(df, pd.DataFrame) and not df.empty else pd.DataFrame()
    except Exception as e:
        if "401" in str(e): st.error("🔑 Erro 401: Verifica o Token do InfluxDB.")
        return pd.DataFrame()

# --- LÓGICA DE DECISÃO ---
def processar_decisao(classe, voc):
    if any(f in str(classe).lower() for f in ["maca", "apple", "banana"]):
        if voc < st.session_state.thresholds["clim_fresco"]: return "VERDE / FRESCO", "#00ffcc", "MANTER EM PRATELEIRA"
        elif voc <= st.session_state.thresholds["clim_maduro"]: return "MADURO / ÓTIMO", "#ffcc00", "PROMOÇÃO (VENDA RÁPIDA)"
        else: return "PODRE / SENESCÊNCIA", "#ff4b4b", "RETIRAR IMEDIATAMENTE"
    else: 
        if voc < st.session_state.thresholds["nclim_firme"]: return "FIRME / BOA", "#00ffcc", "CONFORME"
        elif voc <= st.session_state.thresholds["nclim_risco"]: return "RISCO DE DEGRADAÇÃO", "#ff9900", "VIGILÂNCIA REFORÇADA"
        else: return "DEGRADADA", "#ff4b4b", "REJEITAR LOTE"

# --- HEADER DA APLICAÇÃO ---
col_logo, col_title = st.columns([1, 8])
with col_logo:
    st.markdown("<h1 style='font-size: 3rem; text-align: center; margin-top: 10px;'>🍎</h1>", unsafe_allow_html=True)
with col_title:
    st.markdown("<h1>RipeRadar <span style='color: #00d2ff;'>OS</span></h1>", unsafe_allow_html=True)
    st.markdown("<div><span class='live-dot'></span><span style='color: #00ffcc; font-weight: 600; letter-spacing: 1px;'>CLOUD TELEMETRY ACTIVE</span></div>", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# --- INTERFACE PRINCIPAL ---
tab_dash, tab_admin = st.tabs(["📊 DASHBOARD OPERACIONAL", "⚙️ CONFIGURAÇÕES ADMIN"])

df = fetch_data()

with tab_dash:
    if not df.empty:
        latest = df.iloc[-1]
        
        # Extração Robusta (Evita KeyErrors se a DB falhar o envio de alguma métrica num determinado segundo)
        voc = float(latest['voc_gas']) if 'voc_gas' in latest else 0.0
        fruta = str(latest['classe_dominante']) if 'classe_dominante' in latest else 'Desconhecido'
        conf = float(latest['confianca']) if 'confianca' in latest else 0.0
        temp = float(latest['temp']) if 'temp' in latest else 0.0
        hum = float(latest['hum']) if 'hum' in latest else 0.0
        hpa = float(latest['hPa']) if 'hPa' in latest else 0.0
        
        estado, cor, acao = processar_decisao(fruta, voc)

        # 1. CARD DE AÇÃO CENTRAL
        st.markdown(f"""
            <div class="action-card" style="background: rgba({ '255, 75, 75' if cor == '#ff4b4b' else '0, 255, 204' if cor == '#00ffcc' else '255, 204, 0' }, 0.05); border-color: {cor};">
                <h3 style="color: #a0a5b5; margin-bottom: 5px; font-family: 'Inter';">DETEÇÃO IA VISION: <span style="color: white;">{fruta.upper().replace('_', ' ')}</span></h3>
                <h1 style="color: {cor}; font-size: 3.5rem; margin: 10px 0; font-weight: 900; letter-spacing: 2px;">{estado}</h1>
                <h2 style="color: white; font-family: 'Inter'; font-weight: 300;">{acao}</h2>
            </div>
            """, unsafe_allow_html=True)

        # 2. MÉTRICAS RÁPIDAS
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("ÍNDICE VOC", f"{voc:.0f} Ω", delta="Gás Emitido", delta_color="off")
        c2.metric("CONFIANÇA FUSÃO", f"{conf:.1f}%", delta="TinyML Edge", delta_color="normal")
        c3.metric("TEMP. AMBIENTE", f"{temp:.1f} ºC", delta="Sensor BME", delta_color="off")
        c4.metric("HUMIDADE", f"{hum:.1f}%", delta="Sensor BME", delta_color="off")
        c5.metric("PRESSÃO ATM.", f"{hpa:.1f} hPa", delta="Sensor BME", delta_color="off")

        st.markdown("<br>", unsafe_allow_html=True)

        # 3. GRÁFICOS INTERATIVOS (Apenas criados se as variáveis existirem no DataFrame)
        col_l, col_r = st.columns(2)
        
        with col_l:
            st.markdown("<h3 style='font-size: 1.2rem; margin-bottom: 15px;'>📈 Evolução Olfativa (VOC)</h3>", unsafe_allow_html=True)
            if 'voc_gas' in df.columns and '_time' in df.columns:
                # Removemos NaNs (linhas onde o voc_gas não foi registado) para não quebrar a linha do gráfico
                df_clean = df.dropna(subset=['voc_gas'])
                if not df_clean.empty:
                    fig_voc = px.line(df_clean, x='_time', y='voc_gas', template="plotly_dark", color_discrete_sequence=[cor])
                    fig_voc.update_layout(
                        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', 
                        margin=dict(l=0,r=0,t=0,b=0), xaxis_title="", yaxis_title="Resistência (Ω)",
                        font=dict(family="Inter", color="#a0a5b5"), hovermode="x unified"
                    )
                    fig_voc.update_traces(line=dict(width=3), fill='tozeroy', fillcolor=f"rgba({ '255, 75, 75' if cor == '#ff4b4b' else '0, 255, 204' if cor == '#00ffcc' else '255, 204, 0' }, 0.1)")
                    st.plotly_chart(fig_voc, use_container_width=True)
            else:
                st.caption("A aguardar dados históricos de VOC...")

        with col_r:
            st.markdown("<h3 style='font-size: 1.2rem; margin-bottom: 15px;'>🧠 Temperatura vs Confiança</h3>", unsafe_allow_html=True)
            if 'temp' in df.columns and 'confianca' in df.columns:
                fig_comp = go.Figure()
                # Removemos NaNs individualmente para desenhar cada linha corretamente
                df_temp = df.dropna(subset=['temp'])
                df_conf = df.dropna(subset=['confianca'])
                
                if not df_temp.empty:
                    fig_comp.add_trace(go.Scatter(x=df_temp['_time'], y=df_temp['temp'], name="Temperatura", line=dict(color="#ff5e62", width=3)))
                if not df_conf.empty:
                    fig_comp.add_trace(go.Scatter(x=df_conf['_time'], y=df_conf['confianca'], name="Confiança", yaxis="y2", line=dict(color="#00d2ff", width=2, dash="dot")))
                
                fig_comp.update_layout(
                    template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    margin=dict(l=0,r=0,t=0,b=0), font=dict(family="Inter", color="#a0a5b5"),
                    yaxis=dict(title="ºC"),
                    yaxis2=dict(title="%", overlaying="y", side="right"),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                st.plotly_chart(fig_comp, use_container_width=True)
            else:
                st.caption("A aguardar dados combinados...")

    else:
        st.info("🔭 À procura de sinal da Edge Gateway na Cloud InfluxDB... Garante que o sensor está a enviar dados.")

with tab_admin:
    st.header("🛠️ Ajuste de Thresholds IA")
    st.markdown("<p style='color: #a0a5b5;'>Estes valores calibram a decisão dinâmica do sensor local, sobrepondo-se à literatura padrão.</p>", unsafe_allow_html=True)
    
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("<h3 style='font-size: 1.1rem; color: #ffcc00;'>🍌 Frutos Climatéricos (Maçã/Banana)</h3>", unsafe_allow_html=True)
        st.session_state.thresholds["clim_fresco"] = st.slider("Limite Verde ➡️ Maduro (VOC)", 10000, 15000, st.session_state.thresholds["clim_fresco"])
        st.session_state.thresholds["clim_maduro"] = st.slider("Limite Maduro ➡️ Podre (VOC)", 15000, 20000, st.session_state.thresholds["clim_maduro"])
    
    with col_b:
        st.markdown("<h3 style='font-size: 1.1rem; color: #ff9900;'>🍊 Frutos Não-Climatéricos (Laranja)</h3>", unsafe_allow_html=True)
        st.session_state.thresholds["nclim_firme"] = st.slider("Limite Firme ➡️ Risco (VOC)", 10000, 14000, st.session_state.thresholds["nclim_firme"])
        st.session_state.thresholds["nclim_risco"] = st.slider("Limite Risco ➡️ Degradada (VOC)", 14000, 18000, st.session_state.thresholds["nclim_risco"])
    
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("♻️ REPOR CALIBRAÇÃO DE FÁBRICA", use_container_width=True):
        st.session_state.thresholds = {"clim_fresco": 13000, "clim_maduro": 17000, "nclim_firme": 13000, "nclim_risco": 16000}
        st.rerun()

# --- FOOTER FIXO ---
st.markdown("""
    <div class="footer-container">
        <p class="footer-text">
            Projeto RipeRadar | Realizado por <span class="footer-names">Eduarda Pereira, Gonçalo Santiago e Gonçalo Magalhães</span><br>
            Universidade do Minho • Internet of Things • 2026
        </p>
    </div>
    """, unsafe_allow_html=True)

# Auto-refresh a cada 5 segundos
time.sleep(5)
st.rerun()