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
UTC_OFFSET = 6  # Costa Rica

st_autorefresh(interval=1000, key="daterefresh")

if not os.path.exists("fotos"):
    os.makedirs("fotos")

# --- CONFIGURACIÓN SMTP ---
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "ugaldeviquezalonso@gmail.com"
SENDER_PASSWORD = "krqi xpnr wxua zwfz"

# --- FUNCIONES ---
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
    try:
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
        worksheet = writer.sheets['Historial_OT']
        worksheet.protect('Roble2026', {'autofilter': True})
    return output.getvalue()

# --- DATOS ---
cols_ot = [
    "OT", "Empleado", "Descripcion", "Inicio", "Tipo",
    "FrecuenciaPM", "OrdenMateriales", "Estado",
    "Fin", "Comentarios", "CorreoCopia",
    "TiempoAcumulado", "Foto"
]

df_emp = cargar_datos("empleados.csv", ["Nombre", "Correo"])
df_ot = cargar_datos("ordenes.csv", cols_ot)

# --- MENU ---
st.sidebar.title("🛠️ Panel de Control")
menu = st.sidebar.selectbox("Seleccione sección:", [
    "👥 Empleados",
    "📝 Nueva OT",
    "🔍 Cierre y Consulta",
    "📊 Dashboard"
])

# =========================================================
# EMPLEADOS
# =========================================================
if menu == "👥 Empleados":
    st.header("👥 Gestión de Personal")
    mostrar_reloj_discreto()

    t1, t2, t3 = st.tabs(["➕ Registrar", "✏️ Modificar", "🗑️ Eliminar"])

    with t1:
        with st.form("add_emp", clear_on_submit=True):
            n = st.text_input("Nombre Completo")
            c = st.text_input("Correo Electrónico")
            if st.form_submit_button("Registrar"):
                df_emp = pd.concat([df_emp, pd.DataFrame([{"Nombre": n, "Correo": c}])], ignore_index=True)
                guardar_datos(df_emp, "empleados.csv")
                st.success("Empleado registrado")
                st.rerun()

    with t2:
        if not df_emp.empty:
            sel = st.selectbox("Editar:", df_emp["Nombre"])
            idx = df_emp.index[df_emp["Nombre"] == sel][0]

            with st.form("edit_emp"):
                new_n = st.text_input("Nombre", df_emp.at[idx, "Nombre"])
                new_c = st.text_input("Correo", df_emp.at[idx, "Correo"])
                if st.form_submit_button("Actualizar"):
                    df_emp.at[idx, "Nombre"] = new_n
                    df_emp.at[idx, "Correo"] = new_c
                    guardar_datos(df_emp, "empleados.csv")
                    st.success("Actualizado")
                    st.rerun()

    with t3:
        if not df_emp.empty:
            borrar = st.selectbox("Eliminar:", df_emp["Nombre"])
            if st.button("Eliminar") and st.checkbox("Confirmar"):
                df_emp = df_emp[df_emp["Nombre"] != borrar]
                guardar_datos(df_emp, "empleados.csv")
                st.rerun()

    st.table(df_emp)

# =========================================================
# NUEVA OT
# =========================================================
elif menu == "📝 Nueva OT":
    st.header("📝 Apertura de Orden de Trabajo")
    mostrar_reloj_discreto()

    if df_emp.empty:
        st.warning("Registre empleados primero.")
    else:
        with st.form("f_ot", clear_on_submit=True):

            op = st.selectbox("Operario Asignado", df_emp["Nombre"])

            tp = st.radio(
                "Tipo",
                ["Preventivo", "Correctivo", "SNC alta", "SNC media", "SNC baja"],
                horizontal=True
            )

            frecuencia_pm = ""
            if tp == "Preventivo":
                frecuencia_pm = st.selectbox(
                    "Frecuencia Preventiva",
                    ["S - Semanal", "Q - Quincenal", "M - Mensual", "T - Trimestral", "S6 - Semestral", "A - Anual"]
                )

            material = st.radio(
                "Materiales",
                ["No aplica material", "Ligar a Orden de Materiales"],
                horizontal=True
            )

            orden_materiales = "No aplica"
            if material == "Ligar a Orden de Materiales":
                orden_materiales = st.text_input("Número de Orden de Materiales")

            ds = st.text_area("Descripción")
            foto = st.file_uploader("Foto", type=["jpg", "png", "jpeg"])
            cp = st.text_input("Correo copia")

            if st.form_submit_button("Generar Orden"):

                id_ot = f"{len(df_ot) + 1:04d}"

                correo_op = df_emp[df_emp["Nombre"] == op]["Correo"].values[0]

                nom_foto = f"OT_{id_ot}.jpg" if foto else "Sin foto"
                if foto:
                    with open(os.path.join("fotos", nom_foto), "wb") as f:
                        f.write(foto.getbuffer())

                nueva = {
                    "OT": id_ot,
                    "Empleado": op,
                    "Descripcion": ds,
                    "Inicio": obtener_fecha_cr().strftime("%Y-%m-%d %H:%M:%S"),
                    "Tipo": tp,
                    "FrecuenciaPM": frecuencia_pm,
                    "OrdenMateriales": orden_materiales,
                    "Estado": "Abierta",
                    "Fin": "",
                    "Comentarios": "",
                    "CorreoCopia": cp,
                    "TiempoAcumulado": "0",
                    "Foto": nom_foto
                }

                df_ot = pd.concat([df_ot, pd.DataFrame([nueva])], ignore_index=True)
                guardar_datos(df_ot, "ordenes.csv")

                lista = ["sa.alterna@gmail.com", correo_op, cp]
                cuerpo = f"""OT #{id_ot}
Operario: {op}
Tipo: {tp}
Frecuencia: {frecuencia_pm}
Materiales: {orden_materiales}
Descripción: {ds}"""

                enviar_notificacion(lista, f"Apertura OT #{id_ot}", cuerpo)

                st.success(f"OT #{id_ot} creada")
                st.rerun()

# =========================================================
# CIERRE Y CONSULTA
# =========================================================
elif menu == "🔍 Cierre y Consulta":
    st.header("🔍 Gestión de OT")
    mostrar_reloj_discreto()

    tab1, tab2 = st.tabs(["Activas", "Historial"])

    with tab1:
        pendientes = df_ot[df_ot["Estado"].isin(["Abierta", "En Pausa"])]

        if not pendientes.empty:
            sel = st.selectbox(
                "OT",
                ["---"] + (pendientes["OT"] + " | " + pendientes["Empleado"]).tolist()
            )

            if sel != "---":
                idx = df_ot.index[df_ot["OT"] == sel.split(" | ")[0]][0]

                with st.form("cierre"):
                    estado = st.selectbox(
                        "Estado",
                        ["Abierta", "En Pausa", "Cerrada"],
                        index=["Abierta", "En Pausa", "Cerrada"].index(df_ot.at[idx, "Estado"])
                    )

                    com = st.text_area("Comentarios", df_ot.at[idx, "Comentarios"])

                    if st.form_submit_button("Actualizar"):
                        df_ot.at[idx, "Estado"] = estado
                        df_ot.at[idx, "Comentarios"] = com

                        if estado == "Cerrada":
                            df_ot.at[idx, "Fin"] = obtener_fecha_cr().strftime("%Y-%m-%d %H:%M:%S")

                        guardar_datos(df_ot, "ordenes.csv")
                        st.rerun()

    with tab2:
        st.dataframe(df_ot, use_container_width=True)

        if not df_ot.empty:
            st.download_button(
                "Descargar Excel",
                generar_excel_protegido(df_ot),
                "OT.xlsx"
            )

# =========================================================
# DASHBOARD
# =========================================================
elif menu == "📊 Dashboard":
    st.header("📊 Dashboard")
    mostrar_reloj_discreto()

    if not df_ot.empty:
        st.metric("Total OT", len(df_ot))
        st.plotly_chart(px.pie(df_ot, names="Estado", title="Estados"))
