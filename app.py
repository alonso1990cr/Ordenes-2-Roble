# --- SECCIÓN: CIERRE Y CONSULTA (ACTUALIZADA) ---
elif menu == "🔍 Cierre y Consulta":
    st.header("🔍 Gestión de Cierre y Consulta")
    tab1, tab2 = st.tabs(["Órdenes Activas", "Historial Completo"])
    
    with tab1:
        pendientes = df_ot[df_ot['Estado'].isin(["Abierta", "En Pausa"])].copy()
        if not pendientes.empty:
            ahora = obtener_fecha_cr()
            def calc_dur(row):
                try:
                    sec = float(row['TiempoAcumulado'])
                    if row['Estado'] == "Abierta":
                        sec += (ahora - datetime.strptime(row['Inicio'], "%Y-%m-%d %H:%M:%S")).total_seconds()
                    return f"{int(sec//3600)}h {int((sec%3600)//60)}m"
                except: return "0h 0m"
            
            pendientes['Duración'] = pendientes.apply(calc_dur, axis=1)
            st.dataframe(pendientes[["OT", "Estado", "Empleado", "Tipo", "Duración", "Descripcion"]].style.map(estilo_estados, subset=['Estado']), use_container_width=True, hide_index=True)
            
            sel = st.selectbox("Seleccionar OT:", ["---"] + (pendientes['OT'] + " | " + pendientes['Empleado']).tolist())
            if sel != "---":
                id_sel = sel.split(" | ")[0]
                idx = df_ot.index[df_ot['OT'] == id_sel].tolist()[0]
                
                # --- LÓGICA DE IMAGEN CON MENSAJE DE "NO DISPONIBLE" ---
                f_nom = df_ot.at[idx, 'Foto']
                ruta_foto = os.path.join("fotos", f_nom)
                
                if f_nom != "Sin foto" and os.path.exists(ruta_foto) and os.path.getsize(ruta_foto) > 0:
                    try:
                        st.image(ruta_foto, width=350, caption=f"Evidencia OT #{id_sel}")
                    except Exception:
                        st.warning("⚠️ No hay imagen disponible o el archivo está dañado.")
                else:
                    st.info("ℹ️ No hay imagen disponible para esta orden.")
                
                with st.form("cierre_form"):
                    nuevo_est = st.selectbox("Estado", ["Abierta", "En Pausa", "Cerrada"], index=["Abierta", "En Pausa", "Cerrada"].index(df_ot.at[idx, 'Estado']))
                    nuevo_com = st.text_area("Comentarios", value=df_ot.at[idx, 'Comentarios'])
                    
                    if st.form_submit_button("Actualizar Registro"):
                        ahora_act = obtener_fecha_cr()
                        if df_ot.at[idx, 'Estado'] == "Abierta":
                            ini_dt = datetime.strptime(df_ot.at[idx, 'Inicio'], "%Y-%m-%d %H:%M:%S")
                            df_ot.at[idx, 'TiempoAcumulado'] = str(float(df_ot.at[idx, 'TiempoAcumulado']) + (ahora_act - ini_dt).total_seconds())
                        
                        df_ot.at[idx, 'Estado'], df_ot.at[idx, 'Comentarios'] = nuevo_est, nuevo_com
                        if nuevo_est == "Abierta": df_ot.at[idx, 'Inicio'] = ahora_act.strftime("%Y-%m-%d %H:%M:%S")
                        elif nuevo_est == "Cerrada":
                            df_ot.at[idx, 'Fin'] = ahora_act.strftime("%Y-%m-%d %H:%M:%S")
                            correo_op = df_emp[df_emp['Nombre'] == df_ot.at[idx, 'Empleado']]['Correo'].values[0]
                            enviar_notificacion(["sa.alterna@gmail.com", correo_op, df_ot.at[idx, 'CorreoCopia']], f"Cierre OT #{id_sel}", f"OT CERRADA.\nComentarios: {nuevo_com}")
                        
                        guardar_datos(df_ot, "ordenes.csv"); st.rerun()
