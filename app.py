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

# --- ESTILO CSS (CURSOR Y FOCO) ---
st.markdown("""
    <style>
    input, textarea { caret-color: #ff0000 !important; }
    .stTextInput > div > div > input, .stTextArea > div > div > textarea {
        background-color: #f9f9f9 !important;
        color: #000000 !important;
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

# --- CARGA DE DATOS ---
cols_ot = ["OT", "Empleado", "Descripcion", "Inicio", "Tipo", "Estado", "Fin", "Comentarios", "CorreoCopia", "TiempoAcumulado", "Foto"]
df_emp = cargar_datos("empleados.csv", ["Nombre", "Correo"])
df_ot = cargar_datos("ordenes.csv", cols_ot)

# --- MENÚ LATERAL PERMANENTE ---
st.sidebar.title("🛠️ Navegación Principal")
menu = st.sidebar.selectbox(
    "Seleccione una sección:", 
    ["👥 Empleados", "📝 Nueva OT", "🔍 Cierre y Consulta", "📊 Dashboard"]
)
st.sidebar.divider()

# --- LÓGICA DE SECCIONES ---

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
                    st.rerun()
    with tab_mod:
        if not df_emp.empty:
            emp_sel = st.selectbox("Seleccione para editar:", df_emp['Nombre'])
            idx_e = df_emp.index[df_emp['Nombre'] == emp_sel].tolist()[0]
            with st.form("edit_emp"):
                nuevo_n = st.text_input("Nombre", value=df_emp.at[idx_e, 'Nombre'])
                nuevo_c = st.text_input("Correo", value=df_emp.at[idx_e, 'Correo'])
                if st.form_submit_button("💾 Guardar"):
                    df_emp.at[idx_e, 'Nombre'] = nuevo_n
                    df_emp.at[idx_e, 'Correo'] = nuevo_c
                    guardar_datos(df_emp, "empleados.csv")
                    st.rerun()
    st.table(df_emp)

elif menu == "📝 Nueva OT":
    st.header("📝 Apertura de Orden de Trabajo")
    if df_emp.empty:
        st.warning("Registre operarios primero.")
    else:
        with st.form("f_ot", clear_on_submit=True):
            op = st.selectbox("Operario Asignado", df_emp['Nombre'])
            tp = st.radio("Tipo de Trabajo", ["Preventivo", "Correctivo", "Casos 24h", "Casos ISO"], horizontal=True)
            ds = st.text_area("Descripción del Hallazgo")
            archivo_foto = st.file_uploader("Capturar Foto (Opcional)", type=["jpg", "png", "jpeg"])
            cp = st.text_input("Correo de copia")
            if st.form_submit_button("Generar Orden"):
                if ds and cp:
                    id_ot = f"{len(df_ot) + 1:04d}"
                    nombre_foto = "Sin foto"
                    if archivo_foto:
                        nombre_foto = f"OT_{id_ot}.jpg"
                        with open(os.path.join("fotos", nombre_foto), "wb") as f:
                            f.write(archivo_foto.getbuffer())
                    
                    nueva = {"OT": id_ot, "Empleado": op, "Descripcion": ds, 
                             "Inicio": obtener_fecha_cr().strftime("%Y-%m-%d %H:%M:%S"),
                             "Tipo": tp, "Estado": "Abierta", "Fin": "", "Comentarios": "", 
                             "CorreoCopia": cp, "TiempoAcumulado": "0", "Foto": nombre_foto}
                    df_ot = pd.concat([df_ot, pd.DataFrame([nueva])], ignore_index=True)
                    guardar_datos(df_ot, "ordenes.csv")
                    st.success(f"OT #{id_ot} creada."); st.rerun()

elif menu == "🔍 Cierre y Consulta":
    st.header("🔍 Gestión de Cierre y Consulta")
    tab1, tab2 = st.tabs(["Activas", "Historial"])
    with tab1:
        pendientes = df_ot[df_ot['Estado'].isin(["Abierta", "En Pausa"])].copy()
        if not pendientes.empty:
            sel = st.selectbox("Seleccione OT:", pendientes['OT'] + " - " + pendientes['Descripcion'])
            id_sel = sel.split(" - ")[0]
            idx = df_ot.index[df_ot['OT'] == id_sel].tolist()[0]
            with st.form("m_ot"):
                est = st.selectbox("Estado", ["Abierta", "En Pausa", "Cerrada"], index=["Abierta", "En Pausa", "Cerrada"].index(df_ot.at[idx, 'Estado']))
                com = st.text_area("Comentarios", value=df_ot.at[idx, 'Comentarios'])
                if st.form_submit_button("Actualizar"):
                    df_ot.at[idx, 'Estado'] = est
                    df_ot.at[idx, 'Comentarios'] = com
                    guardar_datos(df_ot, "ordenes.csv"); st.rerun()

elif menu == "📊 Dashboard":
    st.header("📊 Dashboard de Rendimiento")
    if df_ot.empty:
        st.info("No hay datos disponibles.")
    else:
        # Preparación de datos para filtros
        df_d = df_ot.copy()
        df_d['Inicio_DT'] = pd.to_datetime(df_d['Inicio'], errors='coerce')
        df_d['Horas'] = pd.to_numeric(df_d['TiempoAcumulado'], errors='coerce').fillna(0) / 3600
        
        # --- FILTROS EN BARRA LATERAL (Solo visibles en Dashboard) ---
        st.sidebar.subheader("Filtros de Análisis")
        f_inicio = st.sidebar.date_input("Fecha Inicio", df_d['Inicio_DT'].min().date() if not df_d['Inicio_DT'].isnull().all() else obtener_fecha_cr().date())
        f_fin = st.sidebar.date_input("Fecha Fin", obtener_fecha_cr().date())
        f_op = st.sidebar.selectbox("Filtrar por Operario", ["TODOS"] + list(df_emp['Nombre'].unique()))
        f_tipo = st.sidebar.selectbox("Filtrar por Tipo", ["TODOS", "Preventivo", "Correctivo", "Casos 24h", "Casos ISO"])

        # Aplicación de filtros
        mask = (df_d['Inicio_DT'].dt.date >= f_inicio) & (df_d['Inicio_DT'].dt.date <= f_fin)
        if f_op != "TODOS": mask &= (df_d['Empleado'] == f_op)
        if f_tipo != "TODOS": mask &= (df_d['Tipo'] == f_tipo)
        
        df_filtrado = df_d[mask]

        # Métricas principales
        c1, c2, c3 = st.columns(3)
        c1.metric("Total OTs", len(df_filtrado))
        c2.metric("Total Horas", f"{df_filtrado['Horas'].sum():.2f}")
        c3.metric("Promedio Horas/OT", f"{df_filtrado['Horas'].mean():.2f}" if len(df_filtrado) > 0 else "0")

        # Gráficos
        st.plotly_chart(px.bar(df_filtrado, x='OT', y='Horas', color='Tipo', title="Inversión de Tiempo por Orden"), use_container_width=True)
        
        col_a, col_b = st.columns(2)
        with col_a:
            st.plotly_chart(px.pie(df_filtrado, names='Tipo', title="Distribución por Tipo de Trabajo"), use_container_width=True)
        with col_b:
            st.plotly_chart(px.bar(df_filtrado.groupby('Empleado')['Horas'].sum().reset_index(), x='Empleado', y='Horas', title="Horas por Operario"), use_container_width=True)
