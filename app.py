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
st.set_page_config(page_title="Mantenimiento Roble", layout="wide")
UTC_OFFSET = 6 # Costa Rica

# Refresco silencioso cada 1 segundo
st_autorefresh(interval=1000, key="daterefresh")

if not os.path.exists("fotos"):
    os.makedirs("fotos")

# --- CONFIGURACIÓN DE CORREO (SMTP) ---
# Asegúrate de usar una "Contraseña de Aplicación" de Google si tienes 2FA activo
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "ugaldeviquezalonso@gmail.com" 
SENDER_PASSWORD = "krqi xpnr wxua zwfz" 

# --- FUNCIONES DE APOYO ---
def obtener_fecha_cr():
    return datetime.utcnow() - timedelta(hours=UTC_OFFSET)

def mostrar_reloj_discreto():
    hora_actual = obtener_fecha_cr().strftime("%d/%m/%Y %H:%M:%S")
    st.markdown(
        f"""
        <div style="text-align: right; margin-top: -55px; margin-bottom: 20px;">
            <p style="color: #ff4b4b; font-size: 13px; font-family: monospace; font-weight: bold;">
                SISTEMA CR: {hora_actual}
            </p>
        </div>
        """, 
        unsafe_allow_html=True
    )

def enviar_notificacion(destinatarios, asunto, cuerpo):
    """Función robusta para envío de correos."""
    try:
        # Filtrar correos vacíos o inválidos
        destinos_validos = [d.strip() for d in destinatarios if d and "@" in d]
        if not destinos_validos:
            return False
            
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = ", ".join(destinos_validos)
        msg['Subject'] = asunto
        msg.attach(MIMEText(cuerpo, 'plain'))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, destinos_validos, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        st.error(f"Error al enviar correo: {e}")
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

def generar_excel_protegido(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Historial_OT')
        workbook = writer.book
        worksheet = writer.sheets['Historial_OT']
        worksheet.protect('Roble2026', {'autofilter': True})
    return output.getvalue()

# --- CARGA DE DATOS ---
cols_ot = ["OT", "Empleado", "Descripcion", "Inicio", "Tipo", "Estado", "Fin", "Comentarios", "CorreoCopia", "TiempoAcumulado", "Foto"]
df_emp = cargar_datos("empleados.csv", ["Nombre", "Correo"])
df_ot = cargar_datos("ordenes.csv", cols_ot)

# --- NAVEGACIÓN ---
st.sidebar.title("🛠️ Panel de Control")
menu = st.sidebar.selectbox("Seleccione sección:", ["👥 Empleados", "📝 Nueva OT", "🔍 Cierre y Consulta", "📊 Dashboard"])

# --- SECCIÓN: EMPLEADOS ---
if menu == "👥 Empleados":
    st.header("👥 Gestión de Personal")
    mostrar_reloj_discreto()
    t1, t2, t3 = st.tabs(["➕ Registrar", "✏️ Modificar", "🗑️ Eliminar"])
    
    with t1:
        with st.form("add_emp", clear_on_submit=True):
            n = st.text_input("Nombre Completo")
            c = st.text_input("Correo Electrónico")
            if st.form_submit_button("Registrar"):
                if n and c:
                    df_emp = pd.concat([df_emp, pd.DataFrame([{"Nombre":n,"Correo":c}])], ignore_index=True)
                    guardar_datos(df_emp, "empleados.csv")
                    st.success("Empleado registrado"); st.rerun()

    with t2:
        if not df_emp.empty:
            sel_m = st.selectbox("Seleccione empleado a editar:", df_emp['Nombre'])
            idx_m = df_emp.index[df_emp['Nombre'] == sel_m].tolist()[0]
            with st.form("edit_emp"):
                new_n = st.text_input("Nombre", value=df_emp.at[idx_m, 'Nombre'])
                new_c = st.text_input("Correo", value=df_emp.at[idx_m, 'Correo'])
                if st.form_submit_button("Actualizar"):
                    df_emp.at[idx_m, 'Nombre'], df_emp.at[idx_m, 'Correo'] = new_n, new_c
                    guardar_datos(df_emp, "empleados.csv")
                    st.success("Actualizado"); st.rerun()

    with t3:
        if not df_emp.empty:
            borrar = st.selectbox("Seleccione empleado:", df_emp['Nombre'])
            if st.button("Eliminar") and st.checkbox("Confirmar"):
                df_emp = df_emp[df_emp['Nombre'] != borrar]
                guardar_datos(df_emp, "empleados.csv"); st.rerun()
    st.table(df_emp)

# --- SECCIÓN: NUEVA OT ---
elif menu == "📝 Nueva OT":
    st.header("📝 Apertura de Orden de Trabajo")
    mostrar_reloj_discreto()
    if df_emp.empty:
        st.warning("Registre personal primero.")
    else:
        with st.form("f_ot", clear_on_submit=True):
            op = st.selectbox("Operario Asignado", df_emp['Nombre'])
            tp = st.radio("Tipo", ["Preventivo", "Correctivo", "SNC alta", "SNC media","SNC baja"], horizontal=True)
            ds = st.text_area("Descripción")
            foto = st.file_uploader("Foto", type=["jpg", "png", "jpeg"])
            cp = st.text_input("Correo adicional para copia")
            
            if st.form_submit_button("Generar Orden"):
                id_ot = f"{len(df_ot) + 1:04d}"
                # Obtener correo del operario seleccionado
                correo_op = df_emp[df_emp['Nombre'] == op]['Correo'].values[0]
                
                nom_foto = f"OT_{id_ot}.jpg" if foto else "Sin foto"
                if foto:
                    with open(os.path.join("fotos", nom_foto), "wb") as f: f.write(foto.getbuffer())
                
                nueva = {"OT":id_ot, "Empleado":op, "Descripcion":ds, "Inicio":obtener_fecha_cr().strftime("%Y-%m-%d %H:%M:%S"),
                         "Tipo":tp, "Estado":"Abierta", "Fin":"", "Comentarios":"", "CorreoCopia":cp, "TiempoAcumulado":"0", "Foto":nom_foto}
                
                df_ot = pd.concat([df_ot, pd.DataFrame([nueva])], ignore_index=True)
                guardar_datos(df_ot, "ordenes.csv")
                
                # ENVÍO DE CORREO AL APERTURAR
                lista_correos = ["sa.alterna@gmail.com", correo_op, cp]
                cuerpo = f"Se ha generado la OT #{id_ot}\nOperario: {op}\nTipo: {tp}\nDescripción: {ds}"
                enviar_notificacion(lista_correos, f"Apertura OT #{id_ot}", cuerpo)
                
                st.success(f"OT #{id_ot} generada y correos enviados."); st.rerun()

# --- SECCIÓN: CIERRE Y CONSULTA ---
elif menu == "🔍 Cierre y Consulta":
    st.header("🔍 Gestión de Cierre y Consulta")
    mostrar_reloj_discreto()
    tab1, tab2 = st.tabs(["Órdenes Activas", "Historial Completo"])
    
    with tab1:
        pendientes = df_ot[df_ot['Estado'].isin(["Abierta", "En Pausa"])].copy()
        if not pendientes.empty:
            sel = st.selectbox("Seleccionar OT:", ["---"] + (pendientes['OT'] + " | " + pendientes['Empleado']).tolist())
            if sel != "---":
                idx = df_ot.index[df_ot['OT'] == sel.split(" | ")[0]].tolist()[0]
                if df_ot.at[idx, 'Foto'] != "Sin foto":
                    st.image(os.path.join("fotos", df_ot.at[idx, 'Foto']), width=300)
                
                with st.form("gestion_ot"):
                    nuevo_est = st.selectbox("Estado", ["Abierta", "En Pausa", "Cerrada"], index=["Abierta", "En Pausa", "Cerrada"].index(df_ot.at[idx, 'Estado']))
                    nuevo_com = st.text_area("Comentarios", value=df_ot.at[idx, 'Comentarios'])
                    if st.form_submit_button("Actualizar OT"):
                        df_ot.at[idx, 'Estado'], df_ot.at[idx, 'Comentarios'] = nuevo_est, nuevo_com
                        
                        if nuevo_est == "Cerrada":
                            df_ot.at[idx, 'Fin'] = obtener_fecha_cr().strftime("%Y-%m-%d %H:%M:%S")
                            # Obtener correos para notificación de cierre
                            op_nombre = df_ot.at[idx, 'Empleado']
                            correo_op = df_emp[df_emp['Nombre'] == op_nombre]['Correo'].values[0]
                            correo_cp = df_ot.at[idx, 'CorreoCopia']
                            
                            lista_cierre = ["sa.alterna@gmail.com", correo_op, correo_cp]
                            cuerpo_cierre = f"Cierre de OT #{df_ot.at[idx, 'OT']}\nOperario: {op_nombre}\nResolución: {nuevo_com}"
                            enviar_notificacion(lista_cierre, f"Cierre OT #{df_ot.at[idx, 'OT']}", cuerpo_cierre)
                        
                        guardar_datos(df_ot, "ordenes.csv"); st.rerun()

    with tab2:
        st.dataframe(df_ot, use_container_width=True)
        if not df_ot.empty:
            st.download_button("📥 Descargar Excel", generar_excel_protegido(df_ot), "Reporte_OT.xlsx")

# --- SECCIÓN: DASHBOARD ---
elif menu == "📊 Dashboard":
    st.header("📊 Dashboard")
    mostrar_reloj_discreto()
    if not df_ot.empty:
        # Filtros básicos para el dashboard
        op_sel = st.sidebar.selectbox("Filtrar Operario", ["Todos"] + sorted(df_ot['Empleado'].unique().tolist()))
        df_f = df_ot.copy()
        if op_sel != "Todos": df_f = df_f[df_f['Empleado'] == op_sel]
        
        st.metric("Total de Órdenes", len(df_f))
        st.plotly_chart(px.pie(df_f, names='Estado', title="Distribución por Estado"), use_container_width=True)
