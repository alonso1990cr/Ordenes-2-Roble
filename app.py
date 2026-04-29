import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time
import os

# --- CONFIGURACIÓN Y CONSTANTES ---
# Datos obtenidos de configuraciones previas
TIMEZONE_ADJUST = timedelta(hours=6) # Ajuste para Costa Rica (UTC-6)
DESTINATARIOS_FIJOS = ["ronald.badilla@gruporoble.com", "mario.robleto@gruporoble.com"]

# --- FUNCIONES DE CÁLCULO DE TIEMPO ---
def obtener_fecha_cr():
    return datetime.utcnow() - TIMEZONE_ADJUST

def calcular_duracion_laboral(inicio, fin):
    """Calcula duración ignorando horas fuera de jornada y almuerzo (12md-1pm)"""
    duracion_total = timedelta(0)
    current = inicio
    
    while current < fin:
        # Definir jornada del día actual
        if current.weekday() < 5: # Lunes a Viernes
            start_work = current.replace(hour=8, minute=0, second=0)
            end_work = current.replace(hour=17, minute=0, second=0)
            almuerzo_inicio = current.replace(hour=12, minute=0, second=0)
            almuerzo_fin = current.replace(hour=13, minute=0, second=0)
        elif current.weekday() == 5: # Sábado
            start_work = current.replace(hour=7, minute=0, second=0)
            end_work = current.replace(hour=12, minute=0, second=0)
            almuerzo_inicio = almuerzo_fin = end_work
        else: # Domingo
            current = (current + timedelta(days=1)).replace(hour=8, minute=0)
            continue

        # Ajustar ventana de trabajo efectiva
        work_period_start = max(current, start_work)
        work_period_end = min(fin, end_work)

        if work_period_start < work_period_end:
            # Restar almuerzo si el periodo lo cruza
            total_segundos = (work_period_end - work_period_start).total_seconds()
            if work_period_start < almuerzo_inicio and work_period_end > almuerzo_fin:
                total_segundos -= 3600
            
            duracion_total += timedelta(seconds=max(0, total_segundos))
            
        # Avanzar al siguiente día
        current = (current + timedelta(days=1)).replace(hour=8, minute=0)
    
    return duracion_total

def obtener_emoji_duracion(horas):
    if horas < 2: return "⚡ (Rápido)"
    if horas < 8: return "⏳ (Normal)"
    return "🐢 (Extenso)"

# --- PERSISTENCIA DE DATOS (CSV) ---
def cargar_datos(archivo, columnas):
    if os.path.exists(archivo):
        return pd.read_csv(archivo)
    return pd.DataFrame(columns=columnas)

# --- INTERFAZ ---
st.set_page_config(page_title="Sistema Gestión Roble", layout="wide")

menu = st.sidebar.selectbox("Menú", ["Empleados", "Órdenes de Trabajo", "Cierre de Órdenes"])

# 1. REGISTRO DE EMPLEADOS
if menu == "Empleados":
    st.header("👥 Gestión de Empleados")
    df_emp = cargar_datos("empleados.csv", ["Nombre", "Correo"])
    
    with st.expander("Añadir / Modificar Empleado"):
        nombre = st.text_input("Nombre Completo")
        correo = st.text_input("Correo Electrónico")
        if st.button("Guardar Empleado"):
            if nombre in df_emp['Nombre'].values:
                df_emp.loc[df_emp['Nombre'] == nombre, 'Correo'] = correo
            else:
                new_row = pd.DataFrame({"Nombre": [nombre], "Correo": [correo]})
                df_emp = pd.concat([df_emp, new_row], ignore_index=True)
            df_emp.to_csv("empleados.csv", index=False)
            st.success("Empleado guardado.")

    st.table(df_emp)
    
    if not df_emp.empty:
        eliminar = st.selectbox("Eliminar empleado", df_emp['Nombre'])
        if st.button("Eliminar"):
            df_emp = df_emp[df_emp['Nombre'] != eliminar]
            df_emp.to_csv("empleados.csv", index=False)
            st.rerun()

# 2. ÓRDENES DE TRABAJO
elif menu == "Órdenes de Trabajo":
    st.header("📋 Nueva Orden de Trabajo")
    df_emp = cargar_datos("empleados.csv", ["Nombre", "Correo"])
    df_ot = cargar_datos("ordenes.csv", ["OT", "Empleado", "Descripcion", "Inicio", "Tipo", "Estado", "Fin", "Comentarios"])

    if df_emp.empty:
        st.warning("Registre empleados primero.")
    else:
        with st.form("nueva_ot"):
            empleado = st.selectbox("Asignar a", df_emp['Nombre'])
            desc = st.text_area("Descripción del trabajo")
            tipo = st.radio("Tipo", ["Preventivo", "Correctivo"])
            
            if st.form_submit_button("Generar Orden"):
                # Generación automática de consecutivo
                ahora = obtener_fecha_cr()
                num_ot = ahora.strftime("%m%d-%H%M") 
                
                nueva_fila = {
                    "OT": num_ot, "Empleado": empleado, "Descripcion": desc,
                    "Inicio": ahora.strftime("%Y-%m-%d %H:%M:%S"), 
                    "Tipo": tipo, "Estado": "Abierta", "Fin": "", "Comentarios": ""
                }
                df_ot = pd.concat([df_ot, pd.DataFrame([nueva_fila])], ignore_index=True)
                df_ot.to_csv("ordenes.csv", index=False)
                
                # Simulación de envío de correo
                email_emp = df_emp[df_emp['Nombre'] == empleado]['Correo'].values[0]
                st.success(f"OT #{num_ot} creada. Correos enviados a: {email_emp} y supervisores.")

# 3. CIERRE Y CONSULTA
elif menu == "Cierre de Órdenes":
    st.header("✅ Consulta y Cierre")
    df_ot = cargar_datos("ordenes.csv", ["OT", "Empleado", "Descripcion", "Inicio", "Tipo", "Estado", "Fin", "Comentarios"])
    df_emp = cargar_datos("empleados.csv", ["Nombre", "Correo"])
    
    persona = st.selectbox("Consultar Trabajador", df_emp['Nombre'] if not df_emp.empty else [])
    
    if persona:
        ultimas_3 = df_ot[df_ot['Empleado'] == persona].tail(3)
        st.write("Últimas 3 órdenes:")
        st.dataframe(ultimas_3)
        
        ot_id = st.selectbox("Seleccione OT para cerrar", ultimas_3[ultimas_3['Estado'] == "Abierta"]['OT'])
        comentarios = st.text_area("Comentarios de cierre")
        
        if st.button("Cerrar Orden Seleccionada"):
            fin_dt = obtener_fecha_cr()
            inicio_str = df_ot.loc[df_ot['OT'] == ot_id, 'Inicio'].values[0]
            inicio_dt = datetime.strptime(inicio_str, "%Y-%m-%d %H:%M:%S")
            
            duracion = calcular_duracion_laboral(inicio_dt, fin_dt)
            horas_decimal = duracion.total_seconds() / 3600
            
            df_ot.loc[df_ot['OT'] == ot_id, ['Estado', 'Fin', 'Comentarios']] = ["Cerrada", fin_dt.strftime("%Y-%m-%d %H:%M:%S"), comentarios]
            df_ot.to_csv("ordenes.csv", index=False)
            
            st.balloons()
            st.info(f"Orden cerrada. Duración laboral: {duracion} {obtener_emoji_duracion(horas_decimal)}")

# TABLA GENERAL DE SEGUIMIENTO
st.divider()
st.subheader("📊 Historial General")
df_final = cargar_datos("ordenes.csv", [])
if not df_final.empty:
    # Formatear duración para la tabla
    def aplicar_formato(row):
        if row['Estado'] == "Cerrada":
            inicio = datetime.strptime(row['Inicio'], "%Y-%m-%d %H:%M:%S")
            fin = datetime.strptime(row['Fin'], "%Y-%m-%d %H:%M:%S")
            d = calcular_duracion_laboral(inicio, fin)
            return f"{d} {obtener_emoji_duracion(d.total_seconds()/3600)}"
        return "En curso... 🛠️"

    df_final['Duración Real'] = df_final.apply(aplicar_formato, axis=1)
    st.dataframe(df_final, use_container_width=True)
