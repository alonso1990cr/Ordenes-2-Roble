import streamlit as st
import pandas as pd
from datetime import datetime
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- CONFIGURACIÓN DE CORREO ---
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "tu-correo@gmail.com"
SENDER_PASSWORD = "abcd efgh ijkl mnop"  # contraseña de aplicación

# --- FUNCIONES AUXILIARES ---
def obtener_fecha_cr():
    return datetime.now()

def guardar_datos(df, archivo):
    df.to_csv(archivo, index=False)

def cargar_datos(archivo, columnas):
    if os.path.exists(archivo):
        return pd.read_csv(archivo)
    else:
        return pd.DataFrame(columns=columnas)

# --- FUNCIÓN DE ENVÍO DE CORREO ---
def enviar_notificacion(destinatarios, asunto, cuerpo):
    try:
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
        st.error(f"Error técnico de envío: {e}")
        return False

# --- CARGAR DATOS ---
df_ot = cargar_datos("ordenes.csv", ["OT","Empleado","Descripcion","Inicio","Tipo","Estado","Fin","Comentarios","CorreoCopia","TiempoAcumulado","Foto"])
df_emp = cargar_datos("empleados.csv", ["Nombre","Correo"])

st.title("Sistema de Órdenes de Trabajo")

# --- FORMULARIO ---
with st.form("form_orden"):

    st.subheader("Nueva Orden de Trabajo")

    # Inputs
    op = st.selectbox("Operario", df_emp["Nombre"] if not df_emp.empty else [])
    ds = st.text_area("Descripción")
    tp = st.selectbox("Tipo", ["Correctivo", "Preventivo", "Emergencia"])
    cp = st.text_input("Correo adicional (copia)")

    submitted = st.form_submit_button("Generar Orden")

    if submitted:

        if not op or not ds:
            st.warning("Debe completar los campos obligatorios.")
        else:
            id_ot = f"{len(df_ot) + 1:04d}"
            
            datos_op = df_emp[df_emp['Nombre'] == op]
            correo_operario = datos_op['Correo'].values[0] if not datos_op.empty else ""
            
            correo_extra = cp.strip()

            nueva = {
                "OT": id_ot,
                "Empleado": op,
                "Descripcion": ds,
                "Inicio": obtener_fecha_cr().strftime("%Y-%m-%d %H:%M:%S"),
                "Tipo": tp,
                "Estado": "Abierta",
                "Fin": "",
                "Comentarios": "",
                "CorreoCopia": correo_extra,
                "TiempoAcumulado": "0",
                "Foto": "..."
            }

            df_ot = pd.concat([df_ot, pd.DataFrame([nueva])], ignore_index=True)
            guardar_datos(df_ot, "ordenes.csv")

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

# --- MOSTRAR DATOS ---
st.subheader("Órdenes registradas")
st.dataframe(df_ot)
