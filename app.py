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
    # ... (Se mantiene igual que la versión anterior)

elif menu == "📝 Nueva OT":
    st.header("📝 Apertura de Orden de Trabajo")
    # ... (Se mantiene igual que la versión anterior)

elif menu == "🔍 Cierre y Consulta":
    st.header("🔍 Gestión de Cierre y Consulta")
    tab1, tab2 = st.tabs(["Órdenes Activas", "Historial Completo"])
    
    with tab1:
        pendientes = df_ot[df_ot['Estado'].str.contains("Abierta|En Pausa", case=False, na=False)].copy()
        
        if pendientes.empty:
            st.info("No hay órdenes pendientes de cierre.")
        else:
            ahora = obtener_fecha_cr()
            
            # Función para convertir segundos a formato "Xh Ym"
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
            
            # Renderizado de la tabla con colores dinámicos
            st.dataframe(
                pendientes[["OT", "Estado", "Empleado", "Tipo", "Inicio", "Duración", "Comentarios", "Descripcion"]],
                use_container_width=True,
                column_config={
                    "Estado": st.column_config.TextColumn(
                        "Estado",
                        help="Estado actual de la orden",
                    )
                },
                hide_index=True,
            )
            
            # Aplicar colores mediante CSS inyectado para las filas de la tabla
            st.markdown("""
                <style>
                [data-testid="stTable"] td:nth-child(2) { font-weight: bold; }
                </style>
                """, unsafe_allow_html=True)
            
            # (Nota: Streamlit st.dataframe no permite color de texto celda por celda fácilmente sin st.table o librerías extra, 
            # pero aquí forzamos la lógica visual en el formulario de edición que sigue abajo)

            st.divider()
            
            opciones = ["--- Seleccione una orden ---"] + (pendientes['OT'] + " | " + pendientes['Empleado']).tolist()
            sel = st.selectbox("Escoger OT para editar:", opciones)

            if sel != "--- Seleccione una orden ---":
                id_sel = sel.split(" | ")[0]
                idx = df_ot.index[df_ot['OT'] == id_sel].tolist()[0]
                estado_actual = df_ot.at[idx, 'Estado']

                # Mostrar indicador visual de color según estado
                color = "green" if estado_actual == "Abierta" else "orange" # Amarillo/Naranja para pausa
                st.markdown(f"**Estado actual:** :{color}[{estado_actual}]")

                with st.form("form_cierre", clear_on_submit=True):
                    nuevo_est = st.selectbox("Cambiar Estado", ["Abierta", "En Pausa", "Cerrada"], 
                                             index=["Abierta", "En Pausa", "Cerrada"].index(estado_actual))
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
        # En el historial completo aplicamos el color Rojo a las cerradas
        st.subheader("📚 Historial Completo")
        
        def resaltar_estado(val):
            color = 'green' if val == 'Abierta' else 'orange' if val == 'En Pausa' else 'red'
            return f'color: {color}; font-weight: bold'

        df_historial = df_ot.copy()
        st.dataframe(df_historial.style.applymap(resaltar_estado, subset=['Estado']), use_container_width=True)

elif menu == "📊 Dashboard":
    # ... (Se mantiene igual que la versión anterior con los filtros de dashboard)
    st.header("📊 Dashboard de Rendimiento")
