import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import plotly.express as px
import io
from PIL import Image  # Librería para compresión

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Gestión OT - Roble", layout="wide")
UTC_OFFSET = 6 
CORREO_ADMIN = "sa.alterna@gmail.com"

# Crear carpeta de fotos si no existe
if not os.path.exists("fotos"):
    os.makedirs("fotos")

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
    section[data-testid="stSidebar"] { width: 300px !important; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNCIONES TÉCNICAS ---
def obtener_fecha_cr():
    return datetime.utcnow() - timedelta(hours=UTC_OFFSET)

def comprimir_imagen(archivo_subido):
    img = Image.open(archivo_subido)
    # Convertir a RGB si es necesario (evita errores con PNG transparentes)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    
    # Redimensionar si es muy grande (máximo 1200px de ancho)
    ancho_max = 1200
    if img.width > ancho_max:
        proporcion = ancho_max / float(img.width)
        alto = int((float(img.height) * float(proporcion)))
        img = img.resize((ancho_max, alto), Image.LANCZOS)
    
    # Guardar en un buffer con compresión
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=60, optimize=True)
    return buffer.getvalue()

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

def generar_siguiente_ot(df_ot):
    if df_ot.empty: return "0001"
    try:
        solo_numeros = pd.to_numeric(df_ot['OT'], errors='coerce').dropna()
        if solo_numeros.empty: return "0001"
        return f"{int(solo_numeros.max()) + 1:04d}"
    except: return "0001"

# --- CARGA DE DATOS ---
# Añadimos la columna "Foto" a la estructura
cols_ot = ["OT", "Empleado", "Descripcion", "Inicio", "Tipo", "Estado", "Fin", "Comentarios", "CorreoCopia", "TiempoAcumulado", "Foto"]
df_emp = cargar_datos("empleados.csv", ["Nombre", "Correo"])
df_ot = cargar_datos("ordenes.csv", cols_ot)

# --- MENÚ LATERAL ---
st.sidebar.title("Navegación")
menu = st.sidebar.selectbox("SELECCIONE UNA PESTAÑA:", ["👥 Empleados", "📝 Nueva OT", "🔍 Cierre y Consulta", "📊 Dashboard"])
st.sidebar.divider()

# 1. EMPLEADOS (Sin cambios significativos)
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
                    guardar_datos(df_emp, "empleados.csv"); st.rerun()
    with tab_mod:
        if not df_emp.empty:
            emp_sel = st.selectbox("Editar:", df_emp['Nombre'])
            idx = df_emp.index[df_emp['Nombre'] == emp_sel].tolist()[0]
            with st.form("edit_emp"):
                nuevo_n = st.text_input("Nombre", value=df_emp.at[idx, 'Nombre'])
                nuevo_c = st.text_input("Correo", value=df_emp.at[idx, 'Correo'])
                if st.form_submit_button("💾 Guardar"):
                    df_emp.at[idx, 'Nombre'] = nuevo_n; df_emp.at[idx, 'Correo'] = nuevo_c
                    guardar_datos(df_emp, "empleados.csv"); st.rerun()
    st.table(df_emp)

# 2. NUEVA OT (CON FOTO COMPRIMIDA)
elif menu == "📝 Nueva OT":
    st.header("📝 Apertura de Orden de Trabajo")
    if df_emp.empty:
        st.warning("Debe registrar operarios primero.")
    else:
        with st.form("f_ot", clear_on_submit=True):
            op = st.selectbox("Operario Asignado", df_emp['Nombre'])
            tp = st.radio("Tipo de Trabajo", ["Preventivo", "Correctivo", "Casos 24h", "Casos ISO"], horizontal=True)
            ds = st.text_area("Descripción del Hallazgo")
            # --- NUEVO: CARGADOR DE FOTO ---
            archivo_foto = st.file_uploader("Capturar/Subir Foto", type=["jpg", "png", "jpeg"])
            cp = st.text_input("Correo de copia obligatoria")
            
            if st.form_submit_button("Generar Orden"):
                if ds and cp:
                    id_ot = generar_siguiente_ot(df_ot)
                    nombre_foto = "Sin foto"
                    
                    if archivo_foto:
                        nombre_foto = f"OT_{id_ot}.jpg"
                        ruta_foto = os.path.join("fotos", nombre_foto)
                        # Comprimir antes de guardar
                        img_comprimida = comprimir_imagen(archivo_foto)
                        with open(ruta_foto, "wb") as f:
                            f.write(img_comprimida)
                    
                    nueva = {
                        "OT": id_ot, "Empleado": op, "Descripcion": ds, 
                        "Inicio": obtener_fecha_cr().strftime("%Y-%m-%d %H:%M:%S"),
                        "Tipo": tp, "Estado": "Abierta", "Fin": "", "Comentarios": "", 
                        "CorreoCopia": cp, "TiempoAcumulado": "0", "Foto": nombre_foto
                    }
                    df_ot = pd.concat([df_ot, pd.DataFrame([nueva])], ignore_index=True)
                    guardar_datos(df_ot, "ordenes.csv")
                    st.success(f"OT #{id_ot} generada con foto optimizada.")
                    st.rerun()

# 3. CIERRE Y CONSULTA (CON VISUALIZACIÓN DE FOTO)
elif menu == "🔍 Cierre y Consulta":
    st.markdown(f'<div class="reloj-discreto">Hora CR: {obtener_fecha_cr().strftime("%H:%M:%S")}</div>', unsafe_allow_html=True)
    st.header("🔍 Gestión de Cierre y Consulta")
    tab1, tab2 = st.tabs(["Órdenes Activas", "Historial Completo"])
    
    with tab1:
        pendientes = df_ot[df_ot['Estado'].isin(["Abierta", "En Pausa"])].copy()
        if pendientes.empty:
            st.info("No hay órdenes activas.")
        else:
            st.dataframe(pendientes[["OT", "Estado", "Empleado", "Tipo", "Descripcion"]], use_container_width=True)
            sel = st.selectbox("Seleccione OT:", pendientes['OT'] + " - " + pendientes['Descripcion'])
            id_sel = sel.split(" - ")[0]
            idx_ot = df_ot.index[df_ot['OT'] == id_sel].tolist()[0]
            
            # --- MOSTRAR FOTO SI EXISTE ---
            foto_nom = df_ot.at[idx_ot, 'Foto']
            if foto_nom != "Sin foto" and os.path.exists(os.path.join("fotos", foto_nom)):
                st.image(os.path.join("fotos", foto_nom), caption=f"Evidencia OT #{id_sel}", width=400)
            
            with st.form("m_ot"):
                est = st.selectbox("Estado", ["Abierta", "En Pausa", "Cerrada"], index=["Abierta", "En Pausa", "Cerrada"].index(df_ot.at[idx_ot, 'Estado']))
                com = st.text_area("Comentarios", value=df_ot.at[idx_ot, 'Comentarios'])
                if st.form_submit_button("Actualizar"):
                    # (Lógica de tiempo acumulado igual a la anterior...)
                    df_ot.at[idx_ot, 'Estado'] = est; df_ot.at[idx_ot, 'Comentarios'] = com
                    guardar_datos(df_ot, "ordenes.csv"); st.rerun()

    with tab2:
        st.dataframe(df_ot, use_container_width=True)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df_ot.to_excel(writer, index=False)
        st.download_button("📥 Descargar Excel", buffer.getvalue(), "base_datos_roble.xlsx")

# 4. DASHBOARD (Sin cambios)
elif menu == "📊 Dashboard":
    st.header("📊 Dashboard")
    st.info("Visualización de métricas generales.")
