import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import plotly.express as px
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- CONFIGURACIÓN DE CORREO (SMTP) ---
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "tu-correo@gmail.com" 
SENDER_PASSWORD = "tu-clave-de-16-letras" # Contraseña de aplicación de Google

# --- CONFIGURACIÓN GENERAL ---
st.set_page_config(page_title="Gestión OT - Roble", layout="wide")
UTC_OFFSET = 6 

if not os.path.exists("fotos"):
    os.makedirs("fotos")

# --- FUNCIONES DE APOYO ---
def obtener_fecha_cr():
    return datetime.utcnow() - timedelta(hours=UTC_OFFSET)

def enviar_notificacion(destinatarios, asunto, cuerpo):
    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = ", ".join(destinatarios)
        msg['Subject'] = asunto
        msg.attach(MIMEText(cuerpo, 'plain'))
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, destinatarios, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        st.error(f"Error de envío: {e}")
        return False

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
    if val == 'En Pausa': return 'color: orange; font-weight: bold' # Amarillo/Naranja
    if val == 'Cerrada': return 'color: red; font-weight: bold'
    return ''

# --- CARGA DE DATOS ---
cols_ot = ["OT", "Empleado", "Descripcion", "Inicio", "Tipo", "Estado", "Fin", "Comentarios", "CorreoCopia", "TiempoAcumulado", "Foto"]
df_emp = cargar_datos("empleados.csv", ["Nombre", "Correo"])
df_ot = cargar_datos("ordenes.csv", cols_ot)

# --- NAVEGACIÓN ---
menu = st.sidebar.selectbox("Menú", ["👥 Empleados", "📝 Nueva OT", "🔍 Cierre y Consulta", "📊 Dashboard"])

# --- SECCIÓN: EMPLEADOS ---
if menu == "👥 Empleados":
    st.header("👥 Gestión de Operarios")
    t1, t2, t3 = st.tabs(["➕ Registrar", "✏️ Modificar", "🗑️ Eliminar"])
    
    with t1:
        with st.form("add_emp", clear_on_submit=True):
            n, c = st.text_input("Nombre"), st.text_input("Correo")
            if st.form_submit_button("Registrar"):
                if n and c:
                    df_emp = pd.concat([df_emp, pd.DataFrame([{"Nombre":n,"Correo":c}])], ignore_index=True)
                    guardar_datos(df_emp, "empleados.csv")
                    st.success("Registrado"); st.rerun()

    with t2:
        if not df_emp.empty:
            sel = st.selectbox("Editar a:", df_emp['Nombre'])
            idx = df_emp.index[df_emp['Nombre'] == sel].tolist()[0]
            with st.form("edit_emp"):
                new_n = st.text_input("Nombre", value=df_emp.at[idx, 'Nombre'])
                new_c = st.text_input("Correo", value=df_emp.at[idx, 'Correo'])
                if st.form_submit_button("Actualizar"):
                    df_emp.at[idx, 'Nombre'], df_emp.at[idx, 'Correo'] = new_n, new_c
                    guardar_datos(df_emp, "empleados.csv")
                    st.success("Actualizado"); st.rerun()

    with t3:
        if not df_emp.empty:
            borrar = st.selectbox("Eliminar a:", df_emp['Nombre'])
            conf = st.checkbox(f"Confirmar eliminación de {borrar}")
            if st.button("Eliminar Permanentemente") and conf:
                df_emp = df_emp[df_emp['Nombre'] != borrar]
                guardar_datos(df_emp, "empleados.csv"); st.rerun()
    
    st.table(df_emp)

# --- SECCIÓN: NUEVA OT ---
elif menu == "📝 Nueva OT":
    st.header("📝 Apertura de Orden de Trabajo")
    if df_emp.empty: st.warning("Registre operarios primero")
    else:
        with st.form("f_ot", clear_on_submit=True):
            op = st.selectbox("Operario", df_emp['Nombre'])
            tp = st.radio("Tipo", ["Preventivo", "Correctivo", "Casos 24h", "Casos ISO"], horizontal=True)
            ds = st.text_area("Descripción")
            foto = st.file_uploader("Foto", type=["jpg", "png"])
            cp = st.text_input("Correo copia adicional")
            
            if st.form_submit_button("Generar Orden"):
                id_ot = f"{len(df_ot) + 1:04d}"
                correo_op = df_emp[df_emp['Nombre'] == op]['Correo'].values[0]
                nom_foto = f"OT_{id_ot}.jpg" if foto else "Sin foto"
                if foto:
                    with open(os.path.join("fotos", nom_foto), "wb") as f: f.write(foto.getbuffer())
                
                nueva = {"OT":id_ot, "Empleado":op, "Descripcion":ds, "Inicio":obtener_fecha_cr().strftime("%Y-%m-%d %H:%M:%S"),
                         "Tipo":tp, "Estado":"Abierta", "Fin":"", "Comentarios":"", "CorreoCopia":cp, "TiempoAcumulado":"0", "Foto":nom_foto}
                
                df_ot = pd.concat([df_ot, pd.DataFrame([nueva])], ignore_index=True)
                guardar_datos(df_ot, "ordenes.csv")
                enviar_notificacion(["sa.alterna@gmail.com", correo_op, cp], f"Apertura OT #{id_ot}", f"Detalle: {ds}")
                st.success("OT Generada y enviada"); st.rerun()

# --- SECCIÓN: CIERRE Y CONSULTA ---
elif menu == "🔍 Cierre y Consulta":
    st.header("🔍 Gestión de Cierre y Consulta")
    tab1, tab2 = st.tabs(["Órdenes Activas", "Historial Completo"])
    
    with tab1:
        pendientes = df_ot[df_ot['Estado'].isin(["Abierta", "En Pausa"])].copy()
        if not pendientes.empty:
            ahora = obtener_fecha_cr()
            def calc_dur(row):
                sec = float(row['TiempoAcumulado'])
                if row['Estado'] == "Abierta":
                    sec += (ahora - datetime.strptime(row['Inicio'], "%Y-%m-%d %H:%M:%S")).total_seconds()
                return f"{int(sec//3600)}h {int((sec%3600)//60)}m"
            
            pendientes['Duración'] = pendientes.apply(calc_dur, axis=1)
            st.dataframe(pendientes[["OT", "Estado", "Empleado", "Tipo", "Duración", "Descripcion"]].style.map(estilo_estados, subset=['Estado']), use_container_width=True, hide_index=True)
            
            sel = st.selectbox("Seleccionar OT:", ["---"] + (pendientes['OT'] + " | " + pendientes['Empleado']).tolist())
            if sel != "---":
                idx = df_ot.index[df_ot['OT'] == sel.split(" | ")[0]].tolist()[0]
                if df_ot.at[idx, 'Foto'] != "Sin foto":
                    st.image(os.path.join("fotos", df_ot.at[idx, 'Foto']), width=300)
                
                with st.form("cierre"):
                    est = st.selectbox("Estado", ["Abierta", "En Pausa", "Cerrada"], index=["Abierta", "En Pausa", "Cerrada"].index(df_ot.at[idx, 'Estado']))
                    com = st.text_area("Comentarios", value=df_ot.at[idx, 'Comentarios'])
                    if st.form_submit_button("Guardar"):
                        # Lógica de tiempos
                        if df_ot.at[idx, 'Estado'] == "Abierta":
                            ini = datetime.strptime(df_ot.at[idx, 'Inicio'], "%Y-%m-%d %H:%M:%S")
                            df_ot.at[idx, 'TiempoAcumulado'] = str(float(df_ot.at[idx, 'TiempoAcumulado']) + (obtener_fecha_cr() - ini).total_seconds())
                        
                        df_ot.at[idx, 'Estado'], df_ot.at[idx, 'Comentarios'] = est, com
                        if est == "Abierta": df_ot.at[idx, 'Inicio'] = obtener_fecha_cr().strftime("%Y-%m-%d %H:%M:%S")
                        elif est == "Cerrada": 
                            df_ot.at[idx, 'Fin'] = obtener_fecha_cr().strftime("%Y-%m-%d %H:%M:%S")
                            correo_op = df_emp[df_emp['Nombre'] == df_ot.at[idx, 'Empleado']]['Correo'].values[0]
                            enviar_notificacion(["sa.alterna@gmail.com", correo_op, df_ot.at[idx, 'CorreoCopia']], f"Cierre OT #{df_ot.at[idx, 'OT']}", com)
                        
                        guardar_datos(df_ot, "ordenes.csv"); st.rerun()

    with tab2:
        st.dataframe(df_ot.style.map(estilo_estados, subset=['Estado']), use_container_width=True)

# --- SECCIÓN: DASHBOARD ---
elif menu == "📊 Dashboard":
    st.header("📊 Rendimiento")
    if not df_ot.empty:
        df_ot['Inicio_dt'] = pd.to_datetime(df_ot['Inicio'], errors='coerce')
        rango = st.sidebar.date_input("Fecha", [df_ot['Inicio_dt'].min().date(), obtener_fecha_cr().date()])
        op_s = st.sidebar.selectbox("Operario", ["Todos"] + sorted(df_ot['Empleado'].unique().tolist()))
        
        df_f = df_ot.copy()
        if len(rango) == 2: df_f = df_f[(df_f['Inicio_dt'].dt.date >= rango[0]) & (df_f['Inicio_dt'].dt.date <= rango[1])]
        if op_s != "Todos": df_f = df_f[df_f['Empleado'] == op_s]
        
        df_f['Horas'] = pd.to_numeric(df_f['TiempoAcumulado']).fillna(0) / 3600
        c1, c2, c3 = st.columns(3)
        c1.metric("Total OT", len(df_f))
        c2.metric("Horas", f"{df_f['Horas'].sum():.2f}")
        c3.metric("Cerradas", len(df_f[df_f['Estado'] == "Cerrada"]))
        
        st.plotly_chart(px.bar(df_f, x='OT', y='Horas', color='Tipo'), use_container_width=True)
