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
st.set_page_config(page_title="Gestión OT - Roble", layout="wide")
UTC_OFFSET = 6 # Ajuste para Costa Rica

# Refresco automático cada 1 segundo para actualizar el reloj
st_autorefresh(interval=1000, key="daterefresh")

# Configuración de carpetas para fotos
if not os.path.exists("fotos"):
    os.makedirs("fotos")

# --- FUNCIONES DE APOYO ---
def obtener_fecha_cr():
    """Retorna la fecha y hora actual de Costa Rica."""
    return datetime.utcnow() - timedelta(hours=UTC_OFFSET)

def mostrar_reloj_rojo():
    """Muestra la hora en rojo y formato grande en cada sección."""
    hora_actual = obtener_fecha_cr().strftime("%d/%m/%Y %H:%M:%S")
    st.markdown(
        f"""
        <div style="text-align: right; padding-bottom: 20px;">
            <span style="color: #ff4b4b; font-size: 26px; font-weight: bold; font-family: monospace; border: 2px solid #ff4b4b; padding: 5px 15px; border-radius: 10px;">
                🕒 {hora_actual}
            </span>
        </div>
        """, 
        unsafe_allow_html=True
    )

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
st.sidebar.title("🛠️ Panel de Control")
menu = st.sidebar.selectbox("Seleccione sección:", ["👥 Empleados", "📝 Nueva OT", "🔍 Cierre y Consulta", "📊 Dashboard"])

# --- SECCIONES ---

if menu == "👥 Empleados":
    st.header("👥 Gestión de Personal")
    mostrar_reloj_rojo() # Hora en rojo en esta sección
    
    t1, t2, t3 = st.tabs(["➕ Registrar", "✏️ Modificar", "🗑️ Eliminar"])
    with t1:
        with st.form("add_emp", clear_on_submit=True):
            n, c = st.text_input("Nombre Completo"), st.text_input("Correo Electrónico")
            if st.form_submit_button("Registrar"):
                if n and c:
                    df_emp = pd.concat([df_emp, pd.DataFrame([{"Nombre":n,"Correo":c}])], ignore_index=True)
                    guardar_datos(df_emp, "empleados.csv")
                    st.success("Empleado registrado correctamente"); st.rerun()
    # (Opciones de modificar y eliminar omitidas por brevedad, mantienen la lógica previa)
    st.table(df_emp)

elif menu == "📝 Nueva OT":
    st.header("📝 Apertura de Orden de Trabajo")
    mostrar_reloj_rojo() # Hora en rojo en esta sección
    
    if df_emp.empty: 
        st.warning("Debe registrar operarios antes de crear una OT.")
    else:
        with st.form("f_ot", clear_on_submit=True):
            op = st.selectbox("Operario Asignado", df_emp['Nombre'])
            tp = st.radio("Tipo de Trabajo", ["Preventivo", "Correctivo", "Casos 24h", "Casos ISO"], horizontal=True)
            ds = st.text_area("Descripción del hallazgo")
            foto = st.file_uploader("Evidencia Fotográfica", type=["jpg", "png", "jpeg"])
            cp = st.text_input("Enviar copia a (opcional)")
            
            if st.form_submit_button("Generar Orden"):
                id_ot = f"{len(df_ot) + 1:04d}"
                nom_foto = f"OT_{id_ot}.jpg" if foto else "Sin foto"
                if foto:
                    with open(os.path.join("fotos", nom_foto), "wb") as f: f.write(foto.getbuffer())
                
                nueva = {
                    "OT":id_ot, "Empleado":op, "Descripcion":ds, 
                    "Inicio":obtener_fecha_cr().strftime("%Y-%m-%d %H:%M:%S"),
                    "Tipo":tp, "Estado":"Abierta", "Fin":"", "Comentarios":"", 
                    "CorreoCopia":cp, "TiempoAcumulado":"0", "Foto":nom_foto
                }
                df_ot = pd.concat([df_ot, pd.DataFrame([nueva])], ignore_index=True)
                guardar_datos(df_ot, "ordenes.csv")
                st.success(f"Orden #{id_ot} creada con éxito.")
                st.rerun()

elif menu == "🔍 Cierre y Consulta":
    st.header("🔍 Gestión de Cierre y Consulta")
    mostrar_reloj_rojo() # Hora en rojo en esta sección
    
    tab1, tab2 = st.tabs(["Órdenes Activas", "Historial Completo"])
    with tab1:
        pendientes = df_ot[df_ot['Estado'].isin(["Abierta", "En Pausa"])].copy()
        if not pendientes.empty:
            st.dataframe(pendientes[["OT", "Estado", "Empleado", "Tipo", "Descripcion"]].style.map(estilo_estados, subset=['Estado']), use_container_width=True, hide_index=True)
            
            sel = st.selectbox("Seleccionar OT para gestionar:", ["---"] + (pendientes['OT'] + " | " + pendientes['Empleado']).tolist())
            if sel != "---":
                id_sel = sel.split(" | ")[0]
                idx = df_ot.index[df_ot['OT'] == id_sel].tolist()[0]
                
                # Mostrar foto si existe
                f_nom = df_ot.at[idx, 'Foto']
                if f_nom != "Sin foto" and os.path.exists(os.path.join("fotos", f_nom)):
                    st.image(Image.open(os.path.join("fotos", f_nom)), width=400)

                with st.form("cierre_form"):
                    nuevo_est = st.selectbox("Cambiar Estado", ["Abierta", "En Pausa", "Cerrada"], index=["Abierta", "En Pausa", "Cerrada"].index(df_ot.at[idx, 'Estado']))
                    nuevo_com = st.text_area("Comentarios de avance/cierre", value=df_ot.at[idx, 'Comentarios'])
                    
                    if st.form_submit_button("Actualizar Registro"):
                        df_ot.at[idx, 'Estado'], df_ot.at[idx, 'Comentarios'] = nuevo_est, nuevo_com
                        if nuevo_est == "Cerrada":
                            df_ot.at[idx, 'Fin'] = obtener_fecha_cr().strftime("%Y-%m-%d %H:%M:%S")
                        guardar_datos(df_ot, "ordenes.csv")
                        st.success("Registro actualizado."); st.rerun()
    with tab2:
        st.dataframe(df_ot.style.map(estilo_estados, subset=['Estado']), use_container_width=True)

elif menu == "📊 Dashboard":
    st.header("📊 Dashboard de Rendimiento")
    mostrar_reloj_rojo() # Hora en rojo en esta sección
    
    if not df_ot.empty:
        df_f = df_ot.copy()
        df_f['Horas'] = pd.to_numeric(df_f['TiempoAcumulado'], errors='coerce').fillna(0) / 3600
        st.plotly_chart(px.bar(df_f, x='OT', y='Horas', color='Tipo', title="Horas por Tipo de Mantenimiento"), use_container_width=True)
    else:
        st.info("No hay datos suficientes para mostrar el dashboard.")
