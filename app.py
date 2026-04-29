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
from streamlit_autorefresh import st_autorefresh  # Necesario para los segundos

# --- CONFIGURACIÓN DE CORREO (SMTP) ---
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "tu-correo@gmail.com" 
SENDER_PASSWORD = "tu-clave-de-16-letras" 

# --- CONFIGURACIÓN GENERAL ---
st.set_page_config(page_title="Gestión OT - Roble", layout="wide")
UTC_OFFSET = 6

# Refresco automático cada 1000ms (1 segundo) para actualizar el reloj
st_autorefresh(interval=1000, key="daterefresh")

if not os.path.exists("fotos"):
    os.makedirs("fotos")

# --- FUNCIONES DE APOYO ---
def obtener_fecha_cr():
    return datetime.utcnow() - timedelta(hours=UTC_OFFSET)

def mostrar_reloj_rojo():
    hora_actual = obtener_fecha_cr().strftime("%d/%m/%Y %H:%M:%S")
    st.markdown(
        f"""
        <div style="text-align: right; padding-bottom: 20px;">
            <span style="color: #ff4b4b; font-size: 24px; font-weight: bold; font-family: monospace;">
                🕒 {hora_actual}
            </span>
        </div>
        """, 
        unsafe_allow_html=True
    )

def enviar_notificacion(destinatarios, asunto, cuerpo):
    try:
        destinos_validos = [d for d in destinatarios if d and "@" in d]
        if not destinos_validos: return False
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

# --- CONTENIDO POR SECCIÓN ---
if menu == "👥 Empleados":
    st.header("👥 Gestión de Personal")
    mostrar_reloj_rojo()
    t1, t2, t3 = st.tabs(["➕ Registrar", "✏️ Modificar", "🗑️ Eliminar"])
    
    with t1:
        with st.form("add_emp", clear_on_submit=True):
            n, c = st.text_input("Nombre Completo"), st.text_input("Correo Electrónico")
            if st.form_submit_button("Registrar"):
                if n and c:
                    df_emp = pd.concat([df_emp, pd.DataFrame([{"Nombre":n,"Correo":c}])], ignore_index=True)
                    guardar_datos(df_emp, "empleados.csv")
                    st.success("Registrado"); st.rerun()
    # (Resto del código de empleados igual...)
    st.table(df_emp)

elif menu == "📝 Nueva OT":
    st.header("📝 Apertura de Orden de Trabajo")
    mostrar_reloj_rojo()
    if df_emp.empty: st.warning("Registre operarios primero")
    else:
        with st.form("f_ot", clear_on_submit=True):
            op = st.selectbox("Operario Asignado", df_emp['Nombre'])
            tp = st.radio("Tipo", ["Preventivo", "Correctivo", "Casos 24h", "Casos ISO"], horizontal=True)
            ds = st.text_area("Descripción")
            foto = st.file_uploader("Foto", type=["jpg", "png", "jpeg"])
            cp = st.text_input("Copia a")
            
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
                enviar_notificacion(["sa.alterna@gmail.com", correo_op, cp], f"Apertura OT #{id_ot}", f"OT: #{id_ot}\nOperario: {op}\nHallazgo: {ds}")
                st.success(f"OT #{id_ot} guardada."); st.rerun()

elif menu == "🔍 Cierre y Consulta":
    st.header("🔍 Gestión de Cierre y Consulta")
    mostrar_reloj_rojo()
    tab1, tab2 = st.tabs(["Órdenes Activas", "Historial Completo"])
    
    with tab1:
        pendientes = df_ot[df_ot['Estado'].isin(["Abierta", "En Pausa"])].copy()
        if not pendientes.empty:
            ahora = obtener_fecha_cr()
            def calc_dur(row):
                try:
                    sec = float(row['TiempoAcumulado'])
                    if row['Estado'] == "Abierta":
                        sec += (ahora - datetime.strptime(row['Inicio'], "%Y-%m-%d %H:%M:%S")).total_seconds()
                    return f"{int(sec//3600)}h {int((sec%3600)//60)}m"
                except: return "0h 0m"
            
            pendientes['Duración'] = pendientes.apply(calc_dur, axis=1)
            st.dataframe(pendientes[["OT", "Estado", "Empleado", "Tipo", "Duración", "Descripcion"]].style.map(estilo_estados, subset=['Estado']), use_container_width=True, hide_index=True)
            
            sel = st.selectbox("Seleccionar OT:", ["---"] + (pendientes['OT'] + " | " + pendientes['Empleado']).tolist())
            if sel != "---":
                id_sel = sel.split(" | ")[0]
                idx = df_ot.index[df_ot['OT'] == id_sel].tolist()[0]
                
                f_nom = df_ot.at[idx, 'Foto']
                ruta_foto = os.path.join("fotos", f_nom)
                if f_nom != "Sin foto" and os.path.exists(ruta_foto):
                    try:
                        img_valida = Image.open(ruta_foto)
                        st.image(img_valida, width=350)
                    except: st.warning("⚠️ Imagen no legible.")

                with st.form("cierre_form"):
                    nuevo_est = st.selectbox("Estado", ["Abierta", "En Pausa", "Cerrada"], index=["Abierta", "En Pausa", "Cerrada"].index(df_ot.at[idx, 'Estado']))
                    nuevo_com = st.text_area("Avances", value=df_ot.at[idx, 'Comentarios'])
                    
                    if st.form_submit_button("Actualizar Registro"):
                        ahora_act = obtener_fecha_cr()
                        if df_ot.at[idx, 'Estado'] == "Abierta":
                            ini_dt = datetime.strptime(df_ot.at[idx, 'Inicio'], "%Y-%m-%d %H:%M:%S")
                            df_ot.at[idx, 'TiempoAcumulado'] = str(float(df_ot.at[idx, 'TiempoAcumulado']) + (ahora_act - ini_dt).total_seconds())
                        
                        df_ot.at[idx, 'Estado'], df_ot.at[idx, 'Comentarios'] = nuevo_est, nuevo_com
                        if nuevo_est == "Abierta": df_ot.at[idx, 'Inicio'] = ahora_act.strftime("%Y-%m-%d %H:%M:%S")
                        elif nuevo_est == "Cerrada":
                            df_ot.at[idx, 'Fin'] = ahora_act.strftime("%Y-%m-%d %H:%M:%S")
                            correo_op = df_emp[df_emp['Nombre'] == df_ot.at[idx, 'Empleado']]['Correo'].values[0]
                            enviar_notificacion(["sa.alterna@gmail.com", correo_op, df_ot.at[idx, 'CorreoCopia']], f"Cierre OT #{id_sel}", f"Cierre OT #{id_sel}.\nComentarios: {nuevo_com}")
                        
                        guardar_datos(df_ot, "ordenes.csv"); st.rerun()

    with tab2:
        st.dataframe(df_ot.style.map(estilo_estados, subset=['Estado']), use_container_width=True)
        if not df_ot.empty:
            excel_data = generar_excel_protegido(df_ot)
            st.download_button(label="📥 Descargar Reporte Excel", data=excel_data, file_name="Reporte_OT.xlsx")

elif menu == "📊 Dashboard":
    st.header("📊 Dashboard de Rendimiento")
    mostrar_reloj_rojo()
    if not df_ot.empty:
        df_f = df_ot.copy()
        df_f['Horas'] = pd.to_numeric(df_f['TiempoAcumulado'], errors='coerce').fillna(0) / 3600
        st.plotly_chart(px.bar(df_f, x='OT', y='Horas', color='Tipo'), use_container_width=True)
