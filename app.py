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
    .reloj-vivo {
        font-size: 22px; font-weight: bold; color: #1b5e20;
        background-color: #c8e6c9; padding: 10px; border-radius: 10px;
        text-align: center; border: 1px solid #2e7d32; margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- FUNCIONES DE PERSISTENCIA ---
def cargar_datos(archivo, columnas):
    if os.path.exists(archivo):
        try:
            df = pd.read_csv(archivo, dtype=str)
            # REPARACIÓN: Asegurar que existan todas las columnas necesarias
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

# --- MENÚ ---
menu = st.sidebar.selectbox("MENÚ PRINCIPAL", ["👥 Empleados", "📝 Nueva OT", "🔍 Cierre y Consulta", "📊 Dashboard"])

# 1. GESTIÓN DE EMPLEADOS
if menu == "👥 Empleados":
    st.header("👥 Gestión de Operarios")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Registrar Nuevo")
        with st.form("add_emp", clear_on_submit=True):
            n = st.text_input("Nombre Completo")
            c = st.text_input("Correo Electrónico")
            if st.form_submit_button("Registrar"):
                if n and c:
                    df_emp = pd.concat([df_emp, pd.DataFrame([{"Nombre":n,"Correo":c}])], ignore_index=True)
                    guardar_datos(df_emp, "empleados.csv")
                    st.success("Operario registrado.")
                    st.rerun()
    st.divider()
    st.table(df_emp)

# 2. NUEVA ORDEN DE TRABAJO
elif menu == "📝 Nueva OT":
    st.header("📝 Apertura de Orden de Trabajo")
    if df_emp.empty: 
        st.warning("Debe registrar operarios en la pestaña de Empleados primero.")
    else:
        with st.form("f_ot", clear_on_submit=True):
            op = st.selectbox("Operario Asignado", df_emp['Nombre'])
            tp = st.radio("Tipo de Trabajo", ["Preventivo", "Correctivo", "Casos 24h", "Casos ISO"], horizontal=True)
            ds = st.text_area("Descripción del Hallazgo")
            cp = st.text_input("Correo de copia obligatoria")
            
            if st.form_submit_button("Generar Orden"):
                if ds and cp:
                    ahora_str = obtener_fecha_cr().strftime("%Y-%m-%d %H:%M:%S")
                    id_ot = generar_siguiente_ot(df_ot)
                    nueva = {"OT":id_ot, "Empleado":op, "Descripcion":ds, "Inicio":ahora_str, 
                             "Tipo":tp, "Estado":"Abierta", "Fin":"", "Comentarios":"", 
                             "CorreoCopia":cp, "TiempoAcumulado":"0"}
                    df_ot = pd.concat([df_ot, pd.DataFrame([nueva])], ignore_index=True)
                    guardar_datos(df_ot, "ordenes.csv")
                    
                    # Notificación por correo
                    correo_op = df_emp[df_emp['Nombre']==op]['Correo'].values[0]
                    enviar_correo(correo_op, cp, f"Nueva OT #{id_ot} - {tp}", f"Se ha generado la OT {id_ot}.\nDescripción: {ds}")
                    
                    st.success(f"OT #{id_ot} creada con éxito.")
                    st.rerun()
                else:
                    st.error("La descripción y el correo de copia son obligatorios.")

# 3. CIERRE Y CONSULTA (RELOJ + PAUSA)
elif menu == "🔍 Cierre y Consulta":
    st.markdown(f'<div class="reloj-vivo">🕒 Hora Costa Rica: {obtener_fecha_cr().strftime("%H:%M:%S")}</div>', unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["Órdenes Activas", "Historial de Cerradas"])
    
    with tab1:
        pendientes = df_ot[df_ot['Estado'].isin(["Abierta", "En Pausa"])].copy()
        if pendientes.empty:
            st.info("No hay órdenes pendientes de cierre.")
        else:
            def calc_viva(row):
                acum = float(row['TiempoAcumulado'])
                if row['Estado'] == "Abierta":
                    ini = datetime.strptime(row['Inicio'], "%Y-%m-%d %H:%M:%S")
                    ahora = (obtener_fecha_cr() - ini).total_seconds()
                    return str(timedelta(seconds=int(acum + ahora)))
                return str(timedelta(seconds=int(acum)))

            pendientes['Duración Actual'] = pendientes.apply(calc_viva, axis=1)
            st.dataframe(pendientes[["OT", "Estado", "Empleado", "Duración Actual", "Tipo", "Descripcion"]], use_container_width=True)
            
            sel = st.selectbox("Seleccione OT para gestionar:", pendientes['OT'] + " - " + pendientes['Descripcion'])
            id_sel = sel.split(" - ")[0]
            idx = df_ot.index[df_ot['OT'] == id_sel].tolist()[0]
            
            with st.form("m_ot"):
                col_a, col_b = st.columns(2)
                with col_a:
                    est = st.selectbox("Estado", ["Abierta", "En Pausa", "Cerrada"], 
                                       index=["Abierta", "En Pausa", "Cerrada"].index(df_ot.at[idx, 'Estado']))
                with col_b:
                    st.info(f"Estado actual: {df_ot.at[idx, 'Estado']}")
                
                com = st.text_area("Comentarios de avance/cierre", value=df_ot.at[idx, 'Comentarios'])
                
                if st.form_submit_button("Actualizar Orden"):
                    ahora = obtener_fecha_cr()
                    # Si estaba abierta, guardamos el tiempo trabajado antes del cambio
                    if df_ot.at[idx, 'Estado'] == "Abierta":
                        ini = datetime.strptime(df_ot.at[idx, 'Inicio'], "%Y-%m-%d %H:%M:%S")
                        segundos = (ahora - ini).total_seconds()
                        df_ot.at[idx, 'TiempoAcumulado'] = str(float(df_ot.at[idx, 'TiempoAcumulado']) + segundos)
                    
                    if est == "Abierta":
                        df_ot.at[idx, 'Inicio'] = ahora.strftime("%Y-%m-%d %H:%M:%S")
                    elif est == "Cerrada":
                        df_ot.at[idx, 'Fin'] = ahora.strftime("%Y-%m-%d %H:%M:%S")
                    
                    df_ot.at[idx, 'Estado'] = est
                    df_ot.at[idx, 'Comentarios'] = com
                    guardar_datos(df_ot, "ordenes.csv")
                    st.success(f"OT {id_sel} actualizada.")
                    st.rerun()

    with tab2:
        cerradas = df_ot[df_ot['Estado'] == "Cerrada"].copy()
        if not cerradas.empty:
            cerradas['Duración Final'] = cerradas.apply(lambda r: str(timedelta(seconds=int(float(r['TiempoAcumulado'])))), axis=1)
            st.dataframe(cerradas[["OT", "Empleado", "Tipo", "Duración Final", "Fin", "Comentarios"]], use_container_width=True)

# 4. DASHBOARD (SELECTORES DE FECHA REPARADOS)
elif menu == "📊 Dashboard":
    st.header("📊 Dashboard de Rendimiento")
    if df_ot.empty:
        st.info("No hay datos para analizar.")
    else:
        df_d = df_ot.copy()
        df_d['Inicio_DT'] = pd.to_datetime(df_d['Inicio'], errors='coerce')
        df_d = df_d.dropna(subset=['Inicio_DT'])
        df_d['Horas'] = df_d['TiempoAcumulado'].apply(lambda x: round(float(x)/3600, 2))
        
        # Filtros laterales
        hoy = obtener_fecha_cr().date()
        min_f = df_d['Inicio_DT'].min().date() if not df_d.empty else hoy
        
        f_ini = st.sidebar.date_input("Fecha Inicio", min_f)
        f_fin = st.sidebar.date_input("Fecha Fin", hoy)
        f_op = st.sidebar.selectbox("Operario", ["TODOS"] + list(df_emp['Nombre'].unique()))
        f_tp = st.sidebar.selectbox("Tipo", ["TODOS", "Preventivo", "Correctivo", "Casos 24h", "Casos ISO"])
        
        mask = (df_d['Inicio_DT'].dt.date >= f_ini) & (df_d['Inicio_DT'].dt.date <= f_fin)
        if f_op != "TODOS": mask &= (df_d['Empleado'] == f_op)
        if f_tp != "TODOS": mask &= (df_d['Tipo'] == f_tp)
        
        df_f = df_d[mask]
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Total OTs", len(df_f))
        c2.metric("Horas Totales", f"{df_f['Horas'].sum():.2f}")
        c3.metric("Promedio h/OT", f"{df_f['Horas'].mean():.2f}" if not df_f.empty else "0")
        
        if not df_f.empty:
            fig = px.bar(df_f, x='OT', y='Horas', color='Tipo', title="Inversión de Tiempo por Orden")
            st.plotly_chart(fig, use_container_width=True)
            
            # Botón de Descarga Excel
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df_f.drop(columns=['Inicio_DT']).to_excel(writer, index=False, sheet_name='Reporte')
            st.download_button("📥 Descargar este reporte (Excel)", buffer.getvalue(), "reporte.xlsx", "application/vnd.ms-excel")
