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
        text-align: center; border: 1px solid #2e7d32;
    }
    </style>
    """, unsafe_allow_html=True)

# --- FUNCIONES DE PERSISTENCIA ---
def cargar_datos(archivo, columnas):
    if os.path.exists(archivo):
        try:
            df = pd.read_csv(archivo, dtype=str)
            # REPARACIÓN AUTOMÁTICA: Si faltan columnas nuevas, las agregamos
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
        # Filtramos solo los que son números para evitar errores con IDs viejos tipo fecha
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
menu = st.sidebar.selectbox("MENÚ", ["👥 Empleados", "📝 Nueva OT", "🔍 Cierre y Consulta", "📊 Dashboard"])

# 1. EMPLEADOS
if menu == "👥 Empleados":
    st.header("👥 Gestión de Operarios")
    col1, col2 = st.columns(2)
    with col1:
        with st.form("add_emp", clear_on_submit=True):
            n = st.text_input("Nombre")
            c = st.text_input("Correo")
            if st.form_submit_button("Registrar"):
                if n and c:
                    df_emp = pd.concat([df_emp, pd.DataFrame([{"Nombre":n,"Correo":c}])], ignore_index=True)
                    guardar_datos(df_emp, "empleados.csv")
                    st.rerun()
    st.table(df_emp)

# 2. NUEVA OT
elif menu == "📝 Nueva OT":
    st.header("📝 Apertura de Orden")
    if df_emp.empty: st.warning("Registre operarios primero.")
    else:
        with st.form("f_ot"):
            op = st.selectbox("Operario", df_emp['Nombre'])
            tp = st.radio("Tipo", ["Preventivo", "Correctivo", "Casos 24h", "Casos ISO"], horizontal=True)
            ds = st.text_area("Descripción")
            cp = st.text_input("Correo de copia (Obligatorio)")
            if st.form_submit_button("Crear OT"):
                if ds and cp:
                    ahora = obtener_fecha_cr().strftime("%Y-%m-%d %H:%M:%S")
                    id_ot = generar_siguiente_ot(df_ot)
                    nueva = {"OT":id_ot, "Empleado":op, "Descripcion":ds, "Inicio":ahora, 
                             "Tipo":tp, "Estado":"Abierta", "Fin":"", "Comentarios":"", 
                             "CorreoCopia":cp, "TiempoAcumulado":"0"}
                    df_ot = pd.concat([df_ot, pd.DataFrame([nueva])], ignore_index=True)
                    guardar_datos(df_ot, "ordenes.csv")
                    
                    # Envío de correo
                    asunto = f"Nueva OT #{id_ot} - {tp}"
                    cuerpo = f"Se asignó la OT {id_ot} a {op}.\nDescripción: {ds}"
                    enviar_correo(df_emp[df_emp['Nombre']==op]['Correo'].values[0], cp, asunto, cuerpo)
                    
                    st.success(f"OT {id_ot} registrada.")
                    st.rerun()

# 3. CIERRE Y CONSULTA (CON RELOJ Y PAUSA)
elif menu == "🔍 Cierre y Consulta":
    st.markdown(f'<div class="reloj-vivo">🕒 Hora CR: {obtener_fecha_cr().strftime("%H:%M:%S")}</div>', unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["Pendientes", "Historial"])
    
    with tab1:
        # Mostramos Abiertas y En Pausa
        pendientes = df_ot[df_ot['Estado'].isin(["Abierta", "En Pausa"])].copy()
        if pendientes.empty:
            st.info("No hay órdenes activas.")
        else:
            # Cálculo de duración visual
            def calc_viva(row):
                acum = float(row['TiempoAcumulado'])
                if row['Estado'] == "Abierta":
                    ini = datetime.strptime(row['Inicio'], "%Y-%m-%d %H:%M:%S")
                    ahora = (obtener_fecha_cr() - ini).total_seconds()
                    return str(timedelta(seconds=int(acum + ahora)))
                return str(timedelta(seconds=int(acum)))

            pendientes['Duración'] = pendientes.apply(calc_viva, axis=1)
            st.dataframe(pendientes[["OT", "Estado", "Empleado", "Duración", "Tipo", "Descripcion"]], use_container_width=True)
            
            sel = st.selectbox("Seleccionar OT:", pendientes['OT'] + " - " + pendientes['Descripcion'])
            idx = df_ot.index[df_ot['OT'] == sel.split(" - ")[0]].tolist()[0]
            
            with st.form("m_ot"):
                est = st.selectbox("Nuevo Estado", ["Abierta", "En Pausa", "Cerrada"], 
                                   index=["Abierta", "En Pausa", "Cerrada"].index(df_ot.at[idx, 'Estado']))
                com = st.text_area("Comentarios", value=df_ot.at[idx, 'Comentarios'])
                if st.form_submit_button("Actualizar"):
                    ahora = obtener_fecha_cr()
                    # Si estaba abierta, sumamos el tiempo antes de cambiar de estado
                    if df_ot.at[idx, 'Estado'] == "Abierta":
                        ini = datetime.strptime(df_ot.at[idx, 'Inicio'], "%Y-%m-%d %H:%M:%S")
                        dif = (ahora - ini).total_seconds()
                        df_ot.at[idx, 'TiempoAcumulado'] = str(float(df_ot.at[idx, 'TiempoAcumulado']) + dif)
                    
                    if est == "Abierta":
                        df_ot.at[idx, 'Inicio'] = ahora.strftime("%Y-%m-%d %H:%M:%S")
                    elif est == "Cerrada":
                        df_ot.at[idx, 'Fin'] = ahora.strftime("%Y-%m-%d %H:%M:%S")
                    
                    df_ot.at[idx, 'Estado'] = est
                    df_ot.at[idx, 'Comentarios'] = com
                    guardar_datos(df_ot, "ordenes.csv")
                    st.rerun()

    with tab2:
        st.dataframe(df_ot[df_ot['Estado']=="Cerrada"], use_container_width=True)

# 4. DASHBOARD (REPARADO)
elif menu == "📊 Dashboard":
    st.header("📊 Dashboard de Gestión")
    if df_ot.empty:
        st.info("No hay datos.")
    else:
        # Preparación de datos para el Dashboard
        df_d = df_ot.copy()
        df_d['Inicio'] = pd.to_datetime(df_d['Inicio'])
        
        # Cálculo de horas totales (acumulado + tiempo final si aplica)
        def get_h(r):
            total_seg = float(r['TiempoAcumulado'])
            return round(total_seg / 3600, 2)
        
        df_d['Horas'] = df_d.apply(get_h, axis=1)
        
        # Filtros
        st.sidebar.subheader("Filtros")
        f_op = st.sidebar.selectbox("Operario", ["TODOS"] + list(df_emp['Nombre'].unique()))
        f_tp = st.sidebar.selectbox("Tipo", ["TODOS", "Preventivo", "Correctivo", "Casos 24h", "Casos ISO"])
        
        mask = (df_d['OT'] != "")
        if f_op != "TODOS": mask &= (df_d['Empleado'] == f_op)
        if f_tp != "TODOS": mask &= (df_d['Tipo'] == f_tp)
        
        df_f = df_d[mask]
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Total OTs", len(df_f))
        c2.metric("Pausadas", len(df_f[df_f['Estado']=="En Pausa"]))
        c3.metric("Horas Totales", df_f['Horas'].sum())
        
        if not df_f.empty:
            fig = px.bar(df_f, x='OT', y='Horas', color='Tipo', title="Inversión de Tiempo por OT (Horas)")
            st.plotly_chart(fig, use_container_width=True)
