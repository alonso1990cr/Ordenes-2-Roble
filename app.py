import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import plotly.express as px
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- CONFIGURACIÓN DE CORREO (SMTP) ---
# Recuerda usar una "Contraseña de Aplicación" de Google
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "tu-correo@gmail.com" 
SENDER_PASSWORD = "tu-clave-de-16-letras" 

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
        # Filtrar destinatarios vacíos o inválidos
        destinos_validos = [d for d in destinatarios if d and "@" in d]
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

# --- CARGA DE DATOS ---
cols_ot = ["OT", "Empleado", "Descripcion", "Inicio", "Tipo", "Estado", "Fin", "Comentarios", "CorreoCopia", "TiempoAcumulado", "Foto"]
df_emp = cargar_datos("empleados.csv", ["Nombre", "Correo"])
df_ot = cargar_datos("ordenes.csv", cols_ot)

# --- NAVEGACIÓN ---
menu = st.sidebar.selectbox("Menú Principal", ["👥 Empleados", "📝 Nueva OT", "🔍 Cierre y Consulta", "📊 Dashboard"])

# --- SECCIÓN: EMPLEADOS ---
if menu == "👥 Empleados":
    st.header("👥 Gestión de Personal")
    t1, t2, t3 = st.tabs(["➕ Registrar", "✏️ Modificar", "🗑️ Eliminar"])
    
    with t1:
        with st.form("add_emp", clear_on_submit=True):
            n, c = st.text_input("Nombre Completo"), st.text_input("Correo Electrónico")
            if st.form_submit_button("Registrar"):
                if n and c:
                    df_emp = pd.concat([df_emp, pd.DataFrame([{"Nombre":n,"Correo":c}])], ignore_index=True)
                    guardar_datos(df_emp, "empleados.csv")
                    st.success("Operario registrado correctamente"); st.rerun()

    with t2:
        if not df_emp.empty:
            sel_m = st.selectbox("Seleccione empleado a editar:", df_emp['Nombre'], key="edit_sel")
            idx_m = df_emp.index[df_emp['Nombre'] == sel_m].tolist()[0]
            with st.form("edit_emp"):
                new_n = st.text_input("Nombre", value=df_emp.at[idx_m, 'Nombre'])
                new_c = st.text_input("Correo", value=df_emp.at[idx_m, 'Correo'])
                if st.form_submit_button("Actualizar Datos"):
                    df_emp.at[idx_m, 'Nombre'], df_emp.at[idx_m, 'Correo'] = new_n, new_c
                    guardar_datos(df_emp, "empleados.csv")
                    st.success("Datos actualizados"); st.rerun()

    with t3:
        if not df_emp.empty:
            borrar = st.selectbox("Seleccione empleado a eliminar:", df_emp['Nombre'], key="del_sel")
            conf = st.checkbox(f"Confirmo que deseo eliminar a {borrar}")
            if st.button("Eliminar Permanentemente") and conf:
                df_emp = df_emp[df_emp['Nombre'] != borrar]
                guardar_datos(df_emp, "empleados.csv")
                st.warning(f"Eliminado: {borrar}"); st.rerun()
    
    st.divider()
    st.table(df_emp)

# --- SECCIÓN: NUEVA OT ---
elif menu == "📝 Nueva OT":
    st.header("📝 Apertura de Orden de Trabajo")
    if df_emp.empty: st.warning("Debe registrar operarios primero.")
    else:
        with st.form("f_ot", clear_on_submit=True):
            op = st.selectbox("Operario Asignado", df_emp['Nombre'])
            tp = st.radio("Tipo de Trabajo", ["Preventivo", "Correctivo", "Casos 24h", "Casos ISO"], horizontal=True)
            ds = st.text_area("Descripción del Hallazgo")
            foto = st.file_uploader("Adjuntar Foto", type=["jpg", "png", "jpeg"])
            cp = st.text_input("Correo de copia adicional")
            
            if st.form_submit_button("Generar y Notificar"):
                id_ot = f"{len(df_ot) + 1:04d}"
                correo_op = df_emp[df_emp['Nombre'] == op]['Correo'].values[0]
                nom_foto = f"OT_{id_ot}.jpg" if foto else "Sin foto"
                if foto:
                    with open(os.path.join("fotos", nom_foto), "wb") as f: f.write(foto.getbuffer())
                
                nueva = {"OT":id_ot, "Empleado":op, "Descripcion":ds, "Inicio":obtener_fecha_cr().strftime("%Y-%m-%d %H:%M:%S"),
                         "Tipo":tp, "Estado":"Abierta", "Fin":"", "Comentarios":"", "CorreoCopia":cp, "TiempoAcumulado":"0", "Foto":nom_foto}
                
                df_ot = pd.concat([df_ot, pd.DataFrame([nueva])], ignore_index=True)
                guardar_datos(df_ot, "ordenes.csv")
                
                cuerpo = f"Nueva OT Generada: #{id_ot}\nOperario: {op}\nTipo: {tp}\nDescripción: {ds}"
                enviar_notificacion(["sa.alterna@gmail.com", correo_op, cp], f"Apertura OT #{id_ot}", cuerpo)
                st.success(f"OT #{id_ot} generada y notificada."); st.rerun()

# --- SECCIÓN: CIERRE Y CONSULTA ---
elif menu == "🔍 Cierre y Consulta":
    st.header("🔍 Gestión de Cierre y Consulta")
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
            
            sel = st.selectbox("Seleccionar OT para gestionar:", ["---"] + (pendientes['OT'] + " | " + pendientes['Empleado']).tolist())
            if sel != "---":
                id_sel = sel.split(" | ")[0]
                idx = df_ot.index[df_ot['OT'] == id_sel].tolist()[0]
                
                # Mostrar Foto si existe
                f_nom = df_ot.at[idx, 'Foto']
                if f_nom != "Sin foto" and os.path.exists(os.path.join("fotos", f_nom)):
                    st.image(os.path.join("fotos", f_nom), width=350, caption=f"Evidencia OT #{id_sel}")
                
                with st.form("cierre_form"):
                    est_act = df_ot.at[idx, 'Estado']
                    nuevo_est = st.selectbox("Cambiar Estado", ["Abierta", "En Pausa", "Cerrada"], index=["Abierta", "En Pausa", "Cerrada"].index(est_act))
                    nuevo_com = st.text_area("Comentarios / Avances", value=df_ot.at[idx, 'Comentarios'])
                    
                    if st.form_submit_button("Actualizar Registro"):
                        ahora_act = obtener_fecha_cr()
                        # Si estaba abierta, sumamos el tiempo transcurrido
                        if df_ot.at[idx, 'Estado'] == "Abierta":
                            ini_dt = datetime.strptime(df_ot.at[idx, 'Inicio'], "%Y-%m-%d %H:%M:%S")
                            dif = (ahora_act - ini_dt).total_seconds()
                            df_ot.at[idx, 'TiempoAcumulado'] = str(float(df_ot.at[idx, 'TiempoAcumulado']) + dif)
                        
                        df_ot.at[idx, 'Estado'], df_ot.at[idx, 'Comentarios'] = nuevo_est, nuevo_com
                        
                        if nuevo_est == "Abierta": 
                            df_ot.at[idx, 'Inicio'] = ahora_act.strftime("%Y-%m-%d %H:%M:%S")
                        elif nuevo_est == "Cerrada":
                            df_ot.at[idx, 'Fin'] = ahora_act.strftime("%Y-%m-%d %H:%M:%S")
                            # Notificación de cierre
                            op_nom = df_ot.at[idx, 'Empleado']
                            op_cor = df_emp[df_emp['Nombre'] == op_nom]['Correo'].values[0]
                            enviar_notificacion(["sa.alterna@gmail.com", op_cor, df_ot.at[idx, 'CorreoCopia']], f"Cierre OT #{id_sel}", f"OT #{id_sel} finalizada.\nComentarios: {nuevo_com}")
                        
                        guardar_datos(df_ot, "ordenes.csv")
                        st.success("Registro actualizado."); st.rerun()

    with tab2:
        st.dataframe(df_ot.style.map(estilo_estados, subset=['Estado']), use_container_width=True)

# --- SECCIÓN: DASHBOARD ---
elif menu == "📊 Dashboard":
    st.header("📊 Dashboard de Rendimiento")
    if df_ot.empty:
        st.info("No hay datos suficientes para generar estadísticas.")
    else:
        # --- FILTROS DE DASHBOARD (RESTAURADOS) ---
        st.sidebar.divider()
        st.sidebar.subheader("🎯 Filtros de Análisis")
        df_ot['Inicio_dt'] = pd.to_datetime(df_ot['Inicio'], errors='coerce')
        
        f_min = df_ot['Inicio_dt'].min().date() if not df_ot['Inicio_dt'].dropna().empty else obtener_fecha_cr().date()
        rango = st.sidebar.date_input("Rango de Fechas", [f_min, obtener_fecha_cr().date()])
        op_sel = st.sidebar.selectbox("Filtrar por Operario", ["Todos"] + sorted(df_ot['Empleado'].unique().tolist()))
        tp_sel = st.sidebar.selectbox("Filtrar por Tipo", ["Todos"] + sorted(df_ot['Tipo'].unique().tolist()))

        # Aplicar Filtros
        df_f = df_ot.copy()
        if len(rango) == 2:
            df_f = df_f[(df_f['Inicio_dt'].dt.date >= rango[0]) & (df_f['Inicio_dt'].dt.date <= rango[1])]
        if op_sel != "Todos": df_f = df_f[df_f['Empleado'] == op_sel]
        if tp_sel != "Todos": df_f = df_f[df_f['Tipo'] == tp_sel]

        # Métricas
        df_f['Horas'] = pd.to_numeric(df_f['TiempoAcumulado'], errors='coerce').fillna(0) / 3600
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Órdenes Totales", len(df_f))
        c2.metric("Horas Invertidas", f"{df_f['Horas'].sum():.2f}")
        c3.metric("Órdenes Cerradas", len(df_f[df_f['Estado'] == "Cerrada"]))
        
        st.divider()
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.plotly_chart(px.bar(df_f, x='OT', y='Horas', color='Tipo', title="Inversión de Tiempo por OT (Horas)"), use_container_width=True)
        with col_g2:
            st.plotly_chart(px.pie(df_f, names='Estado', title="Distribución de Estados", hole=0.4), use_container_width=True)
