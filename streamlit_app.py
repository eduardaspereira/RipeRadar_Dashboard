import streamlit as st
import pandas as pd
import plotly.express as px
from influxdb_client import InfluxDBClient
from datetime import datetime
import time

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="RipeRadar OS v2.6 (InfluxDB)", layout="wide")

# --- CREDENCIAIS SEGURAS ---
INFLUX_URL = st.secrets["INFLUX_URL"]
INFLUX_TOKEN = st.secrets["INFLUX_TOKEN"]
INFLUX_ORG = st.secrets["INFLUX_ORG"]
INFLUX_BUCKET = st.secrets["INFLUX_BUCKET"]

# --- LÓGICA DE DADOS (INFLUXDB) ---
@st.cache_resource
def get_influx_client():
    return InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)

def fetch_data():
    client = get_influx_client()
    query_api = client.query_api()
    
    query = f"""
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: -10m)
      |> filter(fn: (r) => r["_measurement"] == "mqtt_consumer")
      |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
    """
    try:
        df = query_api.query_data_frame(query)
        return df if isinstance(df, pd.DataFrame) else pd.DataFrame()
    except Exception as e:
        st.error(f"Erro na Base de Dados: {e}")
        return pd.DataFrame()

# --- LÓGICA DE DECISÃO ---
def processar_decisao(classe, voc):
    # NOTA: Ajustei os limites porque os teus novos valores rondam os 15000+
    # Calibra isto depois com dados reais em laboratório!
    if any(f in str(classe).lower() for f in ["maca", "banana"]):
        if voc < 13000: return "VERDE / FRESCO", "#00ffcc", "CONFORME"
        elif voc <= 16000: return "MADURO / ÓTIMO", "#ffcc00", "PROMOÇÃO"
        else: return "PODRE", "#ff4b4b", "RETIRAR"
    else:
        if voc < 13000: return "FIRME / BOA", "#00ffcc", "CONFORME"
        elif voc <= 16000: return "RISCO", "#ff9900", "VIGILÂNCIA"
        else: return "DEGRADADA", "#ff4b4b", "REJEITAR"

# --- INTERFACE ---
st.title("🍎 RipeRadar :: Cloud Intelligence")
df = fetch_data()

if not df.empty:
    latest = df.iloc[-1]
    
    # Novos nomes mapeados diretamente do JSON do Telegraf
    voc = latest.get('voc_gas', 0)
    fruta = latest.get('classe_dominante', 'Desconhecido')
    # O JSON envia 0.85, multiplicamos por 100 para percentagem
    conf = latest.get('confianca', 0) * 100 
    
    estado, cor, acao = processar_decisao(fruta, voc)

    # Widget de Alerta
    st.markdown(f"""
        <div style="background:{cor}22; border:2px solid {cor}; padding:20px; border-radius:15px; text-align:center;">
            <h1 style="color:{cor}; margin:0;">{estado}</h1>
            <h3 style="color:white; margin:0;">Fruta Detetada: {fruta}</h3>
            <h4 style="color:white; margin:0;">{acao} | Confiança: {conf:.1f}% | VOC: {voc}</h4>
        </div>
    """, unsafe_allow_html=True)

    # Gráficos de Histórico Real
    st.subheader("📊 Evolução Histórica (VOC Gas)")
    # Usar a nova coluna voc_gas
    if 'voc_gas' in df.columns:
        fig = px.line(df, x='_time', y='voc_gas', template="plotly_dark")
        st.plotly_chart(fig, width="stretch")
    else:
        st.warning("A aguardar dados da métrica VOC...")
else:
    st.info("À espera de dados no InfluxDB Cloud...")

time.sleep(5)
st.rerun()