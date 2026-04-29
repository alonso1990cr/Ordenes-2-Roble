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
        return pd.read_csv(archivo)
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

# 1. GESTIÓN DE EMPLEADOS (EVITAR DUPLICADOS)
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
                # Si el nombre existe, lo sobreescribe. Si no, lo añade.
                df_emp = df_emp[df_emp['Nombre'].str.upper() != nom.upper()]
                nuevo = pd.DataFrame([{"Nombre": nom, "Correo": ema}])
                df_emp = pd.concat([df_emp, nuevo], ignore_index=True)
                guardar_datos(df_emp, "empleados.csv")
                st.success(f"Empleado {nom} registrado correctamente.")
            else:
                st.error("Por favor llene todos los campos.")

    st.subheader("Personal Registrado")
    st.dataframe(df_emp, use_container_width=True)

    if not df_emp.empty:
        emp_borrar = st.selectbox("Seleccione para eliminar:", df_emp['Nombre'])
        if st.button("Eliminar permanentemente"):
            df_emp = df_emp[df_emp['Nombre'] != emp_borrar]
            guardar_datos(df_emp, "empleados.csv")
            st.rerun()

# 2. NUEVA ORDEN DE TRABAJO (SOLO EMPLEADOS EXISTENTES)
elif menu == "Nueva Orden de Trabajo":
    st.header("📝 Apertura de Orden de Trabajo")
    df_emp = cargar_datos("empleados.csv", ["Nombre", "Correo"])
    df_ot = cargar_datos("ordenes.csv", ["OT", "Empleado", "Descripcion", "Inicio", "Tipo", "Estado", "Fin", "Comentarios"])

    if df_emp.empty:
        st.warning("⚠️ No hay empleados registrados. Vaya a la sección 'Gestión de Empleados' primero.")
    else:
        with st.form("form_nueva_ot"):
            # Aquí solo aparecen los operarios registrados anteriormente
            operario = st.selectbox("Operario Asignado", df_emp['Nombre'])
            tipo = st.radio("Tipo de Trabajo", ["Preventivo", "Correctivo"])
            desc = st.text_area("Descripción de la labor a realizar")
            
            if st.form_submit_button("Generar Orden"):
                ahora = obtener_fecha_cr()
                num_ot = ahora.strftime("%Y%m%d-%H%M")
                
                nueva_fila = {
                    "OT": num_ot, "Empleado": operario, "Descripcion": desc,
                    "Inicio": ahora.strftime("%Y-%m-%d %H:%M:%S"),
                    "Tipo": tipo, "Estado": "Abierta", "Fin": "", "Comentarios": ""
                }
                df_ot = pd.concat([df_ot, pd.DataFrame([nueva_fila])], ignore_index=True)
                guardar_datos(df_ot, "ordenes.csv")
                
                correo_dest = df_emp[df_emp['Nombre'] == operario]['Correo'].values[0]
                cuerpo = f"Nueva OT #{num_ot}\nAsignada a: {operario}\nTipo: {tipo}\nDescripción: {desc}"
                enviar_correo(correo_dest, f"Nueva OT #{num_ot}", cuerpo)
                st.success(f"OT #{num_ot} creada y enviada a {operario}")

# 3. CIERRE Y CONSULTA (MODIFICAR Y SOBREESCRIBIR)
elif menu == "Cierre y Consulta de OT":
    st.header("🔍 Seguimiento de Órdenes")
    df_ot = cargar_datos("ordenes.csv", [])
    df_emp = cargar_datos("empleados.csv", [])
    
    if not df_ot.empty:
        filtro_emp = st.selectbox("Filtrar por operario:", ["TODOS"] + list(df_emp['Nombre'].unique()))
        
        # Filtramos los datos según la consulta
        df_mostrar = df_ot if filtro_emp == "TODOS" else df_ot[df_ot['Empleado'] == filtro_emp]
        
        st.write("### Últimos Registros")
        st.dataframe(df_mostrar.tail(10), use_container_width=True)
        
        # Lógica para modificar/cerrar una orden específica
        st.divider()
        st.write("### Modificar / Cerrar una Orden")
        ot_id = st.selectbox("Seleccione el ID de la OT para trabajar:", df_mostrar['OT'].unique())
        
        # Cargamos datos actuales de esa OT
        datos_actuales = df_ot[df_ot['OT'] == ot_id].iloc[0]
        
        with st.expander(f"Editar Orden #{ot_id}"):
            nuevo_comentario = st.text_area("Comentarios de cierre o avance:", value=datos_actuales['Comentarios'] if pd.notna(datos_actuales['Comentarios']) else "")
            nuevo_estado = st.selectbox("Estado actual:", ["Abierta", "Cerrada"], index=0 if datos_actuales['Estado']=="Abierta" else 1)
            
            if st.button("Guardar Cambios y Sobreescribir"):
                fecha_fin = obtener_fecha_cr()
                
                # Actualizamos la fila en el DataFrame original
                df_ot.loc[df_ot['OT'] == ot_id, 'Comentarios'] = nuevo_comentario
                df_ot.loc[df_ot['OT'] == ot_id, 'Estado'] = nuevo_estado
                
                if nuevo_estado == "Cerrada" and pd.isna(datos_actuales['Fin']):
                    df_ot.loc[df_ot['OT'] == ot_id, 'Fin'] = fecha_fin.strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Cálculo de duración para el correo
                    ini_dt = datetime.strptime(datos_actuales['Inicio'], "%Y-%m-%d %H:%M:%S")
                    duracion = calcular_duracion_laboral(ini_dt, fecha_fin)
                    
                    # Envío de correo de cierre
                    correo_dest = df_emp[df_emp['Nombre'] == datos_actuales['Empleado']]['Correo'].values[0]
                    enviar_correo(correo_dest, f"CIERRE de OT #{ot_id}", f"La orden ha sido cerrada.\nDuración laboral: {duracion}\nComentarios: {nuevo_comentario}")

                guardar_datos(df_ot, "ordenes.csv")
                st.success("Registro actualizado y sobreescrito con éxito.")
                st.rerun()

# --- TABLA DE RESUMEN CON EMOJIS ---
st.divider()
st.subheader("📊 Resumen Histórico")
df_final = cargar_datos("ordenes.csv", [])
if not df_final.empty:
    def aplicar_emojis(row):
        if row['Estado'] == "Cerrada":
            ini = datetime.strptime(row['Inicio'], "%Y-%m-%d %H:%M:%S")
            fin = datetime.strptime(row['Fin'], "%Y-%m-%d %H:%M:%S")
            d = calcular_duracion_laboral(ini, fin)
            hrs = d.total_seconds() / 3600
            return f"{d} " + ("⚡" if hrs < 3 else "⏳" if hrs < 8 else "🐢")
        return "Pendiente 🛠️"

    df_final['Tiempo Laborado'] = df_final.apply(aplicar_emojis, axis=1)
    st.table(df_final[['OT', 'Empleado', 'Tipo', 'Estado', 'Tiempo Laborado']])
