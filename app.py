import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import plotly.express as px
import io
from PIL import Image

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Gestión OT - Roble", layout="wide")
UTC_OFFSET = 6 
CORREO_ADMIN = "sa.alterna@gmail.com"

# Carpetas necesarias
if not os.path.exists("fotos"):
    os.makedirs("fotos")

# --- ESTILO CSS (CURSOR PARPADEANTE Y VISIBILIDAD) ---
st.markdown("""
    <style>
    /* Forzar el cursor (caret) a ser visible y de color rojo brillante */
    input, textarea {
        caret-color: #ff0000 !important;
    }
    
    /* Estilo de los campos de texto */
    .stTextInput > div > div > input, 
    .stTextArea > div > div > textarea {
        background-color: #f9f9f9 !important;
        border: 1px solid #ced4da !important;
        color: #000000 !important;
    }

    /* Resaltado cuando el mouse está sobre un campo */
    input:focus, textarea:focus {
        border: 2px solid #2e7d32 !important;
        background-color: #ffffff !important;
    }

    .reloj-discreto {
        font-size: 16px; font-weight: bold; color: #ff0000;
        text-align: right; margin-bottom: 5px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- FUNCIONES TÉCNICAS ---
def obtener_fecha_cr():
    return datetime.utcnow() - timedelta(hours=UTC_OFFSET)

def comprimir_imagen(archivo_subido):
    img = Image.open(archivo_subido)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    ancho_max = 1200
    if img.width > ancho_max:
        proporcion = ancho_max / float(img.width)
        alto = int((float(img.height) * float(proporcion)))
        img = img.resize((ancho_max, alto), Image.LANCZOS)
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=60, optimize=True)
    return buffer.getvalue()

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

def generar_siguiente_ot(df_ot):
    if df_ot.empty: return "0001"
    try:
        solo_numeros = pd.to_numeric(df_ot['OT'], errors='coerce').dropna()
        if solo_numeros.empty: return "0001"
        return f"{int(solo_numeros.max()) + 1:04d}"
    except: return "0001"

# --- CARGA DE DATOS ---
cols_ot = ["OT", "Empleado", "Descripcion", "Inicio", "Tipo", "Estado", "Fin", "Comentarios", "CorreoCopia", "TiempoAcumulado", "Foto"]
df_emp = cargar_datos("empleados.csv", ["Nombre", "Correo"])
df_ot = cargar_datos("ordenes.csv", cols_ot)

# --- MENÚ LATERAL (Selectbox Permanente) ---
st.sidebar.title("🛠️ Navegación Principal")
menu = st.sidebar.selectbox(
    "Seleccione una sección:", 
    ["👥 Empleados", "📝 Nueva OT", "🔍 Cierre y Consulta", "📊 Dashboard"],
    key="nav_menu"
)
st.sidebar.divider()
st.sidebar.write(f"📅 {obtener_fecha_cr().strftime('%d/%m/%Y')}")

# --- CONTENIDO SEGÚN SECCIÓN ---

# 1. EMPLEADOS
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
            emp_sel = st.selectbox("Seleccione para editar:", df_emp['Nombre'])
            idx_e = df_emp.index[df_emp['Nombre'] == emp_sel].tolist()[0]
            with st.form("edit_emp"):
                nuevo_n = st.text_input("Nombre", value=df_emp.at[idx_e, 'Nombre'])
                nuevo_c = st.text_input("Correo", value=df_emp.at[idx_e, 'Correo'])
                if st.form_submit_button("💾 Guardar Cambios"):
                    df_emp.at[idx_e, 'Nombre'] = nuevo_n
                    df_emp.at[idx_e, 'Correo'] = nuevo_c
                    guardar_datos(df_emp, "empleados.csv")
                    st.success("Actualizado.")
                    st.rerun()
    st.divider()
    st.table(df_emp)

# 2. NUEVA OT
elif menu == "📝 Nueva OT":
    st.header("📝 Apertura de Orden de Trabajo")
    if df_emp.empty:
        st.warning("Debe registrar operarios primero.")
    else:
        with st.form("f_ot", clear_on_submit=True):
            op = st.selectbox("Operario Asignado", df_emp['Nombre'])
            tp = st.radio("Tipo de Trabajo", ["Preventivo", "Correctivo", "Casos 24h", "Casos ISO"], horizontal=True)
            ds = st.text_area("Descripción del Hallazgo")
            archivo_foto = st.file_uploader("Capturar Foto (Opcional)", type=["jpg", "png", "jpeg"])
            cp = st.text_input("Correo de copia")
            
            if st.form_submit_button("Generar Orden"):
                if ds and cp:
                    id_ot = generar_siguiente_ot(df_ot)
                    nombre_foto = "Sin foto"
                    if archivo_foto:
                        nombre_foto = f"OT_{id_ot}.jpg"
                        img_comprimida = comprimir_imagen(archivo_foto)
                        with open(os.path.join("fotos", nombre_foto), "wb") as f:
                            f.write(img_comprimida)
                    
                    nueva = {
                        "OT": id_ot, "Empleado": op, "Descripcion": ds, 
                        "Inicio": obtener_fecha_cr().strftime("%Y-%m-%d %H:%M:%S"),
                        "Tipo": tp, "Estado": "Abierta", "Fin": "", "Comentarios": "", 
                        "CorreoCopia": cp, "TiempoAcumulado": "0", "Foto": nombre_foto
                    }
                    df_ot = pd.concat([df_ot, pd.DataFrame([nueva])], ignore_index=True)
                    guardar_datos(df_ot, "ordenes.csv")
                    st.success(f"OT #{id_ot} creada con éxito.")
                    st.rerun()

# 3. CIERRE Y CONSULTA
elif menu == "🔍 Cierre y Consulta":
    st.markdown(f'<div class="reloj-discreto">Hora CR: {obtener_fecha_cr().strftime("%H:%M:%S")}</div>', unsafe_allow_html=True)
    st.header("🔍 Gestión de Cierre y Consulta")
    tab_activas, tab_historial = st.tabs(["Órdenes Activas", "Historial Completo"])
    
    with tab_activas:
        pendientes = df_ot[df_ot['Estado'].isin(["Abierta", "En Pausa"])].copy()
        if pendientes.empty:
            st.info("No hay órdenes activas.")
        else:
            st.dataframe(pendientes[["OT", "Estado", "Empleado", "Tipo", "Descripcion"]], use_container_width=True)
            sel_ot = st.selectbox("Seleccione OT para editar:", pendientes['OT'] + " - " + pendientes['Descripcion'])
            id_sel = sel_ot.split(" - ")[0]
            idx_ot = df_ot.index[df_ot['OT'] == id_sel].tolist()[0]
            
            # Mostrar foto si existe
            foto_val = str(df_ot.at[idx_ot, 'Foto']).strip()
            if foto_val and foto_val != "Sin foto":
                ruta_img = os.path.join("fotos", foto_val)
                if os.path.exists(ruta_img):
                    st.image(ruta_img, caption="Evidencia de Apertura", width=400)

            with st.form("edit_estado"):
                est = st.selectbox("Estado", ["Abierta", "En Pausa", "Cerrada"], 
                                   index=["Abierta", "En Pausa", "Cerrada"].index(df_ot.at[idx_ot, 'Estado']))
                com = st.text_area("Comentarios / Avance", value=df_ot.at[idx_ot, 'Comentarios'])
                if st.form_submit_button("Actualizar Orden"):
                    ahora = obtener_fecha_cr()
                    # Lógica de tiempo
                    if df_ot.at[idx_ot, 'Estado'] == "Abierta":
                        ini = datetime.strptime(df_ot.at[idx_ot, 'Inicio'], "%Y-%m-%d %H:%M:%S")
                        sec = (ahora - ini).total_seconds()
                        df_ot.at[idx_ot, 'TiempoAcumulado'] = str(float(df_ot.at[idx_ot, 'TiempoAcumulado']) + sec)
                    
                    if est == "Abierta": df_ot.at[idx_ot, 'Inicio'] = ahora.strftime("%Y-%m-%d %H:%M:%S")
                    elif est == "Cerrada": df_ot.at[idx_ot, 'Fin'] = ahora.strftime("%Y-%m-%d %H:%M:%S")
                    
                    df_ot.at[idx_ot, 'Estado'] = est
                    df_ot.at[idx_ot, 'Comentarios'] = com
                    guardar_datos(df_ot, "ordenes.csv")
                    st.success("Orden actualizada.")
                    st.rerun()

    with tab_historial:
        st.dataframe(df_ot, use_container_width=True)
        # Botón Excel
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
            df_ot.to_excel(writer, index=False)
        st.download_button("📥 Descargar Base de Datos (Excel)", buf.getvalue(), "reporte_roble.xlsx")

# 4. DASHBOARD
elif menu == "📊 Dashboard":
    st.header("📊 Dashboard de Rendimiento")
    if not df_ot.empty:
        df_d = df_ot.copy()
        df_d['Horas'] = pd.to_numeric(df_d['TiempoAcumulado'], errors='coerce').fillna(0) / 3600
        fig = px.bar(df_d, x='OT', y='Horas', color='Tipo', title="Inversión de Horas por OT")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sin datos.")
