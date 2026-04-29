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

# --- MENÚ (LÍNEA 82 CORREGIDA) ---
menu = st.sidebar.selectbox("MENÚ PRINCIPAL", ["👥 Empleados", "📝 Nueva OT", "🔍 Cierre y Consulta", "📊 Dashboard"])

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
            emp_sel = st.selectbox("Seleccione empleado para editar:", df_emp['Nombre'])
            idx_emp = df_emp.index[df_emp['Nombre'] == emp_sel].tolist()[0]
            with st.form("edit_emp"):
                nuevo_nombre = st.text_input("Nombre", value=df_emp.at[idx_emp, 'Nombre'])
                nuevo_correo = st.text_input("Correo", value=df_emp.at[idx_emp, 'Correo'])
                c1, c2 = st.columns(2)
                if c1.form_submit_button("💾 Guardar"):
                    df_emp.at[idx_emp, 'Nombre'] = nuevo_nombre
                    df_emp.at[idx_emp, 'Correo'] = nuevo_correo
                    guardar_datos(df_emp, "empleados.csv")
                    st.success("Actualizado")
                    st.rerun()
                confirmar = st.checkbox("Confirmar eliminación")
                if c2.form_submit_button("🗑️ Eliminar"):
                    if confirmar:
                        df_emp = df_emp.drop(idx_emp).reset_index(drop=True)
                        guardar_datos(df_emp, "empleados.csv")
                        st.warning("Eliminado")
                        st.rerun()
    st.divider()
    st.table(df_emp)

# 2. NUEVA ORDEN DE TRABAJO
elif menu == "📝 Nueva OT":
    st.header("📝 Apertura de Orden de Trabajo")
    if df_emp.empty: 
        st.warning("Registre operarios primero.")
    else:
        with st.form("f_ot", clear_on_submit=True):
            op = st.selectbox("Operario Asignado", df_emp['Nombre'])
            tp = st.radio("Tipo de Trabajo", ["Preventivo", "Correctivo", "Casos 24h", "Casos ISO"], horizontal=True)
            ds = st.text_area("Descripción del Hallazgo")
            cp = st.text_input("Correo de copia obligatoria")
            if st.form_submit_button("Generar Orden"):
                if ds and cp:
                    id_ot = generar_siguiente_ot(df_ot)
                    nueva = {"OT":id_ot, "Empleado":op, "Descripcion":ds, "Inicio":obtener_fecha_cr().strftime("%Y-%m-%d %H:%M:%S"), 
                             "Tipo":tp, "Estado":"Abierta", "Fin":"", "Comentarios":"", "CorreoCopia":cp, "TiempoAcumulado":"0"}
                    df_ot = pd.concat([df_ot, pd.DataFrame([nueva])], ignore_index=True)
                    guardar_datos(df_ot, "ordenes.csv")
                    enviar_correo(df_emp[df_emp['Nombre']==op]['Correo'].values[0], cp, f"Nueva OT #{id_ot}", ds)
                    st.success(f"OT #{id_ot} creada.")
                    st.rerun()

# 3. CIERRE Y CONSULTA
elif menu == "🔍 Cierre y Consulta":
    st.markdown(f'<div class="reloj-discreto">Hora CR: {obtener_fecha_cr().strftime("%H:%M:%S")}</div>', unsafe_allow_html=True)
    st.header("🔍 Gestión de Cierre y Consulta")
    
    tab1, tab2 = st.tabs(["Órdenes Activas", "Historial de Cerradas"])
    with tab1:
        pendientes = df_ot[df_ot['Estado'].isin(["Abierta", "En Pausa"])].copy()
        if pendientes.empty: 
            st.info("No hay órdenes pendientes.")
        else:
            def calc_viva(row):
                try:
                    acum = float(row['TiempoAcumulado'])
                    if row['Estado'] == "Abierta":
                        ini = datetime.strptime(row['Inicio'], "%Y-%m-%d %H:%M:%S")
                        return str(timedelta(seconds=int(acum + (obtener_fecha_cr() - ini).total_seconds())))
                    return str(timedelta(seconds=int(acum)))
                except: return "0:00:00"
            pendientes['Duración'] = pendientes.apply(calc_viva, axis=1)
            st.dataframe(pendientes[["OT", "Estado", "Empleado", "Duración", "Tipo", "Descripcion", "Comentarios"]], use_container_width=True)
            sel = st.selectbox("Gestionar OT:", pendientes['OT'] + " - " + pendientes['Descripcion'])
            idx = df_ot.index[df_ot['OT'] == sel.split(" - ")[0]].tolist()[0]
            with st.form("m_ot"):
                est = st.selectbox("Estado", ["Abierta", "En Pausa", "Cerrada"], index=["Abierta", "En Pausa", "Cerrada"].index(df_ot.at[idx, 'Estado']))
                com = st.text_area("Comentarios de avance", value=df_ot.at[idx, 'Comentarios'])
                if st.form_submit_button("Actualizar"):
                    ahora = obtener_fecha_cr()
                    if df_ot.at[idx, 'Estado'] == "Abierta":
                        ini = datetime.strptime(df_ot.at[idx, 'Inicio'], "%Y-%m-%d %H:%M:%S")
                        df_ot.at[idx, 'TiempoAcumulado'] = str(float(df_ot.at[idx, 'TiempoAcumulado']) + (ahora - ini).total_seconds())
                    if est == "Abierta": df_ot.at[idx, 'Inicio'] = ahora.strftime("%Y-%m-%d %H:%M:%S")
                    elif est == "Cerrada": df_ot.at[idx, 'Fin'] = ahora.strftime("%Y-%m-%d %H:%M:%S")
                    df_ot.at[idx, 'Estado'] = est
                    df_ot.at[idx, 'Comentarios'] = com
                    guardar_datos(df_ot, "ordenes.csv")
                    st.rerun()
    with tab2:
        cerradas = df_ot[df_ot['Estado'] == "Cerrada"].copy()
        if not cerradas.empty:
            cerradas['Duración Final'] = cerradas.apply(lambda r: str(timedelta(seconds=int(float(r['TiempoAcumulado'])))), axis=1)
            st.dataframe(cerradas[["OT", "Empleado", "Tipo", "Duración Final", "Fin", "Comentarios"]], use_container_width=True)

# 4. DASHBOARD
elif menu == "📊 Dashboard":
    st.header("📊 Dashboard de Rendimiento")
    if df_ot.empty: 
        st.info("No hay datos.")
    else:
        df_d = df_ot.copy()
        df_d['Inicio_DT'] = pd.to_datetime(df_d['Inicio'], errors='coerce')
        df_d = df_d.dropna(subset=['Inicio_DT'])
        df_d['Horas'] = df_d['TiempoAcumulado'].apply(lambda x: round(float(x)/3600, 2))
        f_ini = st.sidebar.date_input("Fecha Inicio", df_d['Inicio_DT'].min().date())
        f_fin = st.sidebar.date_input("Fecha Fin", obtener_fecha_cr().date())
        f_op = st.sidebar.selectbox("Operario", ["TODOS"] + list(df_emp['Nombre'].unique()) if not df_emp.empty else ["TODOS"])
        f_tp = st.sidebar.selectbox("Tipo de OT", ["TODOS", "Preventivo", "Correctivo", "Casos 24h", "Casos ISO"])
        mask = (df_d['Inicio_DT'].dt.date >= f_ini) & (df_d['Inicio_DT'].dt.date <= f_fin)
        if f_op != "TODOS": mask &= (df_d['Empleado'] == f_op)
        if f_tp != "TODOS": mask &= (df_d['Tipo'] == f_tp)
        df_f = df_d[mask]
        c1, c2, c3 = st.columns(3)
        c1.metric("OTs", len(df_f)); c2.metric("Horas", f"{df_f['Horas'].sum():.2f}"); c3.metric("Promedio", f"{df_f['Horas'].mean():.2f}" if not df_f.empty else "0")
        if not df_f.empty:
            st.plotly_chart(px.bar(df_f, x='OT', y='Horas', color='Tipo', title="Inversión de Tiempo"), use_container_width=True)
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df_f.drop(columns=['Inicio_DT']).to_excel(writer, index=False, sheet_name='Reporte')
            st.download_button("📥 Descargar Reporte Excel", buffer.getvalue(), "reporte_roble.xlsx")
