import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import plotly.express as px
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import io
from streamlit_autorefresh import st_autorefresh

# ======================
# CONFIG
# ======================
st.set_page_config(page_title="Mantenimiento Roble", layout="wide")
UTC_OFFSET = 6

st_autorefresh(interval=1000, key="refresh")

if not os.path.exists("fotos"):
    os.makedirs("fotos")

# ======================
# SMTP
# ======================
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "ugaldeviquezalonso@gmail.com"
SENDER_PASSWORD = "TU_APP_PASSWORD"

# ======================
# FUNCIONES
# ======================
def obtener_fecha_cr():
    return datetime.utcnow() - timedelta(hours=UTC_OFFSET)

def guardar(df, archivo):
    df.to_csv(archivo, index=False)

def cargar(archivo, cols):
    if os.path.exists(archivo):
        return pd.read_csv(archivo, dtype=str).fillna("")
    return pd.DataFrame(columns=cols)

def enviar_correo(destinatarios, asunto, cuerpo):
    try:
        destinos = [d for d in destinatarios if d and "@" in d]

        msg = MIMEMultipart()
        msg["From"] = SENDER_EMAIL
        msg["To"] = ", ".join(destinos)
        msg["Subject"] = asunto
        msg.attach(MIMEText(cuerpo, "plain"))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, destinos, msg.as_string())
        server.quit()
    except Exception as e:
        st.error(e)

def reloj():
    st.markdown(
        f"<div style='text-align:right;color:red;'>CR: {obtener_fecha_cr()}</div>",
        unsafe_allow_html=True
    )

# ======================
# DATA
# ======================
cols_ot = [
    "OT","Empleado","Descripcion","Inicio","Tipo",
    "FrecuenciaPM","OrdenMateriales","Estado","Fin",
    "Comentarios","CorreoCopia","Foto"
]

df_emp = cargar("empleados.csv", ["Nombre", "Correo"])
df_ot = cargar("ordenes.csv", cols_ot)

# ======================
# MENU
# ======================
st.sidebar.title("Panel")
menu = st.sidebar.selectbox("Sección", ["Empleados", "Nueva OT", "OTs", "Dashboard"])

# =========================================================
# EMPLEADOS
# =========================================================
if menu == "Empleados":
    st.title("Empleados")
    reloj()

    with st.form("emp"):
        n = st.text_input("Nombre")
        c = st.text_input("Correo")

        if st.form_submit_button("Guardar"):
            df_emp = pd.concat([df_emp, pd.DataFrame([{"Nombre": n, "Correo": c}])], ignore_index=True)
            guardar(df_emp, "empleados.csv")
            st.rerun()

    st.dataframe(df_emp)

# =========================================================
# NUEVA OT (CORREGIDO COMPLETO)
# =========================================================
elif menu == "Nueva OT":
    st.title("Nueva OT")
    reloj()

    if df_emp.empty:
        st.warning("Registre empleados primero")
    else:

        with st.form("ot_form"):

            op = st.selectbox("Operario", df_emp["Nombre"])

            tp = st.radio(
                "Tipo",
                ["Preventivo", "Correctivo", "SNC alta", "SNC media", "SNC baja"],
                horizontal=True
            )

            # -------------------------
            # FRECUENCIA SOLO PREVENTIVO
            # -------------------------
            frecuencia_pm = ""

            if tp == "Preventivo":
                frecuencia_pm = st.selectbox(
                    "Frecuencia Preventiva",
                    ["S - Semanal", "Q - Quincenal", "M - Mensual", "T - Trimestral", "S6 - Semestral", "A - Anual"]
                )

            # -------------------------
            # MATERIALES DINÁMICO
            # -------------------------
            material = st.radio(
                "Materiales",
                ["No aplica material", "Ligar a Orden de Materiales"],
                horizontal=True
            )

            orden_materiales = "No aplica"

            if material == "Ligar a Orden de Materiales":
                orden_materiales = st.text_input("Digite Orden de Materiales")

            desc = st.text_area("Descripción")
            foto = st.file_uploader("Foto", type=["jpg","png","jpeg"])
            cp = st.text_input("Correo copia")

            generar = st.form_submit_button("Generar OT")

        # =========================
        # PROCESO (FUERA DEL FORM)
        # =========================
        if generar:

            id_ot = f"{len(df_ot)+1:04d}"
            correo_op = df_emp[df_emp["Nombre"] == op]["Correo"].values[0]

            nombre_foto = "Sin foto"
            if foto:
                nombre_foto = f"OT_{id_ot}.jpg"
                with open(os.path.join("fotos", nombre_foto), "wb") as f:
                    f.write(foto.getbuffer())

            nueva = {
                "OT": id_ot,
                "Empleado": op,
                "Descripcion": desc,
                "Inicio": obtener_fecha_cr().strftime("%Y-%m-%d %H:%M:%S"),
                "Tipo": tp,
                "FrecuenciaPM": frecuencia_pm,
                "OrdenMateriales": orden_materiales,
                "Estado": "Abierta",
                "Fin": "",
                "Comentarios": "",
                "CorreoCopia": cp,
                "Foto": nombre_foto
            }

            df_ot = pd.concat([df_ot, pd.DataFrame([nueva])], ignore_index=True)
            guardar(df_ot, "ordenes.csv")

            correos = ["sa.alterna@gmail.com", correo_op, cp]

            cuerpo = f"""
OT #{id_ot}
Operario: {op}
Tipo: {tp}
Frecuencia: {frecuencia_pm}
Materiales: {orden_materiales}
Descripción: {desc}
"""

            enviar_correo(correos, f"OT #{id_ot}", cuerpo)

            st.success("OT creada")
            st.rerun()

# =========================================================
# OT LISTADO
# =========================================================
elif menu == "OTs":
    st.title("Órdenes")
    reloj()
    st.dataframe(df_ot)

# =========================================================
# DASHBOARD
# =========================================================
elif menu == "Dashboard":
    st.title("Dashboard")
    reloj()

    if not df_ot.empty:
        st.metric("Total OT", len(df_ot))
        st.plotly_chart(px.pie(df_ot, names="Estado", title="Estados"))
