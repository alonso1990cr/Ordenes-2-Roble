import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import plotly.express as px
import io
from PIL import Image

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Gestión OT - Roble", layout="wide")
UTC_OFFSET = 6 

if not os.path.exists("fotos"):
    os.makedirs("fotos")

# --- ESTILO CSS ---
st.markdown("""
    <style>
    input, textarea { caret-color: #ff0000 !important; }
    .stTextInput > div > div > input, .stTextArea > div > div > textarea {
        background-color: #f9f9f9 !important;
        color: #000000 !important;
    }
    .reloj-discreto {
        font-size: 16px; font-weight: bold; color: #ff0000;
        text-align: right; margin-bottom: 5px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- FUNCIONES TÉCNICAS ---
def obtener_fecha_cr():
    return datetime.utcnow() - timedelta(hours=UTC_OFFSET)

def cargar_datos(archivo, columnas):
    if os.path.exists(archivo):
        try:
            df = pd.read_csv(archivo, dtype=str).fillna("")
            return df
        except:
            return pd.DataFrame(columns=columnas)
    return pd.DataFrame(columns=columnas)

def guardar_datos(df, archivo):
    df.to_csv(archivo, index=False)

# --- CARGA DE DATOS ---
cols_ot = ["OT", "Empleado", "Descripcion", "Inicio", "Tipo", "Estado", "Fin", "Comentarios", "CorreoCopia", "TiempoAcumulado", "Foto"]
df_emp = cargar_datos("empleados.csv", ["Nombre", "Correo"])
df_ot = cargar_datos("ordenes.csv", cols_ot)

# --- MENÚ LATERAL ---
st.sidebar.title("🛠️ Navegación Principal")
menu = st.sidebar.selectbox(
    "Seleccione una sección:", 
    ["👥 Empleados", "📝 Nueva OT", "🔍 Cierre y Consulta", "📊 Dashboard"]
)
st.sidebar.divider()

# --- LÓGICA DE SECCIONES ---

if menu == "👥 Empleados":
    st.header("👥 Gestión de Operarios")
    # ... (Código de empleados)
    st.table(df_emp)

elif menu == "📝 Nueva OT":
    st.header("📝 Apertura de Orden de Trabajo")
    # ... (Código de Nueva OT)

elif menu == "🔍 Cierre y Consulta":
    st.markdown(f'<div class="reloj-discreto">Hora CR: {obtener_fecha_cr().strftime("%H:%M:%S")}</div>', unsafe_allow_html=True)
    st.header("🔍 Gestión de Cierre y Consulta")
    tab1, tab2 = st.tabs(["Órdenes Activas", "Historial Completo"])
    
    with tab1:
        pendientes = df_ot[df_ot['Estado'].str.contains("Abierta|En Pausa", case=False, na=False)].copy()
        
        if pendientes.empty:
            st.info("No hay órdenes pendientes de cierre.")
        else:
            # Resumen con Duración y Comentarios
            ahora = obtener_fecha_cr()
            def calcular_horas(row):
                try:
                    inicio = datetime.strptime(row['Inicio'], "%Y-%m-%d %H:%M:%S")
                    acumulado = float(row['TiempoAcumulado'])
                    if row['Estado'] == "Abierta":
                        segundos = (ahora - inicio).total_seconds()
                        return round((acumulado + segundos) / 3600, 2)
                    return round(acumulado / 3600, 2)
                except: return 0.0

            pendientes['Duración (Hrs)'] = pendientes.apply(calcular_horas, axis=1)
            st.subheader("📋 Resumen de Órdenes en Proceso")
            st.dataframe(
                pendientes[["OT", "Estado", "Empleado", "Tipo", "Inicio", "Duración (Hrs)", "Comentarios", "Descripcion"]], 
                use_container_width=True
            )
            
            st.divider()
            
            # Selector de Orden
            opciones = ["--- Seleccione una orden ---"] + (pendientes['OT'] + " | " + pendientes['Empleado']).tolist()
            sel = st.selectbox("Escoger OT para editar:", opciones)

            if sel != "--- Seleccione una orden ---":
                id_sel = sel.split(" | ")[0]
                idx = df_ot.index[df_ot['OT'] == id_sel].tolist()[0]

                with st.form("form_cierre", clear_on_submit=True):
                    st.write(f"### Gestionando OT #{id_sel}")
                    nuevo_est = st.selectbox("Estado", ["Abierta", "En Pausa", "Cerrada"], 
                                             index=["Abierta", "En Pausa", "Cerrada"].index(df_ot.at[idx, 'Estado']))
                    coment = st.text_area("Comentarios de avance/finales", value=df_ot.at[idx, 'Comentarios'])
                    
                    if st.form_submit_button("Actualizar y Guardar"):
                        ahora_cierre = obtener_fecha_cr()
                        
                        # Guardar tiempo acumulado si estaba abierta
                        if df_ot.at[idx, 'Estado'] == "Abierta":
                            inicio_dt = datetime.strptime(df_ot.at[idx, 'Inicio'], "%Y-%m-%d %H:%M:%S")
                            df_ot.at[idx, 'TiempoAcumulado'] = str(float(df_ot.at[idx, 'TiempoAcumulado']) + (ahora_cierre - inicio_dt).total_seconds())
                        
                        if nuevo_est == "Abierta": df_ot.at[idx, 'Inicio'] = ahora_cierre.strftime("%Y-%m-%d %H:%M:%S")
                        elif nuevo_est == "Cerrada": df_ot.at[idx, 'Fin'] = ahora_cierre.strftime("%Y-%m-%d %H:%M:%S")
                        
                        df_ot.at[idx, 'Estado'] = nuevo_est
                        df_ot.at[idx, 'Comentarios'] = coment
                        guardar_datos(df_ot, "ordenes.csv")
                        
                        st.success("✅ Registro actualizado correctamente")
                        st.rerun() # Esto limpia el selector y refresca la tabla

    with tab2:
        st.dataframe(df_ot, use_container_width=True)

elif menu == "📊 Dashboard":
    st.header("📊 Dashboard")
    # ... (Tu código de Dashboard filtrado)
