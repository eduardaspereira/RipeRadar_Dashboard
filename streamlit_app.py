import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from influxdb_client import InfluxDBClient
from datetime import datetime, timezone
import time

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="RipeRadar OS | Enterprise", page_icon="🍎", layout="wide", initial_sidebar_state="expanded")

# --- 2. GESTÃO DE SESSÃO (LOGIN / RBAC) ---
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
        st.error("Credenciais inválidas. Tente: chefe/admin123 ou operador/op123")

def logout():
    st.session_state.logado = False
    st.session_state.cargo = ""

# --- 3. CSS CORPORATIVO & PAPER ACADÉMICO ---
st.markdown("""
    <style>
    /* Fundo limpo corporativo */
    .stApp { background-color: #F8F9FA; color: #2C3E50; font-family: 'Inter', sans-serif; }
    
    /* Cartões de Métricas */
    div[data-testid="metric-container"] {
        background-color: #FFFFFF;
        border-radius: 8px;
        padding: 15px 20px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        border-left: 4px solid #1F77B4;
    }
    div[data-testid="stMetricValue"] { font-size: 1.8rem; color: #2C3E50; font-weight: 700; }
    div[data-testid="stMetricLabel"] { color: #7F8C8D; font-weight: 600; font-size: 0.9rem; }

    /* Cartão de Ação Principal */
    .action-card {
        background-color: #FFFFFF;
        padding: 25px; border-radius: 10px; text-align: center; margin-bottom: 20px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.05);
        border: 1px solid #E0E0E0;
    }
    
    /* Tabs Corporativas */
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { padding: 10px 20px; font-weight: 600; color: #7F8C8D; }
    .stTabs [aria-selected="true"] { border-bottom: 3px solid #1F77B4 !important; color: #1F77B4 !important; }

    /* Estilos do Paper e Diagrama ASCII (Os teus originais adaptados para fundo claro) */
    .paper-box { background: #FFFFFF; color: #333333; padding: 40px; border-radius: 8px; font-family: "Times New Roman", serif; border: 1px solid #E0E0E0; box-shadow: 0 2px 5px rgba(0,0,0,0.05);}
    .paper-title { font-size: 24px; text-align: center; font-weight: bold; margin-bottom: 5px; }
    .paper-authors { text-align: center; font-style: italic; margin-bottom: 20px; font-size: 16px; }
    .paper-abstract-title { font-weight: bold; text-align: center; text-transform: uppercase; font-size: 14px; margin-bottom: 10px; }
    .paper-text { text-align: justify; line-height: 1.6; font-size: 15px; margin-bottom: 15px; }
    .paper-list { font-size: 15px; line-height: 1.6; text-align: justify; }
    
    .ascii-diagram { background-color: #F4F6F8; border: 1px solid #d1d5db; border-radius: 6px; padding: 15px; margin: 20px 0; overflow-x: auto; }
    .ascii-diagram pre { font-family: 'Roboto Mono', monospace; font-size: 12px; color: #374151; line-height: 1.2; margin: 0; }
    </style>
    """, unsafe_allow_html=True)

# --- 4. CREDENCIAIS & FUNÇÕES DE DADOS ---
try:
    INFLUX_URL = st.secrets["INFLUX_URL"]
    INFLUX_TOKEN = st.secrets["INFLUX_TOKEN"]
    INFLUX_ORG = st.secrets["INFLUX_ORG"]
    INFLUX_BUCKET = st.secrets["INFLUX_BUCKET"]
except Exception:
    st.warning("⚠️ Configura os Secrets no Streamlit Cloud primeiro!")

@st.cache_data
def get_thresholds():
    return {"clim_fresco": 13000, "clim_maduro": 17000, "nclim_firme": 13000, "nclim_risco": 16000}

thresholds = get_thresholds()

def fetch_data():
    try:
        client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
        query = f'from(bucket: "{INFLUX_BUCKET}") |> range(start: -30m) |> filter(fn: (r) => r["_measurement"] == "mqtt_consumer") |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")'
        df = client.query_api().query_data_frame(query)
        if isinstance(df, list): df = pd.concat(df)
        return df if isinstance(df, pd.DataFrame) and not df.empty else pd.DataFrame()
    except: return pd.DataFrame()

def processar_decisao(classe, voc):
    if any(f in str(classe).lower() for f in ["maca", "apple", "banana"]):
        if voc < thresholds["clim_fresco"]: return "VERDE / FRESCO", "#2CA02C", "ESTADO: PRATELEIRA"
        elif voc <= thresholds["clim_maduro"]: return "MADURO / ÓTIMO", "#F39C12", "ESTADO: PROMOÇÃO IMEDIATA"
        else: return "PODRE / SENESCÊNCIA", "#E74C3C", "ESTADO: RETIRAR DE IMEDIATO"
    else: 
        if voc < thresholds["nclim_firme"]: return "FIRME / BOA", "#2CA02C", "ESTADO: CONFORME"
        elif voc <= thresholds["nclim_risco"]: return "RISCO DE DEGRADAÇÃO", "#F39C12", "ESTADO: VIGILÂNCIA REFORÇADA"
        else: return "DEGRADADA", "#E74C3C", "ESTADO: REJEITAR LOTE"

# ==========================================
# ECRÃ 1: LOGIN
# ==========================================
if not st.session_state.logado:
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.markdown("<div style='background: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); text-align: center; border: 1px solid #E0E0E0;'>", unsafe_allow_html=True)
        st.markdown("<h1 style='font-size: 3rem;'>🍎</h1>", unsafe_allow_html=True)
        st.markdown("<h2 style='color: #2C3E50; margin-bottom: 0;'>RipeRadar OS</h2>", unsafe_allow_html=True)
        st.markdown("<p style='color: #7F8C8D; margin-bottom: 20px;'>Autenticação Corporativa</p>", unsafe_allow_html=True)
        
        st.text_input("ID de Utilizador", key="user_input")
        st.text_input("Palavra-Passe", type="password", key="pass_input")
        st.button("Aceder ao Sistema", on_click=verificar_login, use_container_width=True, type="primary")
        st.markdown("</div>", unsafe_allow_html=True)

# ==========================================
# ECRÃ 2: DASHBOARD PRINCIPAL (LOGADO)
# ==========================================
else:
    # --- MENU LATERAL ---
    with st.sidebar:
        st.markdown("### 👤 Perfil Ativo")
        st.info(f"**{st.session_state.cargo}**")
        st.button("Terminar Sessão", on_click=logout, use_container_width=True)
        st.divider()
        st.markdown("**Status da Infraestrutura:**")
        st.success("🟢 Edge Gateway: Online")
        st.success("🟢 InfluxDB: Sincronizado")
        st.success("🟢 Node 1 (Visão): Ativo")
        st.success("🟢 Node 2 (Olfato): Ativo")

    # --- DADOS E CABEÇALHO ---
    df = fetch_data()
    st.markdown("<h2>RipeRadar <span style='color: #1F77B4; font-weight: 300;'>Retail Monitor</span></h2>", unsafe_allow_html=True)
    
    tab_dash, tab_admin, tab_paper = st.tabs(["📊 Monitorização Real-Time", "⚙️ Calibração de IA", "📄 Arquitetura do Sistema"])

    # ---------------------------------------------------------
    # TAB 1: DASHBOARD
    # ---------------------------------------------------------
    with tab_dash:
        if not df.empty and '_time' in df.columns:
            latest = df.iloc[-1]
            voc = float(latest.get('voc_gas', 0.0))
            fruta = str(latest.get('classe_dominante', 'Desconhecido'))
            conf = float(latest.get('confianca', 0.0))
            temp = float(latest.get('temp', 0.0))
            hum = float(latest.get('hum', 0.0))
            hpa = float(latest.get('hPa', 0.0))
            
            estado, cor, acao = processar_decisao(fruta, voc)

            # Cartão de Decisão (Visível para ambos)
            st.markdown(f"""
                <div class="action-card" style="border-top: 6px solid {cor};">
                    <p style="color: #7F8C8D; text-transform: uppercase; font-size: 0.85rem; font-weight: bold; margin-bottom: 5px;">Lote em Análise: {fruta.upper().replace('_', ' ')} (Confiança IA: {conf*100 if conf <= 1 else conf:.1f}%)</p>
                    <h1 style="color: {cor}; font-size: 3.5rem; margin: 0;">{estado}</h1>
                    <h3 style="color: #34495E; margin-top: 5px;">{acao}</h3>
                </div>
                """, unsafe_allow_html=True)

            # Métricas
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("ÍNDICE VOC", f"{voc/1000:.1f} kΩ")
            c2.metric("TEMPERATURA", f"{temp:.1f} ºC")
            c3.metric("HUMIDADE", f"{hum:.1f}%")
            c4.metric("PRESSÃO", f"{hpa:.1f} hPa")
            c5.metric("STATUS", "Vigilância Ativa")

            st.markdown("<br>", unsafe_allow_html=True)

            # --- ZONA EXCLUSIVA DO CHEFE DE LOJA ---
            if st.session_state.cargo == "Chefe de Loja":
                st.subheader("📋 Painel de Gestão: Histórico Multidimensional")
                col_l, col_r = st.columns([1.5, 1])
                
                with col_l:
                    st.markdown("**Evolução Gasosa do Lote (Últimos 30m)**")
                    if 'voc_gas' in df.columns:
                        df_clean = df.dropna(subset=['voc_gas'])
                        fig_voc = px.area(df_clean, x='_time', y='voc_gas', color_discrete_sequence=['#1F77B4'])
                        fig_voc.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=0,r=0,t=10,b=0))
                        st.plotly_chart(fig_voc, use_container_width=True)

                with col_r:
                    st.markdown("**Assinatura Ambiental Atual**")
                    radar_data = pd.DataFrame(dict(
                        r=[temp * 3, hum, (hpa - 900) if hpa > 900 else 0, (voc / 200) if voc > 0 else 0, conf * 100 if conf <= 1 else conf],
                        theta=['Temp', 'Hum', 'Pressão', 'VOC', 'IA Conf']
                    ))
                    fig_radar = px.line_polar(radar_data, r='r', theta='theta', line_close=True)
                    fig_radar.update_traces(fill='toself', fillcolor='rgba(31, 119, 180, 0.2)', line_color='#1F77B4')
                    fig_radar.update_layout(
                        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                        polar=dict(bgcolor='rgba(0,0,0,0)', radialaxis=dict(visible=False)),
                        margin=dict(l=40, r=40, t=20, b=20)
                    )
                    st.plotly_chart(fig_radar, use_container_width=True)
        else:
            st.info("A aguardar dados da Edge Gateway...")

    # ---------------------------------------------------------
    # TAB 2: CALIBRAÇÃO (ADMIN ONLY)
    # ---------------------------------------------------------
    with tab_admin:
        st.header("⚙️ Calibração de Limiares (Late Fusion)")
        if st.session_state.cargo == "Chefe de Loja":
            with st.form("calibration_form"):
                st.markdown("Ajuste dinâmico dos parâmetros de inferência baseados na resposta do sensor semicondutor (MOS).")
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
                    
                if st.form_submit_button("Guardar Calibração", type="primary"):
                    get_thresholds.clear()
                    def get_thresholds(): return {"clim_fresco": clim_f, "clim_maduro": clim_m, "nclim_firme": nclim_f, "nclim_risco": nclim_r}
                    thresholds = get_thresholds()
                    st.success("Configurações atualizadas com sucesso!")
        else:
            st.error("🔒 Acesso Restrito. Apenas utilizadores com perfil de 'Chefe de Loja' têm permissão para alterar calibrações de inteligência artificial.")

    # ---------------------------------------------------------
    # TAB 3: PUBLICAÇÃO CIENTÍFICA (DOCUMENTAÇÃO)
    # ---------------------------------------------------------
    with tab_paper:
        html_paper = """<div class="paper-box">
        <div class="paper-title">RipeRadar: Multimodal Edge Fusion for Real-Time Fruit Spoilage Detection</div>
        <div class="paper-authors">Eduarda Pereira, Gonçalo Ferreira, Gonçalo Magalhães<br>Department of Informatics, University of Minho, Braga, Portugal</div>
        <div class="paper-abstract-title">Abstract</div>
        <p class="paper-text">A degradação da qualidade hortofrutícola durante a cadeia de abastecimento e no retalho representa um desafio logístico e económico significativo, contribuindo para elevados índices de desperdício alimentar. Para superar as limitações de infraestruturas centralizadas, propomos o <b>RipeRadar</b>, uma arquitetura <i>Internet of Things (IoT)</i> descentralizada para monitorização multimodal.</p>
        <p class="paper-text">O RipeRadar transpõe o processamento analítico para a <i>Edge</i> da rede através de modelos <i>Tiny Machine Learning (TinyML)</i> executados diretamente em microcontroladores. A inovação central reside numa estratégia de <b>Late Fusion</b> (Decision-Level Fusion) que correlaciona inferências visuais de uma rede neuronal (via OV7675 no Arduino Nano 33 BLE) com leituras contínuas de compostos orgânicos voláteis (VOCs) extraídas do sensor BME688 (Arduino Nicla Sense ME).</p>
        <p class="paper-text">A orquestração assíncrona é mediada via Bluetooth Low Energy (BLE) por um <i>Edge Gateway</i> (Raspberry Pi 5), que publica os dados fundidos num <i>Message Broker</i> (HiveMQ) via protocolo MQTT. A ingestão na base de dados temporal (InfluxDB) é automatizada pelo serviço Telegraf, culminando nesta plataforma analítica. Este ecossistema garante autonomia operacional, baixo consumo de largura de banda e mitigação de falsos positivos face a ambiguidades visuais no retalho inteligente.</p>
        <hr style="margin: 30px 0; border: 1px solid #E0E0E0;">
        <h3 style="font-size: 18px; margin-bottom: 10px; color: #111;">System Architecture</h3>
        <div class="ascii-diagram">
        <pre>
[CAMADA DE PERCEÇÃO]           [CAMADA GATEWAY]              [CAMADA CLOUD / APLICAÇÃO]

+---------------------+
| Arduino Nano 33 BLE |
| (Visão / CNN)       | --(BLE)--\\
+---------------------+           \\
                                   v
                            +----------------+  (MQTT)   +----------------+       +-----------------+
                            | Raspberry Pi 5 | --------> | HiveMQ Cloud   |       | Streamlit Cloud |
                            | (Script MQTT)  |  (TLS)    | (Broker MQTT)  |       | (Dashboard UI)  |
                            +----------------+           +----------------+       +-----------------+
                                   ^                             |                        ^
                                  /                        (Telegraf Sub)                 | (Query)
+---------------------+          /                               v                        |
| Nicla Sense ME      | --(BLE)-/                        +----------------+---------------+
| (BME688 - VOC/Temp) |                                  | InfluxDB Cloud |
+---------------------+                                  | (Time-Series)  |
                                                         +----------------+
        </pre>
        </div>
        <ul class="paper-list">
        <li><b>Camada de Perceção (Periphery):</b> Arduino Nano 33 BLE (Visão / CNN) e Arduino Nicla Sense ME (Olfação Digital).</li>
        <li><b>Camada Gateway:</b> Raspberry Pi 5 atua como agregador local, fundindo os dados e publicando via MQTT (QoS 1).</li>
        <li><b>Camada de Mensagens:</b> HiveMQ Cloud gere a conectividade segura (TLS, porta 8883) servindo como <i>Broker</i> central.</li>
        <li><b>Camada de Armazenamento e UI:</b> Telegraf injeta as métricas no InfluxDB Cloud, consumido em tempo real pelo Streamlit.</li>
        </ul>
        </div>"""
        st.markdown(html_paper, unsafe_allow_html=True)

    # --- AUTO REFRESH (Apenas se estiver logado) ---
    time.sleep(5)
    st.rerun()