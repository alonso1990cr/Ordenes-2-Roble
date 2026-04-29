import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import plotly.express as px
import io

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Gestión OT - Roble", layout="wide")
UTC_OFFSET = 6 

if not os.path.exists("fotos"):
    os.makedirs("fotos")

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
    st.header("🔍 Gestión de Cierre y Consulta")
    tab1, tab2 = st.tabs(["Órdenes Activas", "Historial Completo"])
    
    with tab1:
        pendientes = df_ot[df_ot['Estado'].str.contains("Abierta|En Pausa", case=False, na=False)].copy()
        
        if pendientes.empty:
            st.info("No hay órdenes pendientes de cierre.")
        else:
            ahora = obtener_fecha_cr()
            
            def formatear_duracion(row):
                try:
                    inicio = datetime.strptime(row['Inicio'], "%Y-%m-%d %H:%M:%S")
                    acumulado = float(row['TiempoAcumulado'])
                    if row['Estado'] == "Abierta":
                        segundos_actuales = (ahora - inicio).total_seconds()
                        total_segundos = acumulado + segundos_actuales
                    else:
                        total_segundos = acumulado
                    
                    horas = int(total_segundos // 3600)
                    minutos = int((total_segundos % 3600) // 60)
                    return f"{horas}h {minutos}m"
                except:
                    return "0h 0m"

            pendientes['Duración'] = pendientes.apply(formatear_duracion, axis=1)

            st.subheader("📋 Resumen de Órdenes en Proceso")
            
            # Función para aplicar estilos de color
            def estilo_estados(val):
                if val == 'Abierta': return 'color: green; font-weight: bold'
                if val == 'En Pausa': return 'color: orange; font-weight: bold'
                if val == 'Cerrada': return 'color: red; font-weight: bold'
                return ''

            # Usamos .map (compatible con versiones nuevas) sobre el styler
            st.dataframe(
                pendientes[["OT", "Estado", "Empleado", "Tipo", "Inicio", "Duración", "Comentarios", "Descripcion"]]
                .style.map(estilo_estados, subset=['Estado']),
                use_container_width=True,
                hide_index=True
            )
            
            st.divider()
            
            opciones = ["--- Seleccione una orden ---"] + (pendientes['OT'] + " | " + pendientes['Empleado']).tolist()
            sel = st.selectbox("Escoger OT para editar:", opciones)

            if sel != "--- Seleccione una orden ---":
                id_sel = sel.split(" | ")[0]
                idx = df_ot.index[df_ot['OT'] == id_sel].tolist()[0]
                
                with st.form("form_cierre", clear_on_submit=True):
                    st.write(f"### Gestionando OT #{id_sel}")
                    nuevo_est = st.selectbox("Cambiar Estado", ["Abierta", "En Pausa", "Cerrada"], 
                                             index=["Abierta", "En Pausa", "Cerrada"].index(df_ot.at[idx, 'Estado']))
                    coment = st.text_area("Comentarios de avance/finales", value=df_ot.at[idx, 'Comentarios'])
                    
                    if st.form_submit_button("Actualizar y Guardar"):
                        ahora_act = obtener_fecha_cr()
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
        df_historial = df_ot.copy()
        # Cambiado applymap por map para evitar el AttributeError
        st.dataframe(
            df_historial.style.map(estilo_estados, subset=['Estado']), 
            use_container_width=True
        )

elif menu == "📊 Dashboard":
    st.header("📊 Dashboard de Rendimiento")
    # ... (Aquí va tu bloque de dashboard con filtros anterior)
