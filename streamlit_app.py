import streamlit as st
import pandas as pd
import plotly.express as px
from influxdb_client import InfluxDBClient
from datetime import datetime
import time

st.set_page_config(page_title="RipeRadar OS v2.6 (InfluxDB)", layout="wide")

# Lidas do Streamlit Secrets
INFLUX_URL = st.secrets["INFLUX_URL"]
INFLUX_TOKEN = st.secrets["INFLUX_TOKEN"]
INFLUX_ORG = st.secrets["INFLUX_ORG"]
INFLUX_BUCKET = st.secrets["INFLUX_BUCKET"]

@st.cache_resource
def get_influx_client():
    return InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)

def fetch_data():
    client = get_influx_client()
    query_api = client.query_api()
    
    # Busca os últimos 5 minutos de dados. Pivot reorganiza as colunas corretamente.
    query = f"""
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: -5m)
      |> filter(fn: (r) => r["_measurement"] == "mqtt_consumer")
      |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
    """
    try:
        df = query_api.query_data_frame(query)
        return df if isinstance(df, pd.DataFrame) else pd.DataFrame()
    except Exception as e:
        st.error(f"Erro na Base de Dados: {e}")
        return pd.DataFrame()

def processar_decisao(classe, voc):
    if any(f in str(classe).lower() for f in ["maca", "banana"]):
        if voc < 13000: return "VERDE / FRESCO", "#00ffcc", "CONFORME"
        elif voc <= 17000: return "MADURO / ÓTIMO", "#ffcc00", "PROMOÇÃO"
        else: return "PODRE", "#ff4b4b", "RETIRAR"
    else:
        if voc < 13000: return "FIRME / BOA", "#00ffcc", "CONFORME"
        elif voc <= 16000: return "RISCO", "#ff9900", "VIGILÂNCIA"
        else: return "DEGRADADA", "#ff4b4b", "REJEITAR"

st.title("🍎 RipeRadar :: Cloud Intelligence")
df = fetch_data()

if not df.empty:
    latest = df.iloc[-1]
    
    # Mapeamento CORRIGIDO de acordo com o mock_gateway.py
    voc = latest.get('voc_gas', 0)
    fruta = latest.get('classe_dominante', 'Desconhecido')
    conf = latest.get('confianca', 0)
    
    estado, cor, acao = processar_decisao(fruta, voc)

    st.markdown(f"""
        <div style="background:{cor}22; border:2px solid {cor}; padding:20px; border-radius:15px; text-align:center;">
            <h1 style="color:{cor}; margin:0;">{estado}</h1>
            <h3 style="color:white; margin:0;">{acao} | Deteção: {str(fruta).upper()} | Confiança: {conf}%</h3>
        </div>
    """, unsafe_allow_html=True)

    st.subheader("📊 Evolução Histórica de VOC")
    # Gráfico de linha usando o tempo real e a variável voc_gas
    fig = px.line(df, x='_time', y='voc_gas', template="plotly_dark", markers=True)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("À espera de dados no InfluxDB Cloud... Garante que o Telegraf no Raspberry Pi está a correr.")

time.sleep(5)
st.rerun()