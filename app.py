import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Sistema Roble - Gestión OT", layout="wide")

# --- PARÁMETROS CONSTANTES ---
UTC_OFFSET = 6  # Costa Rica es UTC-6
CORREO_COPIA = "sa.alterna@gmail.com"

# --- FUNCIONES DE APOYO ---

def obtener_fecha_cr():
    """Retorna la fecha/hora actual ajustada a Costa Rica"""
    return datetime.utcnow() - timedelta(hours=UTC_OFFSET)

def enviar_correo(destinatario_emp, asunto, cuerpo):
    """Envía correo usando los Secrets de Streamlit"""
    try:
        user = st.secrets["emails"]["sender_user"]
        password = st.secrets["emails"]["sender_password"]
        
        msg = MIMEMultipart()
        msg['From'] = user
        msg['To'] = f"{destinatario_emp}, {CORREO_COPIA}"
        msg['Subject'] = asunto
        msg.attach(MIMEText(cuerpo, 'plain'))
        
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(user, password)
        server.sendmail(user, [destinatario_emp, CORREO_COPIA], msg.as_string())
        server.quit()
        return True
    except Exception as e:
        st.error(f"Error al enviar correo: {e}")
        return False

def calcular_duracion_laboral(inicio, fin):
    """Calcula horas laboradas: L-V (8am-5pm), S (7am-12md). Resta 1h de almuerzo L-V."""
    total_segundos = 0
    curr = inicio
    while curr < fin:
        # Horarios según día
        if curr.weekday() < 5: # Lunes a Viernes
            h_inicio, h_fin = 8, 17
            tiene_almuerzo = True
        elif curr.weekday() == 5: # Sábado
            h_inicio, h_fin = 7, 12
            tiene_almuerzo = False
        else: # Domingo
            curr = (curr + timedelta(days=1)).replace(hour=8, minute=0)
            continue
        
        trabajo_inicio = curr.replace(hour=h_inicio, minute=0, second=0)
        trabajo_fin = curr.replace(hour=h_fin, minute=0, second=0)
        
        entrada = max(curr, trabajo_inicio)
        salida = min(fin, trabajo_fin)
        
        if entrada < salida:
            segundos_dia = (salida - entrada).total_seconds()
            # Restar almuerzo (12md-1pm) si el periodo lo cubre
            if tiene_almuerzo and entrada.hour < 12 and salida.hour >= 13:
                segundos_dia -= 3600
            total_segundos += max(0, segundos_dia)
            
        curr = (curr + timedelta(days=1)).replace(hour=h_inicio, minute=0)
    
    return timedelta(seconds=total_segundos)

def cargar_datos(archivo, columnas):
    if os.path.exists(archivo):
        return pd.read_csv(archivo)
    return pd.DataFrame(columns=columnas)

# --- LÓGICA DE LA APP ---

st.title("🏗️ Gestión de Órdenes de Trabajo - Grupo Roble")

menu = st.sidebar.selectbox("Seleccione una opción", ["Empleados", "Crear Orden de Trabajo", "Cierre y Consulta"])

# 1. GESTIÓN DE EMPLEADOS
if menu == "Empleados":
    st.header("👥 Registro de Empleados")
    df_emp = cargar_datos("empleados.csv", ["Nombre", "Correo"])
    
    with st.expander("Añadir / Editar Empleado"):
        nom = st.text_input("Nombre Completo")
        ema = st.text_input("Correo electrónico")
        if st.button("Guardar Datos"):
            if nom and ema:
                df_emp = df_emp[df_emp['Nombre'] != nom] # Eliminar si ya existe para actualizar
                nuevo = pd.DataFrame([{"Nombre": nom, "Correo": ema}])
                df_emp = pd.concat([df_emp, nuevo], ignore_index=True)
                df_emp.to_csv("empleados.csv", index=False)
                st.success("Guardado correctamente.")
                st.rerun()

    st.subheader("Lista de Personal")
    st.dataframe(df_emp, use_container_width=True)
    
    if not df_emp.empty:
        borrar = st.selectbox("Seleccione para eliminar", df_emp['Nombre'])
        if st.button("Eliminar Empleado"):
            df_emp = df_emp[df_emp['Nombre'] != borrar]
            df_emp.to_csv("empleados.csv", index=False)
            st.rerun()

# 2. CREAR ORDEN DE TRABAJO
elif menu == "Crear Orden de Trabajo":
    st.header("📝 Nueva Orden de Trabajo")
    df_emp = cargar_datos("empleados.csv", ["Nombre", "Correo"])
    df_ot = cargar_datos("ordenes.csv", ["OT", "Empleado", "Descripcion", "Inicio", "Tipo", "Estado", "Fin", "Comentarios"])

    if df_emp.empty:
        st.warning("Debe registrar empleados primero.")
    else:
        with st.form("form_ot"):
            emp_sel = st.selectbox("Asignar a:", df_emp['Nombre'])
            tipo_ot = st.radio("Tipo de mantenimiento:", ["Preventivo", "Correctivo"])
            desc_ot = st.text_area("Descripción detallada")
            
            if st.form_submit_button("Generar y Enviar"):
                fecha_inicio = obtener_fecha_cr()
                num_ot = fecha_inicio.strftime("%Y%m%d-%H%M")
                
                # Guardar en CSV
                nueva_ot = {
                    "OT": num_ot, "Empleado": emp_sel, "Descripcion": desc_ot,
                    "Inicio": fecha_inicio.strftime("%Y-%m-%d %H:%M:%S"),
                    "Tipo": tipo_ot, "Estado": "Abierta", "Fin": "", "Comentarios": ""
                }
                df_ot = pd.concat([df_ot, pd.DataFrame([nueva_ot])], ignore_index=True)
                df_ot.to_csv("ordenes.csv", index=False)
                
                # Enviar correo
                correo_destino = df_emp[df_emp['Nombre'] == emp_sel]['Correo'].values[0]
                cuerpo = f"Nueva OT #{num_ot}\nEmpleado: {emp_sel}\nTipo: {tipo_ot}\nDescripción: {desc_ot}"
                enviar_correo(correo_destino, f"Aviso: Nueva OT {num_ot}", cuerpo)
                st.success(f"Orden #{num_ot} creada con éxito.")

# 3. CIERRE Y CONSULTA
elif menu == "Cierre y Consulta":
    st.header("🔍 Consulta y Cierre de Órdenes")
    df_ot = cargar_datos("ordenes.csv", [])
    df_emp = cargar_datos("empleados.csv", [])
    
    if not df_ot.empty:
        persona = st.selectbox("Consultar historial de:", df_emp['Nombre'].unique())
        historial = df_ot[df_ot['Empleado'] == persona].tail(3)
        st.write("Últimas 3 órdenes:")
        st.table(historial)
        
        # Selección para cerrar
        ots_abiertas = historial[historial['Estado'] == "Abierta"]['OT'].tolist()
        if ots_abiertas:
            ot_a_cerrar = st.selectbox("Seleccione OT para CERRAR", ots_abiertas)
            coment = st.text_area("Comentarios de cierre")
            
            if st.button("Finalizar Orden"):
                fecha_fin = obtener_fecha_cr()
                # Buscar inicio
                ini_str = df_ot.loc[df_ot['OT'] == ot_a_cerrar, 'Inicio'].values[0]
                ini_dt = datetime.strptime(ini_str, "%Y-%m-%d %H:%M:%S")
                
                duracion = calcular_duracion_laboral(ini_dt, fecha_fin)
                
                # Actualizar CSV
                df_ot.loc[df_ot['OT'] == ot_a_cerrar, ['Estado', 'Fin', 'Comentarios']] = ["Cerrada", fecha_fin.strftime("%Y-%m-%d %H:%M:%S"), coment]
                df_ot.to_csv("ordenes.csv", index=False)
                
                # Enviar correo de cierre
                correo_destino = df_emp[df_emp['Nombre'] == persona]['Correo'].values[0]
                cuerpo_fin = f"OT #{ot_a_cerrar} CERRADA\nDuración: {duracion}\nComentarios: {coment}"
                enviar_correo(correo_destino, f"Cierre de OT {ot_a_cerrar}", cuerpo_fin)
                st.info(f"Orden cerrada. Tiempo laborado: {duracion}")
                st.rerun()
        else:
            st.info("No hay órdenes abiertas para este empleado entre las últimas 3.")

# TABLA GENERAL CON EMOJIS
st.divider()
st.subheader("📋 Resumen General de Actividades")
df_vista = cargar_datos("ordenes.csv", [])
if not df_vista.empty:
    def format_row(row):
        if row['Estado'] == "Cerrada":
            ini = datetime.strptime(row['Inicio'], "%Y-%m-%d %H:%M:%S")
            fin = datetime.strptime(row['Fin'], "%Y-%m-%d %H:%M:%S")
            d = calcular_duracion_laboral(ini, fin)
            horas = d.total_seconds() / 3600
            emoji = "⚡" if horas < 4 else "⏳" if horas < 9 else "🐢"
            return f"{d} {emoji}"
        return "Trabajando... 🛠️"

    df_vista['Duración'] = df_vista.apply(format_row, axis=1)
    st.dataframe(df_vista[["OT", "Empleado", "Tipo", "Estado", "Duración", "Descripcion"]], use_container_width=True)
