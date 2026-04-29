import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from streamlit_autorefresh import st_autorefresh

# --- CONFIGURACIÓN DE CORREO ---
# REEMPLAZA ESTOS DATOS CON TU CONTRASEÑA DE 16 LETRAS
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "tu-correo@gmail.com" 
SENDER_PASSWORD = "abcd efgh ijkl mnop" # <--- Las 16 letras de Google

# --- FUNCIÓN DE ENVÍO ---
def enviar_notificacion(destinatarios, asunto, cuerpo):
    try:
        # Limpiar y filtrar la lista de correos para evitar errores si alguno viene vacío
        destinos_limpios = [str(d).strip() for d in destinatarios if d and isinstance(d, str) and "@" in d]
        
        if not destinos_limpios:
            return False

        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = ", ".join(destinos_limpios)
        msg['Subject'] = asunto
        msg.attach(MIMEText(cuerpo, 'plain'))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, destinos_limpios, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        # Esto te mostrará en pantalla por qué falló exactamente (ej. Clave incorrecta)
        st.error(f"Error técnico de envío: {e}")
        return False

# --- DENTRO DE LA SECCIÓN 'NUEVA OT' ---
# Busca esta parte en tu código y reemplázala:

if st.form_submit_button("Generar Orden"):
    id_ot = f"{len(df_ot) + 1:04d}"
    
    # 1. Obtener correo del operario desde el DataFrame de empleados
    datos_op = df_emp[df_emp['Nombre'] == op]
    correo_operario = datos_op['Correo'].values[0] if not datos_op.empty else ""
    
    # 2. Correo de copia (el que escribes en el campo 'cp')
    correo_extra = cp.strip()
    
    # 3. Guardar en CSV
    nueva = {"OT":id_ot, "Empleado":op, "Descripcion":ds, "Inicio":obtener_fecha_cr().strftime("%Y-%m-%d %H:%M:%S"),
             "Tipo":tp, "Estado":"Abierta", "Fin":"", "Comentarios":"", "CorreoCopia":correo_extra, "TiempoAcumulado":"0", "Foto": "..."}
    
    df_ot = pd.concat([df_ot, pd.DataFrame([nueva])], ignore_index=True)
    guardar_datos(df_ot, "ordenes.csv")
    
    # 4. ENVÍO TRIPLE
    destinatarios = ["sa.alterna@gmail.com", correo_operario, correo_extra]
    asunto = f"Apertura de OT #{id_ot} - {op}"
    cuerpo = f"""
    Se ha generado una nueva Orden de Trabajo:
    
    OT #: {id_ot}
    Operario: {op}
    Tipo: {tp}
    Descripción: {ds}
    Fecha: {obtener_fecha_cr().strftime('%d/%m/%Y %H:%M:%S')}
    """
    
    exito = enviar_notificacion(destinatarios, asunto, cuerpo)
    
    if exito:
        st.success(f"OT #{id_ot} guardada y correos enviados correctamente.")
    else:
        st.warning(f"OT #{id_ot} guardada, pero hubo un problema al enviar los correos.")
    
    st.rerun()
