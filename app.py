import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import plotly.express as px
import io
from PIL import Image

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Gestión OT - Roble", layout="wide")
UTC_OFFSET = 6 

# Carpetas necesarias
if not os.path.exists("fotos"):
    os.makedirs("fotos")

# --- ESTILO CSS AVANZADO ---
# Se agrega la regla para que el cursor siempre sea visible y parpadee en inputs
st.markdown("""
    <style>
    /* Estilo para los campos de entrada */
    .stTextInput > div > div > input, 
    .stTextArea > div > div > textarea,
    .stSelectbox > div > div > div {
        background-color: #e8f5e9 !important; 
        color: #1b5e20 !important;
        caret-color: #ff0000 !important; /* Cursor Rojo para que resalte */
    }
    
    /* Asegurar que el cursor parpadee al estar enfocado */
    input:focus, textarea:focus {
        border: 2px solid #2e7d32 !important;
        box-shadow: 0 0 5px rgba(46, 125, 50, 0.5) !important;
    }

    /* Reloj y estética general */
    .reloj-discreto {
        font-size: 16px; font-weight: bold; color: #ff0000;
        text-align: right; margin-bottom: 5px;
    }
    
    /* Resaltado del botón del menú seleccionado */
    div.stButton > button {
        width: 100%;
        border-radius: 5px;
        height: 3em;
        background-color: #f0f2f6;
    }
    </style>
    """, unsafe_allow_html=True)

# --- INICIALIZACIÓN DE NAVEGACIÓN ---
if 'menu_actual' not in st.session_state:
    st.session_state.menu_actual = "👥 Empleados"

def cambiar_menu(opcion):
    st.session_state.menu_actual = opcion

# --- FUNCIONES TÉCNICAS ---
def obtener_fecha_cr():
    return datetime.utcnow() - timedelta(hours=UTC_OFFSET)

def cargar_datos(archivo, columnas):
    if os.path.exists(archivo):
        try:
            df = pd.read_csv(archivo, dtype=str).fillna("")
            return df
        except:
            return pd.DataFrame(columns=columnas)
    return pd.DataFrame(columns=columnas)

def guardar_datos(df, archivo):
    df.to_csv(archivo, index=False)

# Carga inicial de datos
cols_ot = ["OT", "Empleado", "Descripcion", "Inicio", "Tipo", "Estado", "Fin", "Comentarios", "CorreoCopia", "TiempoAcumulado", "Foto"]
df_emp = cargar_datos("empleados.csv", ["Nombre", "Correo"])
df_ot = cargar_datos("ordenes.csv", cols_ot)

# --- MENÚ LATERAL SIEMPRE VISIBLE ---
with st.sidebar:
    st.title("Gestión Roble")
    st.divider()
    
    # Botones que actúan como menú con resaltado
    opciones = ["👥 Empleados", "📝 Nueva OT", "🔍 Cierre y Consulta", "📊 Dashboard"]
    
    for opcion in opciones:
        # Si la opción es la actual, el botón cambia de color (estilo primario)
        if st.session_state.menu_actual == opcion:
            st.button(opcion, on_click=cambiar_menu, args=(opcion,), type="primary", key=f"btn_{opcion}")
        else:
            st.button(opcion, on_click=cambiar_menu, args=(opcion,), type="secondary", key=f"btn_{opcion}")
    
    st.divider()
    st.info(f"Usuario Activo: Operaciones\nCR: {obtener_fecha_cr().strftime('%d/%m/%Y')}")

# --- RENDERIZADO DE SECCIONES ---
menu = st.session_state.menu_actual

if menu == "👥 Empleados":
    st.header("👥 Gestión de Operarios")
    # ... (Aquí va tu código de empleados ya funcional) ...
    st.table(df_emp)

elif menu == "📝 Nueva OT":
    st.header("📝 Apertura de Orden de Trabajo")
    # ... (Aquí va tu código de Nueva OT ya funcional con file_uploader) ...

elif menu == "🔍 Cierre y Consulta":
    st.header("🔍 Gestión de Cierre y Consulta")
    # ... (Aquí va tu código de Cierre con visualización de foto) ...

elif menu == "📊 Dashboard":
    st.header("📊 Dashboard de Rendimiento")
    if df_ot.empty:
        st.info("No hay datos suficientes.")
    else:
        df_d = df_ot.copy()
        df_d['Segundos'] = pd.to_numeric(df_d['TiempoAcumulado'], errors='coerce').fillna(0)
        df_d['Horas'] = round(df_d['Segundos'] / 3600, 2)
        fig = px.bar(df_d, x='OT', y='Horas', color='Tipo', title="Uso de tiempo por OT")
        st.plotly_chart(fig, use_container_width=True)
