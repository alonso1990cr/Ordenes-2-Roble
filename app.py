import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import plotly.express as px # Nueva librería para gráficos

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Gestión OT - Roble", layout="wide")
UTC_OFFSET = 6
CORREO_COPIA = "sa.alterna@gmail.com"

# --- FUNCIONES DE APOYO (Mantenemos las anteriores) ---
def cargar_datos(archivo, columnas):
    if os.path.exists(archivo):
        df = pd.read_csv(archivo, dtype=str)
        for col in columnas:
            if col not in df.columns: df[col] = ""
        return df
    return pd.DataFrame(columns=columnas)

def guardar_datos(df, archivo):
    df.to_csv(archivo, index=False)

def obtener_fecha_cr():
    return datetime.utcnow() - timedelta(hours=UTC_OFFSET)

def calcular_duracion_laboral(inicio, fin):
    total_segundos = 0
    curr = inicio
    while curr < fin:
        if curr.weekday() < 5: h_ini, h_fin, almuerzo = 8, 17, True
        elif curr.weekday() == 5: h_ini, h_fin, almuerzo = 7, 12, False
        else:
            curr = (curr + timedelta(days=1)).replace(hour=8, minute=0)
            continue
        ent = max(curr, curr.replace(hour=h_ini, minute=0, second=0))
        sal = min(fin, curr.replace(hour=h_fin, minute=0, second=0))
        if ent < sal:
            seg = (sal - ent).total_seconds()
            if almuerzo and ent.hour < 12 and sal.hour >= 13: seg -= 3600
            total_segundos += max(0, seg)
        curr = (curr + timedelta(days=1)).replace(hour=h_ini, minute=0)
    return timedelta(seconds=total_segundos)

# --- INTERFAZ ---
menu = st.sidebar.selectbox("MENÚ PRINCIPAL", ["Dashboard", "Gestión de Empleados", "Nueva Orden de Trabajo", "Cierre y Consulta de OT"])

# --- PESTAÑA NUEVA: DASHBOARD ---
if menu == "Dashboard":
    st.header("📊 Dashboard de Rendimiento")
    df_ot = cargar_datos("ordenes.csv", ["OT", "Empleado", "Descripcion", "Inicio", "Tipo", "Estado", "Fin", "Comentarios"])
    df_emp = cargar_datos("empleados.csv", ["Nombre", "Correo"])

    if df_ot.empty:
        st.info("No hay datos suficientes para generar el dashboard.")
    else:
        # Preparación de datos para el Dashboard
        df_dash = df_ot.copy()
        df_dash['Inicio'] = pd.to_datetime(df_dash['Inicio'])
        df_dash['Fin'] = pd.to_datetime(df_dash['Fin'], errors='coerce')
        
        # Calcular duración numérica para la gráfica
        def get_hours(row):
            if pd.notna(row['Fin']):
                d = calcular_duracion_laboral(row['Inicio'], row['Fin'])
                return round(d.total_seconds() / 3600, 2)
            return 0
        df_dash['Horas_Laboradas'] = df_dash.apply(get_hours, axis=1)

        # --- FILTROS ---
        st.sidebar.write("### Filtros de Análisis")
        f_emp = st.sidebar.selectbox("Operario:", ["TODOS"] + list(df_emp['Nombre'].unique()))
        f_inicio = st.sidebar.date_input("Fecha Inicio", df_dash['Inicio'].min().date())
        f_fin = st.sidebar.date_input("Fecha Fin", obtener_fecha_cr().date())

        # Aplicar filtros
        mask = (df_dash['Inicio'].dt.date >= f_inicio) & (df_dash['Inicio'].dt.date <= f_fin)
        if f_emp != "TODOS":
            mask = mask & (df_dash['Empleado'] == f_emp)
        
        df_filtrado = df_dash.loc[mask]

        # --- MÉTRICAS CLAVE ---
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Órdenes", len(df_filtrado))
        col2.metric("Órdenes Cerradas", len(df_filtrado[df_filtrado['Estado'] == 'Cerrada']))
        col3.metric("Promedio Horas/OT", f"{df_filtrado[df_filtrado['Horas_Laboradas'] > 0]['Horas_Laboradas'].mean():.2f}")

        # --- GRÁFICA ---
        st.subheader("Duración de Trabajo por Orden")
        if not df_filtrado.empty:
            fig = px.bar(df_filtrado, x='OT', y='Horas_Laboradas', color='Empleado',
                         title="Horas Efectivas por Orden de Trabajo",
                         labels={'Horas_Laboradas': 'Horas (Sin Almuerzo/Fines de Semana)'},
                         hover_data=['Tipo', 'Estado'])
            st.plotly_chart(fig, use_container_width=True)
            
            st.write("### Detalle de Datos Filtrados")
            st.dataframe(df_filtrado[['OT', 'Empleado', 'Tipo', 'Estado', 'Inicio', 'Fin', 'Horas_Laboradas']], use_container_width=True)
        else:
            st.warning("No hay registros en el rango seleccionado.")

# --- (Mantén aquí el resto de las secciones: Gestión de Empleados, Nueva OT, Cierre de OT) ---
# ... (El código anterior de las otras pestañas se inserta aquí)
