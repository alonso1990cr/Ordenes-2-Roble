import streamlit as st
import sqlite3
from datetime import datetime
import pandas as pd
import plotly.express as px

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="Mantenimiento Pro", layout="wide")
DB = "mantenimiento.db"

# =========================
# DB
# =========================
def conn():
    return sqlite3.connect(DB, check_same_thread=False)

def init():
    c = conn().cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS empleados (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT,
        correo TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS ordenes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        empleado TEXT,
        tipo TEXT,
        frecuencia TEXT,
        materiales TEXT,
        descripcion TEXT,
        estado TEXT,
        fecha TEXT,
        comentarios TEXT
    )
    """)

    conn().commit()
    conn().close()

init()

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def q(sql, params=()):
    c = conn()
    cur = c.cursor()
    cur.execute(sql, params)
    c.commit()
    c.close()

def df(sql):
    return pd.read_sql_query(sql, conn())

# =========================
# MENU ORIGINAL (CLARO)
# =========================
menu = st.sidebar.radio(
    "Menú",
    ["Empleados", "Nueva OT", "Listado OT", "Dashboard"]
)

# =========================
# EMPLEADOS
# =========================
if menu == "Empleados":
    st.title("Empleados")

    with st.form("emp"):
        n = st.text_input("Nombre")
        c = st.text_input("Correo")

        if st.form_submit_button("Guardar"):
            q("INSERT INTO empleados (nombre, correo) VALUES (?,?)", (n, c))
            st.success("Guardado")
            st.rerun()

    st.dataframe(df("SELECT * FROM empleados"))

# =========================
# NUEVA OT (CON TUS REGLAS)
# =========================
elif menu == "Nueva OT":
    st.title("Nueva OT")

    empleados = df("SELECT nombre FROM empleados")

    if empleados.empty:
        st.warning("No hay empleados")
    else:

        with st.form("ot"):

            emp = st.selectbox("Operario", empleados["nombre"])

            tipo = st.radio(
                "Tipo",
                ["Preventivo", "Correctivo", "SNC Alta", "SNC Media", "SNC Baja"]
            )

            # ✔ FRECUENCIA SOLO PREVENTIVO
            frecuencia = ""
            if tipo == "Preventivo":
                frecuencia = st.selectbox(
                    "Frecuencia",
                    ["Semanal", "Quincenal", "Mensual", "Trimestral", "Semestral", "Anual"]
                )

            # ✔ MATERIAL SOLO SI ACTIVO
            usar_mat = st.checkbox("Ligar a orden de materiales")

            materiales = ""
            if usar_mat:
                materiales = st.text_input("Código orden de materiales")

            descripcion = st.text_area("Descripción")

            if st.form_submit_button("Crear OT"):

                q("""
                INSERT INTO ordenes (
                    empleado, tipo, frecuencia, materiales,
                    descripcion, estado, fecha, comentarios
                )
                VALUES (?,?,?,?,?,?,?,?)
                """, (
                    emp, tipo, frecuencia, materiales,
                    descripcion, "Abierta", now(), ""
                ))

                st.success("OT creada")
                st.rerun()

# =========================
# LISTADO + EDITAR + ELIMINAR
# =========================
elif menu == "Listado OT":
    st.title("Órdenes de Trabajo")

    data = df("SELECT * FROM ordenes ORDER BY id DESC")
    st.dataframe(data, use_container_width=True)

    st.divider()

    st.subheader("Editar / Eliminar OT")

    ot = st.number_input("ID OT", min_value=1, step=1)

    estado = st.selectbox("Estado", ["Abierta", "En proceso", "Cerrada"])
    comentario = st.text_area("Comentario")

    col1, col2 = st.columns(2)

    if col1.button("Actualizar"):
        q("UPDATE ordenes SET estado=?, comentarios=? WHERE id=?",
          (estado, comentario, ot))
        st.success("Actualizado")
        st.rerun()

    if col2.button("Eliminar"):
        q("DELETE FROM ordenes WHERE id=?", (ot,))
        st.warning("Eliminado")
        st.rerun()

# =========================
# DASHBOARD
# =========================
elif menu == "Dashboard":
    st.title("Dashboard")

    data = df("SELECT * FROM ordenes")

    if not data.empty:
        st.metric("Total OT", len(data))

        st.plotly_chart(px.pie(data, names="estado", title="Estados"))
        st.plotly_chart(px.histogram(data, x="tipo", title="Tipos de OT"))
