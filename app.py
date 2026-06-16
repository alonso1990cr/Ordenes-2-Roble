import streamlit as st

# =========================
# Simulación de base de datos en memoria
# =========================
if "ordenes" not in st.session_state:
    st.session_state.ordenes = []

# =========================
# Función para generar orden consecutiva
# =========================
def generar_orden():
    if len(st.session_state.ordenes) == 0:
        return 1
    return max(o["numero_orden"] for o in st.session_state.ordenes) + 1


# =========================
# UI PRINCIPAL
# =========================
st.title("Sistema de Órdenes de Trabajo")

with st.form("form_orden"):

    # -------------------------
    # Tipo de orden
    # -------------------------
    tipo = st.radio("Tipo de orden", ["Correctivo", "Preventivo"])

    # -------------------------
    # Frecuencia preventiva (solo si aplica)
    # -------------------------
    frecuencia = None
    if tipo == "Preventivo":
        frecuencia = st.selectbox(
            "Frecuencia preventiva",
            ["Mensual", "Trimestral", "Semestral", "Anual"]
        )

    # -------------------------
    # Ligar a orden de materiales
    # -------------------------
    ligar_materiales = st.checkbox("Ligar a orden de materiales")

    codigo_materiales = None
    if ligar_materiales:
        codigo_materiales = st.text_input("Código de orden de materiales")

    # -------------------------
    # Otros datos
    # -------------------------
    descripcion = st.text_area("Descripción del trabajo")

    # -------------------------
    # Botón submit
    # -------------------------
    submit = st.form_submit_button("Generar Orden")

# =========================
# PROCESO DE GUARDADO
# =========================
if submit:
    numero_orden = generar_orden()

    nueva_orden = {
        "numero_orden": numero_orden,
        "tipo": tipo,
        "frecuencia": frecuencia,
        "descripcion": descripcion,
        "orden_materiales": codigo_materiales
    }

    st.session_state.ordenes.append(nueva_orden)

    st.success(f"Orden #{numero_orden} generada correctamente")

# =========================
# MOSTRAR ÓRDENES
# =========================
st.subheader("Órdenes generadas")

for o in st.session_state.ordenes:
    st.write(o)
