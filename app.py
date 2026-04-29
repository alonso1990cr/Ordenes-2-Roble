import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Gestión OT - Roble", layout="wide")
UTC_OFFSET = 6
CORREO_COPIA = "sa.alterna@gmail.com"

# --- FUNCIONES DE PERSISTENCIA ---
def cargar_datos(archivo, columnas):
    if os.path.exists(archivo):
        # Forzamos a que todas las columnas se lean como texto (string) para evitar el TypeError
        df = pd.read_csv(archivo, dtype=str)
        # Si faltan columnas por alguna razón, las agregamos
        for col in columnas:
            if col not in df.columns:
                df[col] = ""
        return df
    return pd.DataFrame(columns=columnas)

def guardar_datos(df, archivo):
    df.to_csv(archivo, index=False)

# --- FUNCIONES TÉCNICAS ---
def obtener_fecha_cr():
    return datetime.utcnow() - timedelta(hours=UTC_OFFSET)

def enviar_correo(destinatario, asunto, cuerpo):
    try:
        user = st.secrets["emails"]["sender_user"]
        password = st.secrets["emails"]["sender_password"]
        msg = MIMEMultipart()
        msg['From'] = user
        msg['To'] = f"{destinatario}, {CORREO_COPIA}"
        msg['Subject'] = asunto
        msg.attach(MIMEText(cuerpo, 'plain'))
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(user, password)
        server.sendmail(user, [destinatario, CORREO_COPIA], msg.as_string())
        server.quit()
        return True
    except:
        return False

def calcular_duracion_laboral(inicio, fin):
    total_segundos = 0
    curr = inicio
    while curr < fin:
        if curr.weekday() < 5: # Lunes-Viernes
            h_ini, h_fin, almuerzo = 8, 17, True
        elif curr.weekday() == 5: # Sábado
            h_ini, h_fin, almuerzo = 7, 12, False
        else: # Domingo
            curr = (curr + timedelta(days=1)).replace(hour=8, minute=0)
            continue
        
        ent = max(curr, curr.replace(hour=h_ini, minute=0, second=0))
        sal = min(fin, curr.replace(hour=h_fin, minute=0, second=0))
        
        if ent < sal:
            seg = (sal - ent).total_seconds()
            if almuerzo and ent.hour < 12 and sal.hour >= 13:
                seg -= 3600
            total_segundos += max(0, seg)
        curr = (curr + timedelta(days=1)).replace(hour=h_ini, minute=0)
    return timedelta(seconds=total_segundos)

# --- INTERFAZ ---
menu = st.sidebar.selectbox("MENÚ PRINCIPAL", ["Gestión de Empleados", "Nueva Orden de Trabajo", "Cierre y Consulta de OT"])

# 1. GESTIÓN DE EMPLEADOS
if menu == "Gestión de Empleados":
    st.header("👥 Registro de Operarios")
    df_emp = cargar_datos("empleados.csv", ["Nombre", "Correo"])
    
    with st.form("form_empleados"):
        st.write("### Añadir o Modificar")
        nom = st.text_input("Nombre Completo del Empleado").strip()
        ema = st.text_input("Correo Electrónico").strip()
        btn_guardar = st.form_submit_button("Guardar / Actualizar")
        
        if btn_guardar:
            if nom and ema:
                df_emp = df_emp[df_emp['Nombre'].str.upper() != nom.upper()]
                nuevo = pd.DataFrame([{"Nombre": nom, "Correo": ema}])
                df_emp = pd.concat([df_emp, nuevo], ignore_index=True)
                guardar_datos(df_emp, "empleados.csv")
                st.success(f"Empleado {nom} registrado correctamente.")
            else:
                st.error("Por favor llene todos los campos.")

    st.subheader("Personal Registrado")
    st.dataframe(df_emp, use_container_width=True)

# 2. NUEVA ORDEN DE TRABAJO
elif menu == "Nueva Orden de Trabajo":
    st.header("📝 Apertura de Orden de Trabajo")
    df_emp = cargar_datos("empleados.csv", ["Nombre", "Correo"])
    df_ot = cargar_datos("ordenes.csv", ["OT", "Empleado", "Descripcion", "Inicio", "Tipo", "Estado", "Fin", "Comentarios"])

    if df_emp.empty:
        st.warning("⚠️ No hay empleados registrados.")
    else:
        with st.form("form_nueva_ot"):
            operario = st.selectbox("Operario Asignado", df_emp['Nombre'])
            tipo = st.radio("Tipo de Trabajo", ["Preventivo", "Correctivo"])
            desc = st.text_area("Descripción de la labor")
            
            if st.form_submit_button("Generar Orden"):
                ahora = obtener_fecha_cr()
                num_ot = ahora.strftime("%Y%m%d-%H%M")
                
                nueva_fila = {
                    "OT": num_ot, "Empleado": operario, "Descripcion": desc,
                    "Inicio": ahora.strftime("%Y-%m-%d %H:%M:%S"),
                    "Tipo": tipo, "Estado": "Abierta", "Fin": "", "Comentarios": ""
                }
                # Convertimos a DataFrame asegurando que todo sea texto
                df_nueva = pd.DataFrame([nueva_fila]).astype(str)
                df_ot = pd.concat([df_ot, df_nueva], ignore_index=True)
                guardar_datos(df_ot, "ordenes.csv")
                
                correo_dest = df_emp[df_emp['Nombre'] == operario]['Correo'].values[0]
                enviar_correo(correo_dest, f"Nueva OT #{num_ot}", f"OT #{num_ot}\nDescripción: {desc}")
                st.success(f"OT #{num_ot} creada.")

# 3. CIERRE Y CONSULTA (Aquí estaba el error)
elif menu == "Cierre y Consulta de OT":
    st.header("🔍 Seguimiento de Órdenes")
    df_ot = cargar_datos("ordenes.csv", ["OT", "Empleado", "Descripcion", "Inicio", "Tipo", "Estado", "Fin", "Comentarios"])
    df_emp = cargar_datos("empleados.csv", ["Nombre", "Correo"])
    
    if not df_ot.empty:
        ot_id = st.selectbox("Seleccione el ID de la OT para trabajar:", df_ot['OT'].unique())
        
        # Seleccionamos la fila específica
        idx = df_ot.index[df_ot['OT'] == ot_id].tolist()[0]
        datos_actuales = df_ot.loc[idx]
        
        with st.form("form_edicion"):
            st.write(f"### Editando Orden #{ot_id}")
            # Usamos str() para asegurar que no pasamos valores nulos al widget
            comentario_previo = str(datos_actuales['Comentarios']) if pd.notna(datos_actuales['Comentarios']) else ""
            
            nuevo_comentario = st.text_area("Comentarios de cierre o avance:", value=comentario_previo)
            nuevo_estado = st.selectbox("Estado actual:", ["Abierta", "Cerrada"], 
                                       index=0 if datos_actuales['Estado']=="Abierta" else 1)
            
            if st.form_submit_button("Guardar Cambios y Sobreescribir"):
                # ACTUALIZACIÓN SEGURA: Convertimos la columna a objeto (texto) antes de asignar
                df_ot['Comentarios'] = df_ot['Comentarios'].astype(object)
                df_ot.at[idx, 'Comentarios'] = str(nuevo_comentario)
                df_ot.at[idx, 'Estado'] = str(nuevo_estado)
                
                if nuevo_estado == "Cerrada" and (pd.isna(datos_actuales['Fin']) or datos_actuales['Fin'] == ""):
                    fecha_fin = obtener_fecha_cr()
                    df_ot.at[idx, 'Fin'] = fecha_fin.strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Cálculo de duración
                    ini_dt = datetime.strptime(str(datos_actuales['Inicio']), "%Y-%m-%d %H:%M:%S")
                    duracion = calcular_duracion_laboral(ini_dt, fecha_fin)
                    
                    # Envío de correo
                    correo_dest = df_emp[df_emp['Nombre'] == datos_actuales['Empleado']]['Correo'].values[0]
                    enviar_correo(correo_dest, f"CIERRE de OT #{ot_id}", f"Cerrada con duración: {duracion}")

                guardar_datos(df_ot, "ordenes.csv")
                st.success("Registro actualizado.")
                st.rerun()

    st.write("### Historial General")
    st.dataframe(df_ot, use_container_width=True)
