# 2. NUEVA ORDEN DE TRABAJO (ACTUALIZADA)
elif menu == "📝 Nueva Orden de Trabajo":
    st.header("📝 Apertura de Orden de Trabajo")
    if df_emp.empty: 
        st.warning("Debe registrar al menos un empleado antes de abrir una OT.")
    else:
        with st.form("nueva_ot", clear_on_submit=True):
            operario = st.selectbox("Seleccionar Operario", df_emp['Nombre'])
            
            # Requisito: Agregar Casos 24h y Casos ISO
            tipo = st.radio(
                "Tipo de Mantenimiento / Categoría", 
                ["Preventivo", "Correctivo", "Casos 24h", "Casos ISO"],
                horizontal=True
            )
            
            desc = st.text_area("Descripción de la falla, tarea o caso")
            
            if st.form_submit_button("Generar y Notificar OT"):
                if desc:
                    ahora = obtener_fecha_cr()
                    # El ID sigue siendo YYYYMMDD-HHMM
                    num_ot = ahora.strftime("%Y%m%d-%H%M")
                    
                    nueva_linea = {
                        "OT": num_ot, 
                        "Empleado": operario, 
                        "Descripcion": desc, 
                        "Inicio": ahora.strftime("%Y-%m-%d %H:%M:%S"), 
                        "Tipo": tipo, 
                        "Estado": "Abierta", 
                        "Fin": "", 
                        "Comentarios": ""
                    }
                    
                    # Actualizar DataFrame y persistir en ordenes.csv
                    df_ot = pd.concat([df_ot, pd.DataFrame([nueva_linea])], ignore_index=True)
                    guardar_datos(df_ot, "ordenes.csv")
                    
                    # Notificación automática al operario
                    correo_op = df_emp[df_emp['Nombre'] == operario]['Correo'].values[0]
                    asunto = f"Nueva OT Asignada ({tipo}): #{num_ot}"
                    cuerpo = f"Se ha abierto una orden de tipo {tipo}.\nDescripción: {desc}"
                    
                    if enviar_correo(correo_op, asunto, cuerpo):
                        st.success(f"OT #{num_ot} creada y notificada con éxito.")
                    else:
                        st.warning(f"OT #{num_ot} creada, pero hubo un error al enviar el correo.")
                    
                    st.rerun()
                else:
                    st.error("Por favor, agregue una descripción para la orden.")
