elif menu == "🔍 Cierre y Consulta":
    st.markdown(f'<div class="reloj-discreto">Hora CR: {obtener_fecha_cr().strftime("%H:%M:%S")}</div>', unsafe_allow_html=True)
    st.header("🔍 Gestión de Cierre y Consulta")
    tab1, tab2 = st.tabs(["Órdenes Activas", "Historial Completo"])
    
    with tab1:
        pendientes = df_ot[df_ot['Estado'].str.contains("Abierta|En Pausa", case=False, na=False)].copy()
        
        if pendientes.empty:
            st.info("No hay órdenes pendientes de cierre.")
        else:
            # --- TABLA DE RESUMEN ---
            ahora = obtener_fecha_cr()
            def calcular_horas(row):
                try:
                    inicio = datetime.strptime(row['Inicio'], "%Y-%m-%d %H:%M:%S")
                    acumulado = float(row['TiempoAcumulado'])
                    if row['Estado'] == "Abierta":
                        segundos_actuales = (ahora - inicio).total_seconds()
                        return round((acumulado + segundos_actuales) / 3600, 2)
                    return round(acumulado / 3600, 2)
                except: return 0.0

            pendientes['Duración (Hrs)'] = pendientes.apply(calcular_horas, axis=1)
            st.subheader("📋 Resumen de Órdenes en Proceso")
            st.dataframe(
                pendientes[["OT", "Estado", "Empleado", "Tipo", "Inicio", "Duración (Hrs)", "Comentarios", "Descripcion"]], 
                use_container_width=True
            )
            
            st.divider()
            
            # --- FORMULARIO DE EDICIÓN ---
            # Usamos un key dinámico basado en un estado de limpieza si fuera necesario
            opciones = ["--- Seleccione una orden ---"] + (pendientes['OT'] + " | " + pendientes['Empleado'] + " | " + pendientes['Descripcion']).tolist()
            sel = st.selectbox("Seleccione Orden para gestionar cierre:", opciones, key="selector_cierre")

            if sel != "--- Seleccione una orden ---":
                id_sel = sel.split(" | ")[0]
                idx = df_ot.index[df_ot['OT'] == id_sel].tolist()[0]

                col_foto, col_form = st.columns([1, 2])
                
                with col_foto:
                    foto_nom = str(df_ot.at[idx, 'Foto'])
                    if foto_nom != "Sin foto" and foto_nom != "":
                        ruta = os.path.join("fotos", foto_nom)
                        if os.path.exists(ruta):
                            st.image(ruta, caption=f"Evidencia OT #{id_sel}")
                    else:
                        st.info("Sin foto adjunta")

                with col_form:
                    # Importante: clear_on_submit=True limpia los widgets internos del formulario
                    with st.form("form_cierre", clear_on_submit=True):
                        st.write(f"**Editando OT: {id_sel}**")
                        nuevo_est = st.selectbox("Cambiar Estado", ["Abierta", "En Pausa", "Cerrada"], 
                                                 index=["Abierta", "En Pausa", "Cerrada"].index(df_ot.at[idx, 'Estado']))
                        coment = st.text_area("Comentarios finales / Avances", value=df_ot.at[idx, 'Comentarios'])
                        
                        btn_guardar = st.form_submit_button("Actualizar y Guardar")
                        
                        if btn_guardar:
                            ahora_cierre = obtener_fecha_cr()
                            
                            # Lógica de acumulación de tiempo
                            if df_ot.at[idx, 'Estado'] == "Abierta":
                                inicio_dt = datetime.strptime(df_ot.at[idx, 'Inicio'], "%Y-%m-%d %H:%M:%S")
                                dif_segundos = (ahora_cierre - inicio_dt).total_seconds()
                                df_ot.at[idx, 'TiempoAcumulado'] = str(float(df_ot.at[idx, 'TiempoAcumulado']) + dif_segundos)
                            
                            if nuevo_est == "Abierta":
                                df_ot.at[idx, 'Inicio'] = ahora_cierre.strftime("%Y-%m-%d %H:%M:%S")
                            elif nuevo_est == "Cerrada":
                                df_ot.at[idx, 'Fin'] = ahora_cierre.strftime("%Y-%m-%d %H:%M:%S")
                            
                            df_ot.at[idx, 'Estado'] = nuevo_est
                            df_ot.at[idx, 'Comentarios'] = coment
                            
                            # Guardar en CSV
                            guardar_datos(df_ot, "ordenes.csv")
                            
                            # Mensaje de éxito
                            st.success("✅ Registro actualizado correctamente")
                            
                            # El st.rerun() limpia la selección del selectbox y refresca la tabla superior
                            st.rerun()
