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
    tab_reg, tab_mod = st.tabs(["Registrar Nuevo", "Modificar / Eliminar"])
    with tab_reg:
        with st.form("add_emp", clear_on_submit=True):
            n = st.text_input("Nombre Completo")
            c = st.text_input("Correo Electrónico")
            if st.form_submit_button("Registrar"):
                if n and c:
                    df_emp = pd.concat([df_emp, pd.DataFrame([{"Nombre":n,"Correo":c}])], ignore_index=True)
                    guardar_datos(df_emp, "empleados.csv")
                    st.success("Operario registrado.")
                    st.rerun()
    st.table(df_emp)

elif menu == "📝 Nueva OT":
    st.header("📝 Apertura de Orden de Trabajo")
    if df_emp.empty:
        st.warning("Registre operarios primero.")
    else:
        with st.form("f_ot", clear_on_submit=True):
            op = st.selectbox("Operario Asignado", df_emp['Nombre'])
            tp = st.radio("Tipo de Trabajo", ["Preventivo", "Correctivo", "Casos 24h", "Casos ISO"], horizontal=True)
            ds = st.text_area("Descripción del Hallazgo")
            archivo_foto = st.file_uploader("Capturar Foto (Opcional)", type=["jpg", "png", "jpeg"])
            cp = st.text_input("Correo de copia")
            if st.form_submit_button("Generar Orden"):
                if ds and cp:
                    id_ot = f"{len(df_ot) + 1:04d}"
                    nombre_foto = "Sin foto"
                    if archivo_foto:
                        nombre_foto = f"OT_{id_ot}.jpg"
                        with open(os.path.join("fotos", nombre_foto), "wb") as f:
                            f.write(archivo_foto.getbuffer())
                    
                    nueva = {"OT": id_ot, "Empleado": op, "Descripcion": ds, 
                             "Inicio": obtener_fecha_cr().strftime("%Y-%m-%d %H:%M:%S"),
                             "Tipo": tp, "Estado": "Abierta", "Fin": "", "Comentarios": "", 
                             "CorreoCopia": cp, "TiempoAcumulado": "0", "Foto": nombre_foto}
                    df_ot = pd.concat([df_ot, pd.DataFrame([nueva])], ignore_index=True)
                    guardar_datos(df_ot, "ordenes.csv")
                    st.success(f"OT #{id_ot} guardada con éxito."); st.rerun()

elif menu == "🔍 Cierre y Consulta":
    st.markdown(f'<div class="reloj-discreto">Hora CR: {obtener_fecha_cr().strftime("%H:%M:%S")}</div>', unsafe_allow_html=True)
    st.header("🔍 Gestión de Cierre y Consulta")
    tab1, tab2 = st.tabs(["Órdenes Activas", "Historial Completo"])
    
    with tab1:
        pendientes = df_ot[df_ot['Estado'].str.contains("Abierta|En Pausa", case=False, na=False)].copy()
        
        if pendientes.empty:
            st.info("No hay órdenes pendientes de cierre.")
        else:
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
            
            opciones = ["--- Seleccione una orden ---"] + (pendientes['OT'] + " | " + pendientes['Empleado']).tolist()
            sel = st.selectbox("Escoger OT para editar:", opciones)

            if sel != "--- Seleccione una orden ---":
                id_sel = sel.split(" | ")[0]
                idx = df_ot.index[df_ot['OT'] == id_sel].tolist()[0]

                foto_nom = str(df_ot.at[idx, 'Foto'])
                if foto_nom != "Sin foto" and foto_nom != "":
                    ruta = os.path.join("fotos", foto_nom)
                    if os.path.exists(ruta):
                        st.image(ruta, caption=f"Evidencia OT #{id_sel}", width=400)

                with st.form("form_cierre", clear_on_submit=True):
                    st.write(f"### Gestionando OT #{id_sel}")
                    nuevo_est = st.selectbox("Cambiar Estado", ["Abierta", "En Pausa", "Cerrada"], 
                                             index=["Abierta", "En Pausa", "Cerrada"].index(df_ot.at[idx, 'Estado']))
                    coment = st.text_area("Comentarios de avance/finales", value=df_ot.at[idx, 'Comentarios'])
                    
                    if st.form_submit_button("Actualizar y Guardar"):
                        ahora_act = obtener_fecha_cr()
                        
                        # Corrección de la línea con error
                        if df_ot.at[idx, 'Estado'] == "Abierta":
                            inicio_dt = datetime.strptime(df_ot.at[idx, 'Inicio'], "%Y-%m-%d %H:%M:%S")
                            dif_seg = (ahora_act - inicio_dt).total_seconds()
                            df_ot.at[idx, 'TiempoAcumulado'] = str(float(df_ot.at[idx, 'TiempoAcumulado']) + dif_seg)
                        
                        if nuevo_est == "Abierta":
                            df_ot.at[idx, 'Inicio'] = ahora_act.strftime("%Y-%m-%d %H:%M:%S")
                        elif nuevo_est == "Cerrada":
                            df_ot.at[idx, 'Fin'] = ahora_act.strftime("%Y-%m-%d %H:%M:%S")
                        
                        df_ot.at[idx, 'Estado'] = nuevo_est
                        df_ot.at[idx, 'Comentarios'] = coment
                        guardar_datos(df_ot, "ordenes.csv")
                        
                        st.success("✅ Registro actualizado correctamente")
                        st.rerun()

    with tab2:
        st.subheader("📚 Historial Completo")
        st.dataframe(df_ot, use_container_width=True)

elif menu == "📊 Dashboard":
    st.header("📊 Dashboard de Rendimiento")
    if not df_ot.empty:
        df_d = df_ot.copy()
        df_d['Horas'] = pd.to_numeric(df_d['TiempoAcumulado'], errors='coerce').fillna(0) / 3600
        st.plotly_chart(px.bar(df_d, x='OT', y='Horas', color='Tipo', title="Inversión de Horas"), use_container_width=True)
