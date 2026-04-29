import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import plotly.express as px
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- CONFIGURACIÓN DE CORREO ---
# NOTA: Debes usar una "Contraseña de Aplicación" de Google, no tu clave normal.
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "tu-correo@gmail.com" 
SENDER_PASSWORD = "tu-clave-de-aplicacion" # Cámbiala por tu clave real

# --- CONFIGURACIÓN GENERAL ---
st.set_page_config(page_title="Gestión OT - Roble", layout="wide")
UTC_OFFSET = 6 

if not os.path.exists("fotos"):
    os.makedirs("fotos")

# --- FUNCIONES DE ENVÍO ---
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
        st.error(f"Error enviando correo: {e}")
        return False

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

# --- MENÚ LATERAL ---
st.sidebar.title("🛠️ Navegación Principal")
menu = st.sidebar.selectbox("Seleccione:", ["👥 Empleados", "📝 Nueva OT", "🔍 Cierre y Consulta", "📊 Dashboard"])

# --- LÓGICA DE SECCIONES ---

if menu == "👥 Empleados":
    st.header("👥 Gestión de Operarios")
    # ... (Se mantiene igual: Registrar, Modificar, Eliminar)
    tab_reg, tab_mod, tab_del = st.tabs(["➕ Registrar", "✏️ Modificar", "🗑️ Eliminar"])
    with tab_reg:
        with st.form("add_emp", clear_on_submit=True):
            n = st.text_input("Nombre Completo")
            c = st.text_input("Correo Electrónico")
            if st.form_submit_button("Registrar"):
                if n and c:
                    df_emp = pd.concat([df_emp, pd.DataFrame([{"Nombre":n,"Correo":c}])], ignore_index=True)
                    guardar_datos(df_emp, "empleados.csv")
                    st.success(f"Operario {n} registrado.")
                    st.rerun()
    # (Omitido por brevedad: tab_mod y tab_del funcionan igual que antes)

elif menu == "📝 Nueva OT":
    st.header("📝 Apertura de Orden de Trabajo")
    if df_emp.empty:
        st.warning("Registre operarios primero.")
    else:
        with st.form("f_ot", clear_on_submit=True):
            op_nombre = st.selectbox("Operario Asignado", df_emp['Nombre'])
            tp = st.radio("Tipo", ["Preventivo", "Correctivo", "Casos 24h", "Casos ISO"], horizontal=True)
            ds = st.text_area("Descripción del Hallazgo")
            archivo_foto = st.file_uploader("Foto", type=["jpg", "png", "jpeg"])
            cp = st.text_input("Correo de copia adicional")
            
            if st.form_submit_button("Generar Orden"):
                if ds and cp:
                    id_ot = f"{len(df_ot) + 1:04d}"
                    # Obtener correo del operario
                    op_correo = df_emp[df_emp['Nombre'] == op_nombre]['Correo'].values[0]
                    
                    nueva = {"OT": id_ot, "Empleado": op_nombre, "Descripcion": ds, 
                             "Inicio": obtener_fecha_cr().strftime("%Y-%m-%d %H:%M:%S"),
                             "Tipo": tp, "Estado": "Abierta", "Fin": "", "Comentarios": "", 
                             "CorreoCopia": cp, "TiempoAcumulado": "0", "Foto": f"OT_{id_ot}.jpg" if archivo_foto else "Sin foto"}
                    
                    df_ot = pd.concat([df_ot, pd.DataFrame([nueva])], ignore_index=True)
                    guardar_datos(df_ot, "ordenes.csv")
                    
                    # Preparar correos
                    destinos = ["sa.alterna@gmail.com", op_correo, cp]
                    cuerpo = f"Nueva OT Generada: #{id_ot}\nOperario: {op_nombre}\nTipo: {tp}\nHallazgo: {ds}\nFecha: {nueva['Inicio']}"
                    enviar_notificacion(destinos, f"Apertura OT #{id_ot} - {op_nombre}", cuerpo)
                    
                    st.success(f"OT #{id_ot} enviada por correo."); st.rerun()

elif menu == "🔍 Cierre y Consulta":
    st.header("🔍 Gestión de Cierre y Consulta")
    tab1, tab2 = st.tabs(["Órdenes Activas", "Historial Completo"])
    
    with tab1:
        pendientes = df_ot[df_ot['Estado'].str.contains("Abierta|En Pausa", case=False, na=False)].copy()
        if not pendientes.empty:
            # (Lógica de tabla con colores ya implementada anteriormente)
            opciones = ["--- Seleccione ---"] + (pendientes['OT'] + " | " + pendientes['Empleado']).tolist()
            sel = st.selectbox("Escoger OT:", opciones)

            if sel != "--- Seleccione ---":
                id_sel = sel.split(" | ")[0]
                idx = df_ot.index[df_ot['OT'] == id_sel].tolist()[0]
                
                with st.form("form_cierre"):
                    nuevo_est = st.selectbox("Estado", ["Abierta", "En Pausa", "Cerrada"], index=0)
                    coment = st.text_area("Avances", value=df_ot.at[idx, 'Comentarios'])
                    
                    if st.form_submit_button("Actualizar y Notificar"):
                        # ... (Cálculo de tiempo acumulado igual que antes)
                        df_ot.at[idx, 'Estado'] = nuevo_est
                        df_ot.at[idx, 'Comentarios'] = coment
                        guardar_datos(df_ot, "ordenes.csv")
                        
                        if nuevo_est == "Cerrada":
                            op_nom = df_ot.at[idx, 'Empleado']
                            op_cor = df_emp[df_emp['Nombre'] == op_nom]['Correo'].values[0]
                            destinos = ["sa.alterna@gmail.com", op_cor, df_ot.at[idx, 'CorreoCopia']]
                            cuerpo = f"OT #{id_sel} CERRADA\nOperario: {op_nom}\nComentarios: {coment}"
                            enviar_notificacion(destinos, f"CIERRE OT #{id_sel}", cuerpo)
                        
                        st.success("Actualizado y notificado."); st.rerun()
# ... (Dashboard se mantiene igual)
