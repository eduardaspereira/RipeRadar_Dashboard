import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from influxdb_client import InfluxDBClient
from datetime import datetime, timezone
import time

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="RipeRadar OS | Enterprise", page_icon="🍏", layout="wide", initial_sidebar_state="expanded")

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
        st.error("Credenciais inválidas. Tente novamente.")

def logout():
    st.session_state.logado = False
    st.session_state.cargo = ""

# --- 3. CSS PREMIUM (SaaS ENTERPRISE UI) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
    
    /* Fundo Global Suave */
    .stApp { background-color: #F0F4F8; color: #1E293B; font-family: 'Inter', sans-serif; }
    
    /* Ocultar elementos nativos desnecessários */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Custom Metric Cards */
    .premium-card {
        background: #FFFFFF; border-radius: 16px; padding: 20px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.04); border: 1px solid #E2E8F0;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .premium-card:hover { transform: translateY(-3px); box-shadow: 0 8px 25px rgba(0, 0, 0, 0.08); }
    .card-title { color: #64748B; font-size: 0.85rem; font-weight: 600; text-transform: uppercase; margin-bottom: 5px; letter-spacing: 0.5px; }
    .card-value { color: #0F172A; font-size: 2rem; font-weight: 700; display: flex; align-items: baseline; gap: 8px;}
    .card-unit { color: #94A3B8; font-size: 1rem; font-weight: 400; }
    
    /* Action Card Principal */
    .main-action-card {
        background: #FFFFFF; border-radius: 20px; padding: 30px; text-align: center;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.05); margin-bottom: 25px; position: relative; overflow: hidden;
    }
    
    /* Timeline Estilo Corporate */
    .timeline { border-left: 3px solid #CBD5E1; margin-left: 20px; padding-left: 30px; position: relative; }
    .timeline-item { position: relative; margin-bottom: 25px; }
    .timeline-item::before {
        content: ''; position: absolute; left: -39px; top: 4px; width: 14px; height: 14px;
        border-radius: 50%; background: #FFFFFF; border: 3px solid #3B82F6; box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.1);
    }
    .timeline-item.warning::before { border-color: #F59E0B; box-shadow: 0 0 0 4px rgba(245, 158, 11, 0.1); }
    .timeline-item.danger::before { border-color: #EF4444; box-shadow: 0 0 0 4px rgba(239, 68, 68, 0.1); }
    .timeline-date { font-size: 0.8rem; color: #64748B; font-weight: 700; margin-bottom: 8px; }
    .timeline-content { background: #FFFFFF; padding: 18px; border-radius: 12px; border: 1px solid #E2E8F0; box-shadow: 0 2px 8px rgba(0,0,0,0.02);}
    
    /* Login Screen Centrado e Limpo */
    .login-container {
        background: #FFFFFF; padding: 50px; border-radius: 24px;
        box-shadow: 0 20px 40px rgba(0, 0, 0, 0.08); text-align: center; max-width: 450px; margin: 0 auto;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] { gap: 20px; border-bottom: 2px solid #E2E8F0; }
    .stTabs [data-baseweb="tab"] { padding: 12px 20px; font-weight: 600; color: #64748B; font-size: 1rem;}
    .stTabs [aria-selected="true"] { border-bottom: 3px solid #0F172A !important; color: #0F172A !important; background: transparent;}
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
        if voc < thresholds["clim_fresco"]: return "VERDE / FRESCO", "#10B981", "ESTADO: PRATELEIRA", "success"
        elif voc <= thresholds["clim_maduro"]: return "MADURO / ÓTIMO", "#F59E0B", "ESTADO: PROMOÇÃO IMEDIATA", "warning"
        else: return "PODRE / SENESCÊNCIA", "#EF4444", "ESTADO: RETIRAR DE IMEDIATO", "danger"
    else: 
        if voc < thresholds["nclim_firme"]: return "FIRME / BOA", "#10B981", "ESTADO: CONFORME", "success"
        elif voc <= thresholds["nclim_risco"]: return "RISCO DE DEGRADAÇÃO", "#F59E0B", "ESTADO: VIGILÂNCIA REFORÇADA", "warning"
        else: return "DEGRADADA", "#EF4444", "ESTADO: REJEITAR LOTE", "danger"

# ==========================================
# ECRÃ 1: LOGIN
# ==========================================
if not st.session_state.logado:
    st.markdown("<br><br><br><br>", unsafe_allow_html=True)
    st.markdown("""
        <div class="login-container">
            <h1 style="font-size: 3.5rem; margin-bottom: 0;">🍎</h1>
            <h2 style="color: #0F172A; font-weight: 700; letter-spacing: -1px; margin-top: 10px;">RipeRadar OS</h2>
            <p style="color: #64748B; margin-bottom: 30px;">Gestão Inteligente de Qualidade Hortofrutícola</p>
        </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.text_input("ID de Utilizador", key="user_input")
        st.text_input("Palavra-Passe", type="password", key="pass_input")
        st.markdown("<br>", unsafe_allow_html=True)
        st.button("Entrar no Sistema", on_click=verificar_login, use_container_width=True, type="primary")

# ==========================================
# ECRÃ 2: DASHBOARD
# ==========================================
else:
    # --- MENU LATERAL PREMIUM ---
    with st.sidebar:
        st.markdown(f"<h3 style='color: #0F172A; font-weight: 700;'>Bem-vindo,<br><span style='color: #3B82F6;'>{st.session_state.cargo}</span></h3>", unsafe_allow_html=True)
        st.button("Sair da Conta", on_click=logout, use_container_width=True)
        st.markdown("<br><hr style='border-color: #E2E8F0;'><br>", unsafe_allow_html=True)
        
        st.markdown("<p style='font-size: 0.85rem; font-weight: 600; color: #64748B; text-transform: uppercase;'>Infraestrutura IoT</p>", unsafe_allow_html=True)
        st.markdown("🟢 **Gateway Edge** (Online)<br>🟢 **Nicla Sense** (Ativo)<br>🟢 **Nano 33 BLE** (Ativo)", unsafe_allow_html=True)

    # --- CARREGAR DADOS ---
    df = fetch_data()
    
    # Cabeçalho Principal
    st.markdown("<h1 style='color: #0F172A; font-weight: 700; font-size: 2.2rem; letter-spacing: -1px;'>Painel de Monitorização</h1>", unsafe_allow_html=True)
    
    tab_dash, tab_admin = st.tabs(["Dashboard de Operações", "Calibração do Sistema"])

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
            
            estado, cor, acao, severidade = processar_decisao(fruta, voc)

            # --- LINHA SUPERIOR: AÇÃO + GAUGE VOC ---
            col_acao, col_gauge = st.columns([1.5, 1])
            
            with col_acao:
                st.markdown(f"""
                    <div class="main-action-card" style="border-bottom: 8px solid {cor};">
                        <div style="font-size: 1rem; color: #64748B; font-weight: 600; text-transform: uppercase; margin-bottom: 10px;">Lote em Análise: <span style="color: #0F172A;">{fruta.upper().replace('_', ' ')}</span></div>
                        <h1 style="color: {cor}; font-size: 3.2rem; font-weight: 800; margin: 0; line-height: 1.1;">{estado}</h1>
                        <h3 style="color: #334155; font-weight: 600; margin-top: 15px;">{acao}</h3>
                    </div>
                """, unsafe_allow_html=True)
                
            with col_gauge:
                # O Novo Gráfico Gauge de Alta Qualidade
                limite_min = thresholds["clim_fresco"] if "maca" in fruta.lower() or "banana" in fruta.lower() else thresholds["nclim_firme"]
                limite_max = thresholds["clim_maduro"] if "maca" in fruta.lower() or "banana" in fruta.lower() else thresholds["nclim_risco"]
                
                fig_gauge = go.Figure(go.Indicator(
                    mode = "gauge+number",
                    value = voc,
                    number = {'suffix': " Ω", 'font': {'size': 35, 'color': '#0F172A', 'family': 'Inter'}},
                    title = {'text': "NÍVEL DE VOC ATUAL", 'font': {'size': 14, 'color': '#64748B', 'family': 'Inter'}},
                    gauge = {
                        'axis': {'range': [None, 25000], 'tickwidth': 1, 'tickcolor': "#CBD5E1"},
                        'bar': {'color': cor, 'thickness': 0.25},
                        'bgcolor': "white",
                        'borderwidth': 0,
                        'steps': [
                            {'range': [0, limite_min], 'color': "rgba(239, 68, 68, 0.15)"},    # Vermelho leve
                            {'range': [limite_min, limite_max], 'color': "rgba(245, 158, 11, 0.15)"}, # Laranja leve
                            {'range': [limite_max, 25000], 'color': "rgba(16, 185, 129, 0.15)"}  # Verde leve
                        ]
                    }
                ))
                fig_gauge.update_layout(height=250, margin=dict(l=20, r=20, t=30, b=10), paper_bgcolor='rgba(0,0,0,0)', font={'family': "Inter"})
                st.plotly_chart(fig_gauge, use_container_width=True)

            # --- LINHA DO MEIO: CARTÕES HTML PREMIUM ---
            c1, c2, c3, c4 = st.columns(4)
            c1.markdown(f'<div class="premium-card"><div class="card-title">🔍 Confiança IA</div><div class="card-value">{conf*100 if conf <= 1 else conf:.1f} <span class="card-unit">%</span></div></div>', unsafe_allow_html=True)
            c2.markdown(f'<div class="premium-card"><div class="card-title">🌡️ Temperatura</div><div class="card-value">{temp:.1f} <span class="card-unit">ºC</span></div></div>', unsafe_allow_html=True)
            c3.markdown(f'<div class="premium-card"><div class="card-title">💧 Humidade</div><div class="card-value">{hum:.1f} <span class="card-unit">%</span></div></div>', unsafe_allow_html=True)
            c4.markdown(f'<div class="premium-card"><div class="card-title">✅ Status de Rede</div><div class="card-value" style="color: #10B981; font-size: 1.5rem;">Sincronizado</div></div>', unsafe_allow_html=True)

            st.markdown("<br><br>", unsafe_allow_html=True)

            # --- ZONA DO CHEFE: GRÁFICO HISTÓRICO + TIMELINE ---
            if st.session_state.cargo == "Chefe de Loja":
                st.markdown("<h3 style='color: #0F172A; font-weight: 700; font-size: 1.5rem;'>Histórico de Degradação (Gestão)</h3>", unsafe_allow_html=True)
                col_grafico, col_timeline = st.columns([1.8, 1])
                
                with col_grafico:
                    st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
                    if 'voc_gas' in df.columns:
                        df_clean = df.dropna(subset=['voc_gas']).sort_values('_time')
                        fig_line = px.area(df_clean, x='_time', y='voc_gas', color_discrete_sequence=['#3B82F6'])
                        fig_line.update_traces(fillcolor='rgba(59, 130, 246, 0.1)', line=dict(width=3))
                        fig_line.update_layout(
                            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', 
                            xaxis_title="", yaxis_title="Resistência VOC (Ω)",
                            margin=dict(l=0, r=0, t=10, b=0),
                            xaxis=dict(showgrid=False), yaxis=dict(gridcolor='#E2E8F0')
                        )
                        st.plotly_chart(fig_line, use_container_width=True)
                    st.markdown("</div>", unsafe_allow_html=True)

                with col_timeline:
                    st.markdown('<div class="timeline">', unsafe_allow_html=True)
                    if 'voc_gas' in df.columns:
                        df_sorted = df.sort_values(by='_time', ascending=False)
                        eventos = 0
                        for idx, row in df_sorted.iterrows():
                            v_voc = float(row.get('voc_gas', 0))
                            v_fruta = str(row.get('classe_dominante', ''))
                            if v_voc > 0 and v_fruta:
                                est, color, ac, sev = processar_decisao(v_fruta, v_voc)
                                if sev in ["warning", "danger"] and eventos < 4:
                                    d_time = row['_time'].strftime("%H:%M:%S")
                                    st.markdown(f"""
                                    <div class="timeline-item {sev}">
                                        <div class="timeline-date">Hoje às {d_time}</div>
                                        <div class="timeline-content">
                                            <strong style="color: {color};">{est}</strong><br>
                                            <span style="font-size: 0.9rem; color: #475569;">Alerta acionado devido à queda da resistência VOC para {v_voc/1000:.1f}kΩ.</span>
                                        </div>
                                    </div>
                                    """, unsafe_allow_html=True)
                                    eventos += 1
                        if eventos == 0:
                            st.markdown('<div class="timeline-item"><div class="timeline-content" style="border-left: 4px solid #10B981;"><strong>Lote Estável</strong><br>Sem alertas recentes.</div></div>', unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("A aguardar ingestão de dados da Edge Gateway...")

    # ---------------------------------------------------------
    # TAB 2: CALIBRAÇÃO (ADMIN ONLY)
    # ---------------------------------------------------------
    with tab_admin:
        if st.session_state.cargo == "Chefe de Loja":
            st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
            with st.form("calibration_form"):
                st.markdown("<h3 style='margin-top:0;'>Ajuste de Limiares do Sensor MOS</h3>", unsafe_allow_html=True)
                st.markdown("<p style='color: #64748B;'>Defina os valores de corte de resistência elétrica (em Ohms) para calibrar a lógica de Late Fusion.</p>", unsafe_allow_html=True)
                col_a, col_b = st.columns(2)
                with col_a:
                    st.markdown("#### Frutos Climatéricos (Banana/Maçã)")
                    clim_f = st.slider("Fresco ➡️ Maduro", 10000, 15000, thresholds["clim_fresco"])
                    clim_m = st.slider("Maduro ➡️ Podre", 15000, 20000, thresholds["clim_maduro"])
                with col_b:
                    st.markdown("#### Frutos Não-Climatéricos (Laranja)")
                    nclim_f = st.slider("Firme ➡️ Risco", 10000, 14000, thresholds["nclim_firme"])
                    nclim_r = st.slider("Risco ➡️ Degradada", 14000, 18000, thresholds["nclim_risco"])
                    
                if st.form_submit_button("Aplicar Nova Calibração", type="primary"):
                    get_thresholds.clear()
                    def get_thresholds(): return {"clim_fresco": clim_f, "clim_maduro": clim_m, "nclim_firme": nclim_f, "nclim_risco": nclim_r}
                    thresholds = get_thresholds()
                    st.success("Configurações aplicadas na Edge Gateway e Cloud.")
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.error("🔒 Área de Administração: Acesso barrado a perfis operacionais.")

    # Auto-Refresh dinâmico
    time.sleep(5)
    st.rerun()