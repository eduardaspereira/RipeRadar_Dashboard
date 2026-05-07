import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from influxdb_client import InfluxDBClient
from datetime import datetime, timezone
import time

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="RipeRadar OS | Edge AI", page_icon="🍎", layout="wide", initial_sidebar_state="expanded")

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

# --- 3. CSS DARK MODE PREMIUM ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;700&display=swap');
    
    /* Fundo Dark Mode Premium (Azul Noite Profundo) */
    .stApp { background-color: #0B0F19; color: #F8FAFC; font-family: 'Inter', sans-serif; }
    
    /* Ocultar elementos nativos */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Cartões Premium Dark com efeito Glassmorphism subtil */
    .premium-card {
        background: linear-gradient(145deg, #111827 0%, #0F172A 100%);
        border-radius: 16px; padding: 24px;
        border: 1px solid rgba(56, 189, 248, 0.1);
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
    }
    .card-title { color: #94A3B8; font-size: 0.85rem; font-weight: 600; text-transform: uppercase; margin-bottom: 8px; letter-spacing: 0.5px; }
    .card-value { color: #F8FAFC; font-size: 2.2rem; font-weight: 700; display: flex; align-items: baseline; gap: 8px; font-family: 'JetBrains Mono', monospace;}
    .card-unit { color: #64748B; font-size: 1rem; font-weight: 500; font-family: 'Inter', sans-serif;}
    
    /* Action Card Principal */
    .main-action-card {
        background: linear-gradient(180deg, #1E293B 0%, #0F172A 100%);
        border-radius: 20px; padding: 35px; text-align: center;
        border: 1px solid rgba(255, 255, 255, 0.05); margin-bottom: 25px; box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
    }
    
    /* Timeline Estilo Hacker/Corporate */
    .timeline { border-left: 2px solid #334155; margin-left: 15px; padding-left: 30px; position: relative;}
    .timeline-item { position: relative; margin-bottom: 30px; }
    .timeline-item::before {
        content: ''; position: absolute; left: -39px; top: 4px; width: 16px; height: 16px;
        border-radius: 50%; background: #0F172A; border: 3px solid #38BDF8; box-shadow: 0 0 10px rgba(56, 189, 248, 0.4);
    }
    .timeline-item.warning::before { border-color: #FBBF24; box-shadow: 0 0 10px rgba(251, 191, 36, 0.4); }
    .timeline-item.danger::before { border-color: #EF4444; box-shadow: 0 0 10px rgba(239, 68, 68, 0.4); }
    .timeline-date { font-size: 0.85rem; color: #94A3B8; font-weight: 600; margin-bottom: 8px; font-family: 'JetBrains Mono', monospace;}
    .timeline-content { background-color: rgba(30, 41, 59, 0.5); padding: 20px; border-radius: 12px; border: 1px solid #334155;}
    
    /* Login Screen Centrado */
    .login-wrapper {
        background: #111827; padding: 50px 40px; border-radius: 24px;
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7); text-align: center;
        border: 1px solid #1E293B;
    }
    
    /* Customizando os Inputs e Botões do Streamlit */
    div[data-baseweb="input"] { background-color: #0F172A; border-color: #334155; }
    div[data-baseweb="input"] > input { color: #F8FAFC; }
    
    /* Abas Premium */
    .stTabs [data-baseweb="tab-list"] { border-bottom: 2px solid #1E293B; gap: 24px; }
    .stTabs [data-baseweb="tab"] { color: #64748B; font-weight: 600; font-size: 1.05rem; padding-bottom: 12px;}
    .stTabs [aria-selected="true"] { color: #38BDF8 !important; border-bottom: 3px solid #38BDF8 !important; background: transparent;}
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
    
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("""
        <div class="login-wrapper">
            <h1 style='font-size: 4rem; margin: 0; line-height: 1;'>🍎</h1>
            <h2 style='color: #F8FAFC; font-weight: 700; margin-top: 15px; font-size: 2rem;'>RipeRadar OS</h2>
            <p style='color: #94A3B8; margin-bottom: 35px; font-size: 0.95rem;'>Sistema Integrado de Monitorização IoT</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<div style='margin-top: -20px; position: relative; z-index: 10;'>", unsafe_allow_html=True)
        st.text_input("Identificação de Utilizador", key="user_input")
        st.text_input("Código de Acesso", type="password", key="pass_input")
        st.markdown("<br>", unsafe_allow_html=True)
        st.button("Iniciar Sessão Segura", on_click=verificar_login, use_container_width=True, type="primary")
        st.markdown("</div>", unsafe_allow_html=True)

# ==========================================
# ECRÃ 2: DASHBOARD (LOGADO)
# ==========================================
else:
    # --- MENU LATERAL PREMIUM ---
    with st.sidebar:
        st.markdown(f"""
            <div style="background: rgba(15, 23, 42, 0.5); padding: 20px; border-radius: 12px; border: 1px solid #1E293B; text-align: center; margin-bottom: 20px;">
                <h3 style="margin: 0; color: #94A3B8; font-size: 0.9rem; text-transform: uppercase;">Operador Ativo</h3>
                <h2 style="margin: 5px 0 15px 0; color: #38BDF8;">{st.session_state.cargo}</h2>
            </div>
        """, unsafe_allow_html=True)
        
        st.button("Terminar Sessão", on_click=logout, use_container_width=True)
        
        st.markdown("<hr style='border-color: #1E293B;'>", unsafe_allow_html=True)
        
        # Secção de Saúde do Sistema (UI Apenas)
        st.markdown("<h4 style='color: #F8FAFC; font-size: 1rem; margin-bottom: 15px;'>⚙️ Diagnóstico de Sistema</h4>", unsafe_allow_html=True)
        
        st.markdown("<p style='font-size: 0.8rem; color: #94A3B8; margin-bottom: 2px;'>Carga CPU (Edge Gateway)</p>", unsafe_allow_html=True)
        st.progress(24)
        
        st.markdown("<p style='font-size: 0.8rem; color: #94A3B8; margin-bottom: 2px; margin-top: 10px;'>Sinal BLE (Nicla Sense)</p>", unsafe_allow_html=True)
        st.progress(85)
        
        st.markdown("<hr style='border-color: #1E293B;'>", unsafe_allow_html=True)
        
        # Toggle para Live Refresh
        st.markdown("<h4 style='color: #F8FAFC; font-size: 1rem; margin-bottom: 10px;'>🔄 Controlo de Telemetria</h4>", unsafe_allow_html=True)
        auto_refresh = st.toggle("Sincronização Live (5s)", value=True, help="Desligue para ajustar configurações sem interrupções.")

    # --- CARREGAR DADOS ---
    df = fetch_data()
    
    st.markdown("<h1 style='font-weight: 700; font-size: 2.2rem; margin-bottom: 20px;'>Centro de Comando Analítico</h1>", unsafe_allow_html=True)
    
    # --- ABAS (O Operador agora TAMBÉM tem Calibração) ---
    if st.session_state.cargo == "Chefe de Loja":
        tab_dash, tab_time, tab_admin = st.tabs(["📊 Monitorização em Tempo Real", "⏱️ Timeline Histórica", "⚙️ Calibração de IA"])
    else:
        tab_dash, tab_admin = st.tabs(["📊 Monitorização em Tempo Real", "⚙️ Calibração de IA"])

    # ---------------------------------------------------------
    # TAB 1: DASHBOARD (IGUAL PARA AMBOS)
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
                        <div style="font-size: 1rem; color: #94A3B8; font-weight: 600; text-transform: uppercase; margin-bottom: 10px; letter-spacing: 1px;">Alvo Visualizado: <span style="color: #F8FAFC;">{fruta.upper().replace('_', ' ')}</span></div>
                        <h1 style="color: {cor}; font-size: 3.5rem; font-weight: 800; margin: 0; line-height: 1.1;">{estado}</h1>
                        <h3 style="color: #E2E8F0; font-weight: 400; margin-top: 15px;">Ação Recomendada: <b>{acao.split(': ')[1] if ': ' in acao else acao}</b></h3>
                    </div>
                """, unsafe_allow_html=True)
                
            with col_gauge:
                limite_min = thresholds["clim_fresco"] if "maca" in fruta.lower() or "banana" in fruta.lower() else thresholds["nclim_firme"]
                limite_max = thresholds["clim_maduro"] if "maca" in fruta.lower() or "banana" in fruta.lower() else thresholds["nclim_risco"]
                
                fig_gauge = go.Figure(go.Indicator(
                    mode = "gauge+number", value = voc,
                    number = {'suffix': " Ω", 'font': {'size': 35, 'color': '#F8FAFC', 'family': 'JetBrains Mono'}},
                    title = {'text': "RESISTÊNCIA DO SENSOR (VOC)", 'font': {'size': 13, 'color': '#94A3B8', 'family': 'Inter'}},
                    gauge = {
                        'axis': {'range': [None, 25000], 'tickwidth': 2, 'tickcolor': "#334155"},
                        'bar': {'color': cor, 'thickness': 0.25},
                        'bgcolor': "#0F172A", 'borderwidth': 0,
                        'steps': [
                            {'range': [0, limite_min], 'color': "rgba(239, 68, 68, 0.15)"},    
                            {'range': [limite_min, limite_max], 'color': "rgba(245, 158, 11, 0.15)"}, 
                            {'range': [limite_max, 25000], 'color': "rgba(16, 185, 129, 0.15)"}  
                        ]
                    }
                ))
                fig_gauge.update_layout(height=260, margin=dict(l=30, r=30, t=30, b=10), paper_bgcolor='rgba(0,0,0,0)', font={'family': "Inter"})
                st.plotly_chart(fig_gauge, use_container_width=True)

            # --- LINHA DO MEIO: CARTÕES PREMIUM ---
            c1, c2, c3, c4 = st.columns(4)
            c1.markdown(f'<div class="premium-card"><div class="card-title">🎯 IA Confidence</div><div class="card-value">{conf*100 if conf <= 1 else conf:.1f} <span class="card-unit">%</span></div></div>', unsafe_allow_html=True)
            c2.markdown(f'<div class="premium-card"><div class="card-title">🌡️ Temperatura</div><div class="card-value">{temp:.1f} <span class="card-unit">ºC</span></div></div>', unsafe_allow_html=True)
            c3.markdown(f'<div class="premium-card"><div class="card-title">💧 Humidade</div><div class="card-value">{hum:.1f} <span class="card-unit">%</span></div></div>', unsafe_allow_html=True)
            c4.markdown(f'<div class="premium-card"><div class="card-title">⏱️ Latência MQTT</div><div class="card-value" style="color: #38BDF8;">124 <span class="card-unit">ms</span></div></div>', unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # --- GRÁFICO DE HISTÓRICO MELHORADO ---
            st.markdown("<h3 style='color: #F8FAFC; font-weight: 600; font-size: 1.3rem; margin-bottom: 15px;'>Evolução Dinâmica de Emissões Voláteis (Última Hora)</h3>", unsafe_allow_html=True)
            st.markdown("<div class='premium-card' style='padding: 10px 20px;'>", unsafe_allow_html=True)
            if 'voc_gas' in df.columns:
                df_clean = df.dropna(subset=['voc_gas']).sort_values('_time')
                
                # Gráfico Avançado Plotly
                fig_line = go.Figure()
                fig_line.add_trace(go.Scatter(
                    x=df_clean['_time'], y=df_clean['voc_gas'],
                    mode='lines+markers',
                    line=dict(color='#38BDF8', width=3, shape='spline'), # Spline para curvas suaves
                    marker=dict(size=6, color='#0F172A', line=dict(width=2, color='#38BDF8')),
                    fill='tozeroy', fillcolor='rgba(56, 189, 248, 0.1)',
                    name='Resistência VOC',
                    hovertemplate='<b>%{x|%H:%M:%S}</b><br>VOC: %{y:.0f} Ω<extra></extra>'
                ))
                
                fig_line.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', 
                    xaxis_title="", yaxis_title="Resistência (Ohms)",
                    margin=dict(l=10, r=10, t=20, b=10),
                    hovermode="x unified",
                    xaxis=dict(showgrid=False, color="#94A3B8"), 
                    yaxis=dict(gridcolor='#1E293B', color="#94A3B8", zerolinecolor='#1E293B')
                )
                st.plotly_chart(fig_line, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
            
        else:
            st.info("A aguardar ingestão de pacotes MQTT...")

    # ---------------------------------------------------------
    # ABA 2: TIMELINE (EXCLUSIVA CHEFE DE LOJA)
    # ---------------------------------------------------------
    if st.session_state.cargo == "Chefe de Loja":
        with tab_time:
            st.markdown("<h3 style='margin-bottom: 5px;'>Auditoria de Eventos e Alertas Críticos</h3>", unsafe_allow_html=True)
            st.markdown("<p style='color: #94A3B8; margin-bottom: 30px;'>Registo imutável gerado pela heurística de fusão da Edge Gateway.</p>", unsafe_allow_html=True)
            
            st.markdown('<div class="timeline">', unsafe_allow_html=True)
            if not df.empty and 'voc_gas' in df.columns:
                df_sorted = df.sort_values(by='_time', ascending=False)
                eventos = 0
                for idx, row in df_sorted.iterrows():
                    v_voc = float(row.get('voc_gas', 0))
                    v_fruta = str(row.get('classe_dominante', ''))
                    if v_voc > 0 and v_fruta:
                        est, color, ac, sev = processar_decisao(v_fruta, v_voc)
                        if sev in ["warning", "danger"] and eventos < 10:
                            d_time = row['_time'].strftime("%H:%M:%S")
                            st.markdown(f"""
                            <div class="timeline-item {sev}">
                                <div class="timeline-date">REGISTO LOG: {d_time}</div>
                                <div class="timeline-content">
                                    <strong style="color: {color}; font-size: 1.15rem;">{est}</strong><br>
                                    <div style="margin-top: 8px; color: #E2E8F0;">
                                        📦 Produto Identificado: <span style="color: #38BDF8; font-weight: 600;">{v_fruta.replace('_', ' ').title()}</span><br>
                                        🧪 Leitura Sensorial: <span style="font-family: 'JetBrains Mono'; font-size: 0.95rem;">{v_voc/1000:.2f} kΩ</span>
                                    </div>
                                    <div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid #334155;">
                                        <span style="color: #94A3B8; font-size: 0.85rem;">Protocolo de Segurança:</span> 
                                        <strong style="color: #F8FAFC;">{ac.split(': ')[1] if ': ' in ac else ac}</strong>
                                    </div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                            eventos += 1
                if eventos == 0:
                    st.markdown('<div class="timeline-item"><div class="timeline-content" style="border-left: 4px solid #10B981;"><strong>✅ Diagnóstico Perfeito</strong><br>Nenhum desvio dos parâmetros basais de qualidade detetado.</div></div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

    # ---------------------------------------------------------
    # ABA DE CALIBRAÇÃO (AGORA PARA AMBOS, MAS CHEFE PODE TER MAIS PODER NO FUTURO)
    # ---------------------------------------------------------
    with tab_admin:
        st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
        with st.form("calibration_form"):
            st.markdown("<h3 style='margin-top:0;'>Parâmetros do Modelo de Late Fusion</h3>", unsafe_allow_html=True)
            st.markdown("<p style='color: #94A3B8;'>Sintonize a janela de resistência do sensor BME688. <i>Recomendado suspender o Live Refresh antes de operar.</i></p>", unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("#### 🍌 Fenologia Climatérica (Banana/Maçã)")
                clim_f = st.slider("Transição Verde ➡️ Maduro", 10000, 15000, thresholds["clim_fresco"])
                clim_m = st.slider("Transição Maduro ➡️ Podre", 15000, 20000, thresholds["clim_maduro"])
            with col_b:
                st.markdown("#### 🍊 Fenologia Não-Climatérica (Laranja)")
                nclim_f = st.slider("Transição Firme ➡️ Risco", 10000, 14000, thresholds["nclim_firme"])
                nclim_r = st.slider("Transição Risco ➡️ Degradada", 14000, 18000, thresholds["nclim_risco"])
                
            st.markdown("<br>", unsafe_allow_html=True)
            if st.form_submit_button("Atualizar Algoritmo na Edge", type="primary"):
                get_thresholds.clear()
                def get_thresholds(): return {"clim_fresco": clim_f, "clim_maduro": clim_m, "nclim_firme": nclim_f, "nclim_risco": nclim_r}
                thresholds = get_thresholds()
                st.success("Novos limiares injetados com sucesso. Próxima inferência usará as novas regras.")
        st.markdown("</div>", unsafe_allow_html=True)

    # --- AUTO REFRESH DINÂMICO ---
    # Só faz refresh se a checkbox (toggle) estiver ativada!
    if auto_refresh:
        time.sleep(5)
        st.rerun()