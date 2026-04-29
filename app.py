import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import plotly.express as px
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from PIL import Image
import io
from streamlit_autorefresh import st_autorefresh

# --- CONFIGURACIÓN GENERAL ---
st.set_page_config(page_title="Gestión OT - Roble", layout="wide")
UTC_OFFSET = 6 # Costa Rica

# Refresco silencioso cada 1 segundo
st_autorefresh(interval=1000, key="daterefresh")

if not os.path.exists("fotos"):
    os.makedirs("fotos")

# --- FUNCIONES DE APOYO ---
def obtener_fecha_cr():
    return datetime.utcnow() - timedelta(hours=UTC_OFFSET)

def mostrar_reloj_discreto():
    """Muestra la hora en rojo, pequeña y alineada a la derecha."""
    hora_actual = obtener_fecha_cr().strftime("%d/%m/%Y %H:%M:%S")
    st.markdown(
        f"""
        <div style="text-align: right; margin-top: -50px;">
            <p style="color: #ff4b4b; font-size: 12px; font-family: monospace; font-weight: bold;">
                SISTEMA CR: {hora_actual}
            </p>
        </div>
        """, 
        unsafe_allow_html=True
    )

def cargar_datos(archivo, columnas):
    if os.path.exists(archivo):
        try:
            return pd.read_csv(archivo, dtype=str).fillna("")
        except:
            return pd.DataFrame(columns=columnas)
    return pd.DataFrame(columns=columnas)

def guardar_datos(df, archivo):
    df.to_csv(archivo, index=False)

def estilo_estados(val):
    if val == 'Abierta': return 'color: green; font-weight: bold'
    if val == 'En Pausa': return 'color: orange; font-weight: bold'
    if val == 'Cerrada': return 'color: red; font-weight: bold'
    return ''

def generar_excel_protegido(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Historial_OT')
        workbook  = writer.book
        worksheet = writer.sheets['Historial_OT']
        worksheet.protect('Roble2026', {
            'objects': True, 'scenarios': True, 'format_cells': False,
            'insert_columns': False, 'delete_columns': False, 'sort': False, 'autofilter': True,
        })
    return output.getvalue()

# --- CARGA DE DATOS ---
cols_ot = ["OT", "Empleado", "Descripcion", "Inicio", "Tipo", "Estado", "Fin", "Comentarios", "CorreoCopia", "TiempoAcumulado", "Foto"]
df_emp = cargar_datos("empleados.csv", ["Nombre", "Correo"])
df_ot = cargar_datos("ordenes.csv", cols_ot)

# --- NAVEGACIÓN ---
st.sidebar.title("🛠️ Panel de Control")
menu = st.sidebar.selectbox("Seleccione sección:", ["👥 Empleados", "📝 Nueva OT", "🔍 Cierre y Consulta", "📊 Dashboard"])

# --- LÓGICA POR SECCIÓN ---

if menu == "👥 Empleados":
    st.header("👥 Gestión de Personal")
    mostrar_reloj_discreto()
    t1, t2, t3 = st.tabs(["➕ Registrar", "✏️ Modificar", "🗑️ Eliminar"])
    with t1:
        with st.form("add_emp", clear_on_submit=True):
            n, c = st.text_input("Nombre Completo"), st.text_input("Correo Electrónico")
            if st.form_submit_button("Registrar"):
                if n and c:
                    df_emp = pd.concat([df_emp, pd.DataFrame([{"Nombre":n,"Correo":c}])], ignore_index=True)
                    guardar_datos(df_emp, "empleados.csv")
                    st.success("Registrado"); st.rerun()
    st.table(df_emp)

elif menu == "📝 Nueva OT":
    st.header("📝 Apertura de Orden de Trabajo")
    mostrar_reloj_discreto()
    if df_emp.empty: st.warning("Registre operarios primero")
    else:
        with st.form("f_ot", clear_on_submit=True):
            op = st.selectbox("Operario Asignado", df_emp['Nombre'])
            tp = st.radio("Tipo de Trabajo", ["Preventivo", "Correctivo", "Casos 24h", "Casos ISO"], horizontal=True)
            ds = st.text_area("Descripción del Hallazgo")
            foto = st.file_uploader("Adjuntar Foto", type=["jpg", "png", "jpeg"])
            cp = st.text_input("Correo copia adicional")
            if st.form_submit_button("Generar OT"):
                id_ot = f"{len(df_ot) + 1:04d}"
                nom_foto = f"OT_{id_ot}.jpg" if foto else "Sin foto"
                if foto:
                    with open(os.path.join("fotos", nom_foto), "wb") as f: f.write(foto.getbuffer())
                
                nueva = {"OT":id_ot, "Empleado":op, "Descripcion":ds, "Inicio":obtener_fecha_cr().strftime("%Y-%m-%d %H:%M:%S"),
                         "Tipo":tp, "Estado":"Abierta", "Fin":"", "Comentarios":"", "CorreoCopia":cp, "TiempoAcumulado":"0", "Foto":nom_foto}
                df_ot = pd.concat([df_ot, pd.DataFrame([nueva])], ignore_index=True)
                guardar_datos(df_ot, "ordenes.csv")
                st.success(f"OT #{id_ot} generada"); st.rerun()

elif menu == "🔍 Cierre y Consulta":
    st.header("🔍 Gestión de Cierre y Consulta")
    mostrar_reloj_discreto()
    tab1, tab2 = st.tabs(["Órdenes Activas", "Historial Completo"])
    with tab1:
        pendientes = df_ot[df_ot['Estado'].isin(["Abierta", "En Pausa"])].copy()
        if not pendientes.empty:
            st.dataframe(pendientes[["OT", "Estado", "Empleado", "Tipo", "Descripcion"]].style.map(estilo_estados, subset=['Estado']), use_container_width=True, hide_index=True)
            sel = st.selectbox("Seleccionar OT:", ["---"] + (pendientes['OT'] + " | " + pendientes['Empleado']).tolist())
            if sel != "---":
                idx = df_ot.index[df_ot['OT'] == sel.split(" | ")[0]].tolist()[0]
                if df_ot.at[idx, 'Foto'] != "Sin foto":
                    st.image(os.path.join("fotos", df_ot.at[idx, 'Foto']), width=300)
                with st.form("c_form"):
                    est = st.selectbox("Estado", ["Abierta", "En Pausa", "Cerrada"], index=["Abierta", "En Pausa", "Cerrada"].index(df_ot.at[idx, 'Estado']))
                    com = st.text_area("Comentarios", value=df_ot.at[idx, 'Comentarios'])
                    if st.form_submit_button("Actualizar"):
                        df_ot.at[idx, 'Estado'], df_ot.at[idx, 'Comentarios'] = est, com
                        if est == "Cerrada": df_ot.at[idx, 'Fin'] = obtener_fecha_cr().strftime("%Y-%m-%d %H:%M:%S")
                        guardar_datos(df_ot, "ordenes.csv"); st.rerun()
    with tab2:
        st.dataframe(df_ot.style.map(estilo_estados, subset=['Estado']), use_container_width=True)
        if not df_ot.empty:
            st.download_button("📥 Descargar Excel Protegido", generar_excel_protegido(df_ot), "Reporte_OT.xlsx")

elif menu == "📊 Dashboard":
    st.header("📊 Dashboard de Rendimiento")
    mostrar_reloj_discreto()
    
    if not df_ot.empty:
        # --- FILTROS DEL DASHBOARD ---
        st.sidebar.divider()
        st.sidebar.subheader("🎯 Filtros de Búsqueda")
        
        df_ot['Inicio_dt'] = pd.to_datetime(df_ot['Inicio'], errors='coerce')
        
        # 1. Filtro de Fecha
        f_min = df_ot['Inicio_dt'].min().date() if not df_ot['Inicio_dt'].dropna().empty else obtener_fecha_cr().date()
        rango = st.sidebar.date_input("Rango de Fechas", [f_min, obtener_fecha_cr().date()])
        
        # 2. Filtro de Operario
        ops = ["Todos"] + sorted(df_ot['Empleado'].unique().tolist())
        op_sel = st.sidebar.selectbox("Filtrar por Operario", ops)
        
        # 3. Filtro por Tipo de Trabajo
        tps = ["Todos"] + sorted(df_ot['Tipo'].unique().tolist())
        tp_sel = st.sidebar.selectbox("Filtrar por Tipo", tps)

        # Aplicar Filtros
        df_f = df_ot.copy()
        if len(rango) == 2:
            df_f = df_f[(df_f['Inicio_dt'].dt.date >= rango[0]) & (df_f['Inicio_dt'].dt.date <= rango[1])]
        if op_sel != "Todos":
            df_f = df_f[df_f['Empleado'] == op_sel]
        if tp_sel != "Todos":
            df_f = df_f[df_f['Tipo'] == tp_sel]

        # Métricas
        df_f['Horas'] = pd.to_numeric(df_f['TiempoAcumulado'], errors='coerce').fillna(0) / 3600
        c1, c2, c3 = st.columns(3)
        c1.metric("Órdenes Filtradas", len(df_f))
        c2.metric("Horas Totales", f"{df_f['Horas'].sum():.2f}")
        c3.metric("Órdenes Cerradas", len(df_f[df_f['Estado'] == "Cerrada"]))
        
        # Gráficos
        st.plotly_chart(px.bar(df_f, x='OT', y='Horas', color='Tipo', title="Inversión de Tiempo por OT"), use_container_width=True)
        st.plotly_chart(px.pie(df_f, names='Estado', title="Distribución por Estado"), use_container_width=True)
    else:
        st.info("No hay datos para mostrar.")
