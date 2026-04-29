import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import plotly.express as px
import io
import time

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Gestión OT - Roble", layout="wide")
UTC_OFFSET = 6 
CORREO_ADMIN = "sa.alterna@gmail.com"

# --- ESTILO PERSONALIZADO ---
st.markdown("""
    <style>
    .stTextInput > div > div > input, .stTextArea > div > div > textarea,
    .stSelectbox > div > div > div, .stMultiSelect > div > div {
        background-color: #e8f5e9 !important; color: #1b5e20 !important;
    }
    .reloj-vivo {
        font-size: 24px; font-weight: bold; color: #2e7d32;
        padding: 10px; border: 2px solid #2e7d32; border-radius: 10px;
        text-align: center; margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- FUNCIONES DE PERSISTENCIA ---
def cargar_datos(archivo, columnas):
    if os.path.exists(archivo):
        df = pd.read_csv(archivo, dtype=str)
        for col in columnas:
            if col not in df.columns: df[col] = "0" if "Tiempo" in col else ""
        return df
    return pd.DataFrame(columns=columnas)

def guardar_datos(df, archivo):
    df.to_csv(archivo, index=False)

# --- FUNCIONES TÉCNICAS ---
def obtener_fecha_cr():
    return datetime.utcnow() - timedelta(hours=UTC_OFFSET)

def generar_siguiente_ot(df_ot):
    if df_ot.empty: return "0001"
    try:
        ultimo_num = int(df_ot['OT'].iloc[-1])
        return f"{ultimo_num + 1:04d}"
    except: return "0001"

def calcular_duracion_real(inicio_str, fin_str, acumulado_seg):
    try:
        acumulado = float(acumulado_seg)
        if not fin_str or fin_str == "":
            return str(timedelta(seconds=int(acumulado))).split(".")[0]
        
        ini = datetime.strptime(inicio_str, "%Y-%m-%d %H:%M:%S")
        fin = datetime.strptime(fin_str, "%Y-%m-%d %H:%M:%S")
        
        # Aquí podrías usar tu función de horario laboral si lo prefieres, 
        # por ahora sumamos el tiempo transcurrido al acumulado
        actual = (fin - ini).total_seconds()
        total = acumulado + actual
        return str(timedelta(seconds=int(total))).split(".")[0]
    except: return "0:00:00"

# --- CARGA DE DATOS ---
cols_ot = ["OT", "Empleado", "Descripcion", "Inicio", "Tipo", "Estado", "Fin", "Comentarios", "CorreoCopia", "TiempoAcumulado"]
df_emp = cargar_datos("empleados.csv", ["Nombre", "Correo"])
df_ot = cargar_datos("ordenes.csv", cols_ot)

# --- MENÚ ---
menu = st.sidebar.selectbox("MENÚ", ["👥 Empleados", "📝 Nueva OT", "🔍 Cierre y Consulta", "📊 Dashboard"])

# 1. EMPLEADOS (Simplificado para el ejemplo)
if menu == "👥 Empleados":
    st.header("👥 Gestión de Operarios")
    st.table(df_emp)

# 2. NUEVA OT
elif menu == "📝 Nueva OT":
    st.header("📝 Apertura de OT")
    with st.form("nueva_ot"):
        operario = st.selectbox("Operario", df_emp['Nombre'])
        tipo = st.radio("Tipo", ["Preventivo", "Correctivo", "Casos 24h", "Casos ISO"], horizontal=True)
        desc = st.text_area("Descripción")
        copia = st.text_input("Correo de copia obligatorio")
        if st.form_submit_button("Generar"):
            if desc and copia:
                ahora = obtener_fecha_cr().strftime("%Y-%m-%d %H:%M:%S")
                nueva = {"OT": generar_siguiente_ot(df_ot), "Empleado": operario, "Descripcion": desc, 
                         "Inicio": ahora, "Tipo": tipo, "Estado": "Abierta", "Fin": "", 
                         "Comentarios": "", "CorreoCopia": copia, "TiempoAcumulado": "0"}
                df_ot = pd.concat([df_ot, pd.DataFrame([nueva])], ignore_index=True)
                guardar_datos(df_ot, "ordenes.csv")
                st.success("OT Creada")
                st.rerun()

# 3. CIERRE Y CONSULTA (CON RELOJ Y PAUSA)
elif menu == "🔍 Cierre y Consulta":
    # Reloj en vivo
    ahora_reloj = obtener_fecha_cr().strftime("%H:%M:%S")
    st.markdown(f'<div class="reloj-vivo">🕒 Hora en Vivo (Costa Rica): {ahora_reloj}</div>', unsafe_allow_html=True)
    
    t1, t2 = st.tabs(["Pendientes (Abiertas/Pausa)", "Historial Cerradas"])
    
    with t1:
        # Filtrar solo las que no están cerradas
        pendientes = df_ot[df_ot['Estado'] != "Cerrada"].copy()
        
        if pendientes.empty:
            st.info("No hay órdenes pendientes.")
        else:
            # Calcular duración actual para mostrar en tabla
            def duracion_viva(row):
                if row['Estado'] == "Abierta":
                    ini = datetime.strptime(row['Inicio'], "%Y-%m-%d %H:%M:%S")
                    actual = (obtener_fecha_cr() - ini).total_seconds()
                    total = float(row['TiempoAcumulado']) + actual
                    return str(timedelta(seconds=int(total)))
                else: # En Pausa
                    return str(timedelta(seconds=int(float(row['TiempoAcumulado']))))

            pendientes['Duración Actual'] = pendientes.apply(duracion_viva, axis=1)
            st.dataframe(pendientes[["OT", "Empleado", "Estado", "Duración Actual", "Tipo", "Descripcion"]], use_container_width=True)
            
            # Formulario de modificación
            sel = st.selectbox("Seleccionar OT para gestionar:", pendientes['OT'] + " - " + pendientes['Descripcion'])
            id_sel = sel.split(" - ")[0]
            idx = df_ot.index[df_ot['OT'] == id_sel].tolist()[0]
            
            with st.form("gestion_ot"):
                nuevo_estado = st.selectbox("Cambiar estado a:", ["Abierta", "En Pausa", "Cerrada"], index=["Abierta", "En Pausa", "Cerrada"].index(df_ot.at[idx, 'Estado']))
                coment = st.text_area("Comentarios", value=df_ot.at[idx, 'Comentarios'])
                
                if st.form_submit_button("Actualizar Estado"):
                    ahora = obtener_fecha_cr()
                    estado_anterior = df_ot.at[idx, 'Estado']
                    
                    # LÓGICA DE TIEMPO
                    if estado_anterior == "Abierta":
                        # Si estaba abierta, calculamos cuánto tiempo pasó y lo sumamos al acumulado
                        ini = datetime.strptime(df_ot.at[idx, 'Inicio'], "%Y-%m-%d %H:%M:%S")
                        segundos_transcurridos = (ahora - ini).total_seconds()
                        df_ot.at[idx, 'TiempoAcumulado'] = str(float(df_ot.at[idx, 'TiempoAcumulado']) + segundos_transcurridos)
                    
                    if nuevo_estado == "Abierta":
                        # Si se abre o se reanuda, el nuevo "Inicio" es ahora
                        df_ot.at[idx, 'Inicio'] = ahora.strftime("%Y-%m-%d %H:%M:%S")
                    
                    if nuevo_estado == "Cerrada":
                        df_ot.at[idx, 'Fin'] = ahora.strftime("%Y-%m-%d %H:%M:%S")
                    
                    df_ot.at[idx, 'Estado'] = nuevo_estado
                    df_ot.at[idx, 'Comentarios'] = coment
                    guardar_datos(df_ot, "ordenes.csv")
                    st.success(f"OT {id_sel} actualizada a {nuevo_estado}")
                    st.rerun()

    with t2:
        cerradas = df_ot[df_ot['Estado'] == "Cerrada"].copy()
        if not cerradas.empty:
            cerradas['Duración Final'] = cerradas.apply(lambda r: calcular_duracion_real(r['Inicio'], r['Fin'], r['TiempoAcumulado']), axis=1)
            st.dataframe(cerradas[["OT", "Empleado", "Tipo", "Duración Final", "Comentarios"]], use_container_width=True)

# 4. DASHBOARD (Mantiene filtros anteriores)
elif menu == "📊 Dashboard":
    st.header("📊 Dashboard")
    # ... (Se mantiene igual al código anterior)
