import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import plotly.express as px
import io

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Gestión OT - Roble", layout="wide")
UTC_OFFSET = 6 
CORREO_ADMIN = "sa.alterna@gmail.com"

# --- ESTILO PERSONALIZADO ---
st.markdown("""
    <style>
    .stTextInput > div > div > input, .stTextArea > div > div > textarea,
    .stSelectbox > div > div > div, .stMultiSelect > div > div {
        background-color: #e8f5e9 !important; color: #1b5e20 !important;
    }
    .reloj-discreto {
        font-size: 16px; font-weight: bold; color: #ff0000;
        text-align: right; margin-bottom: 5px;
    }
    /* Asegurar que el sidebar sea visible y estático */
    section[data-testid="stSidebar"] {
        width: 300px !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- FUNCIONES DE PERSISTENCIA ---
def cargar_datos(archivo, columnas):
    if os.path.exists(archivo):
        try:
            df = pd.read_csv(archivo, dtype=str)
            for col in columnas:
                if col not in df.columns:
                    df[col] = "0" if "Tiempo" in col else ""
            return df
        except:
            return pd.DataFrame(columns=columnas)
    return pd.DataFrame(columns=columnas)

def guardar_datos(df, archivo):
    df.to_csv(archivo, index=False)

# --- FUNCIONES TÉCNICAS ---
def obtener_fecha_cr():
    return datetime.utcnow() - timedelta(hours=UTC_OFFSET)

def generar_siguiente_ot(df_ot):
    if df_ot.empty: return "0001"
    try:
        solo_numeros = pd.to_numeric(df_ot['OT'], errors='coerce').dropna()
        if solo_numeros.empty: return "0001"
        return f"{int(solo_numeros.max()) + 1:04d}"
    except: return "0001"

def enviar_correo(dest_op, dest_copia, asunto, cuerpo):
    try:
        user = st.secrets["emails"]["sender_user"]
        password = st.secrets["emails"]["sender_password"]
        msg = MIMEMultipart()
        msg['From'] = user
        destinatarios = [dest_op, CORREO_ADMIN, dest_copia]
        msg['To'] = ", ".join(destinatarios)
        msg['Subject'] = asunto
        msg.attach(MIMEText(cuerpo, 'plain'))
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(user, password)
        server.sendmail(user, destinatarios, msg.as_string())
        server.quit()
        return True
    except: return False

# --- CARGA DE DATOS ---
cols_ot = ["OT", "Empleado", "Descripcion", "Inicio", "Tipo", "Estado", "Fin", "Comentarios", "CorreoCopia", "TiempoAcumulado"]
df_emp = cargar_datos("empleados.csv", ["Nombre", "Correo"])
df_ot = cargar_datos("ordenes.csv", cols_ot)

# --- MENÚ PERMANENTE EN LA BARRA LATERAL ---
# Al estar definido al inicio y fuera de cualquier 'if', siempre será visible.
st.sidebar.title("Navegación")
menu = st.sidebar.selectbox(
    "SELECCIONE UNA PESTAÑA:", 
    ["👥 Empleados", "📝 Nueva OT", "🔍 Cierre y Consulta", "📊 Dashboard"]
)
st.sidebar.divider()

# 1. GESTIÓN DE EMPLEADOS
if menu == "👥 Empleados":
    st.header("👥 Gestión de Operarios")
    tab_reg, tab_mod = st.tabs(["Registrar Nuevo", "Modificar / Eliminar"])
    
    with tab_reg:
        with st.form("add_emp", clear_on_submit=True):
            n = st.text_input("Nombre Completo")
            c = st.text_input("Correo Electrónico")
            if st.form_submit_button("Registrar"):
                if n and c:
                    df_emp = pd.concat([df_emp, pd.DataFrame([{"Nombre":n,"Correo":c}])], ignore_index=True)
                    guardar_datos(df_emp, "empleados.csv")
                    st.success("Operario registrado.")
                    st.rerun()
    
    with tab_mod:
        if not df_emp.empty:
            emp_sel =
