# app.py

import sys
import streamlit as st
import pandas as pd
import io # Mantenuto per ExcelWriter
import numpy as np
import base64
import os
from pathlib import Path
from fpdf import FPDF, XPos, YPos

# Importa le funzioni di LOGICA da core_logic
from core_logic import SolverA3, estrai_dati_bolla_reale

# Importa le funzioni di STILE e UTILITY da styles.py
from styles import (
    apply_custom_css, 
    create_pdf_from_df,
    prepare_data_entry_export
) 

# Importa le funzioni di DATA da data_utils.py
from data_utils import (
    _normalize,
    # extract_m2_classic_data è stata rimossa perché obsoleta
    read_excel_or_csv,
    select_three_columns
)

# FUNZIONE DI ORCHESTRAZIONE (CONTROLLER) - LOGICA UNIFICATA
def run_processing(): 
    """
    Esegue l'intero processo con logica di solving UNIFICATA (SolverA3)
    Legge i dati ESCLUSIVAMENTE da st.session_state.voci_final_data e st.session_state.partite_final_data.
    
    Restituisce 4 valori: (msg, df_risultato, residui, opzione_processing).
    """
    
    # 1. Prepara VOCI dall'editor
    try:
        voci_df_editor = st.session_state.voci_final_data.copy()
        
        # Mappa dai nomi visualizzati (es. 'Colli') ai nomi interni del solver (es. 'colli')
        voci_df_solver = voci_df_editor.rename(columns={
            "Voce Doganale": "nome",
            "Colli": "colli",
            "Peso lordo": "peso"
        }).copy()
        
        voci_df_solver["nome"] = voci_df_solver["nome"].astype(str).str.strip()
        voci_df_solver["colli"] = pd.to_numeric(voci_df_solver["colli"], errors="coerce").fillna(0)
        voci_df_solver["peso"] = pd.to_numeric(voci_df_solver["peso"], errors="coerce").fillna(0)
        
    except Exception as e:
        return f"Errore during la preparazione delle Voci H1: {e}", None, None, None


    # 2. Prepara PARTITE A3 dall'editor
    try:
        partite_df_editor = st.session_state.partite_final_data.copy()
        
        cols_editor = partite_df_editor.columns
        
        # Modo Avanzato: (Partita A3/MRN E Contenitore sono presenti E sono diversi)
        is_avanzato = (
            'Contenitore' in cols_editor and 
            'Partita A3/MRN' in cols_editor and
            not partite_df_editor.empty and 
            (partite_df_editor['Partita A3/MRN'] != partite_df_editor['Contenitore']).any()
        )

        if is_avanzato:
             # MODO AVANZATO (MRN)
             rename_map = {
                'Partita A3/MRN': 'nome', 
                'Peso lordo': 'peso', 
                'Colli': 'colli',
                'Contenitore': 'Contenitore'
             }
             column_list = ['nome', 'colli', 'peso', 'Contenitore']
             
             if 'MRN-S' in cols_editor:
                rename_map['MRN-S'] = 'MRN-S'
                column_list.append('MRN-S')

             partite_df_solver = partite_df_editor.rename(columns=rename_map)[column_list].copy()
             report_msg = "Allocazione completata con criterio **Avanzato (MRN)**."

        elif 'Partita A3/MRN' in cols_editor:
             # MODO CLASSICO (Container)
             rename_map = {
                'Partita A3/MRN': 'nome', 
                'Peso lordo': 'peso', 
                'Colli': 'colli',
             }
             partite_df_solver = partite_df_editor.rename(columns=rename_map).copy()
             partite_df_solver['Contenitore'] = partite_df_solver['nome'] 
             partite_df_solver['MRN-S'] = None
             report_msg = "Allocazione completata con criterio **Classico (Container)**."
        
        else:
            return "Errore: Dati A3 non validi. Colonne 'Partita A3/MRN' non trovata.", None, None, None

        
        # Pulizia valori (comune a entrambi i percorsi)
        partite_df_solver['nome'] = partite_df_solver['nome'].astype(str).str.strip().str.upper()
        partite_df_solver['Contenitore'] = partite_df_solver['Contenitore'].astype(str).str.strip().str.upper()
        partite_df_solver['colli'] = pd.to_numeric(partite_df_solver['colli'], errors='coerce')
        partite_df_solver['peso'] = pd.to_numeric(partite_df_solver['peso'], errors='coerce')
        if 'MRN-S' in partite_df_solver.columns:
            partite_df_solver['MRN-S'] = partite_df_solver['MRN-S'].astype(str).str.strip()

        # Filtra righe non valide
        partite_df_solver = partite_df_solver.dropna(subset=['nome', 'colli', 'peso', 'Contenitore'])
        partite_df_solver = partite_df_solver[
            (partite_df_solver['colli'] > 0) | (partite_df_solver['peso'] > 0)
        ]
        
        if 'MRN-S' not in partite_df_solver.columns:
            partite_df_solver['MRN-S'] = None
        
        if partite_df_solver.empty:
            return "Errore: Nessuna riga A3 valida trovata nei dati (colli/peso > 0).", None, None, None
            
    except Exception as e:
        return f"Errore during l'analisi e preparazione dei dati A3: {e}", None, None, None


    # 3. Flusso di Elaborazione UNIFICATO (Sempre SolverA3)
    try:
        # Esegui il SolverA3 (garantisce la quadratura)
        solver = SolverA3(voci_df_solver, partite_df_solver) 
        griglia_colli, griglia_peso = solver.risolvi()

        # Popola lo stato di sessione con i risultati
        voci_att = pd.DataFrame({
            "Colli Allocati": griglia_colli.sum(axis=1),
            "Peso Allocato": griglia_peso.sum(axis=1),
            "Colli Attesi": solver.voci["colli"],
            "Peso Atteso": solver.voci["peso"]
        })
        part_att = pd.DataFrame({
            "Colli Allocati": griglia_colli.sum(axis=0),
            "Peso Allocato": griglia_peso.sum(axis=0),
            "Colli Attesi": solver.partite["colli"],
            "Peso Atteso": solver.partite["peso"]
        })
        
        st.session_state.risultati = {
            "griglia_colli": griglia_colli,
            "griglia_peso": griglia_peso,
            "voci_attuali": voci_att,
            "partite_attuali": part_att
        }
        st.session_state.solver = solver 
        
        # Salva il messaggio di successo nello stato
        st.session_state.report_message = report_msg 

        # Ritorniamo sempre 'singolo_h1' per attivare la visualizzazione della griglia
        return report_msg, voci_df_solver.copy(), None, 'singolo_h1'
    
    except Exception as e:
        return f"Errore critico during il calcolo SolverA3: {e}", None, None, None


# --- CONFIGURAZIONE BASE ---
st.set_page_config(
    layout="wide",
    page_title="Easy M2 Solver",
    page_icon="file_ico.png", 
    initial_sidebar_state="expanded"
)

# Applica gli stili (importato da styles.py)
apply_custom_css()

# --- LOGO IN ALTO A SINISTRA ---
BASE_DIR = os.path.dirname(__file__)
# CORREZIONE: Il file fornito è .jpg, non .png
LOGO_FILENAME = "LOGO_EASYM2.png" 
LOGO_PATH = os.path.join(BASE_DIR, LOGO_FILENAME)
mime_type = "image/jpeg" # CORREZIONE: Mime type per jpg

img_tag = '<span style="font-size:2rem;">📦</span>'
try:
    with open(LOGO_PATH, "rb") as image_file:
        LOGO_BASE64_STRING = base64.b64encode(image_file.read()).decode()
        img_tag = f'<img src="data:{mime_type};base64,{LOGO_BASE64_STRING}" style="height:auto; max-height:80px; width:auto;">'
except FileNotFoundError:
    pass

st.markdown(
    f"""
    <div id="logo-container">
        {img_tag}
    </div>
    """,
    unsafe_allow_html=True
)

# --- LOAD TEMPLATE FILE ---
TEMPLATE_FILENAME = "EASYM2_A3_TEMPLATE.xlsx"
TEMPLATE_PATH = os.path.join(BASE_DIR, TEMPLATE_FILENAME)
try:
    with open(TEMPLATE_PATH, "rb") as f:
        TEMPLATE_BYTES = f.read()
except FileNotFoundError:
    TEMPLATE_BYTES = None 

# --- SESSION STATE ---
# Standardizza i dati di default per matchare le colonne caricate
default_voci = pd.DataFrame(
    [{"Voce Doganale": "TARIC (Esempio)", "Colli": 100, "Peso lordo": 1000.0}]
)
default_partite = pd.DataFrame(
    [{"Partita A3/MRN": "CONT1 (Esempio)", "Colli": 100, "Peso lordo": 1000.0, "Contenitore": "CONT1 (Esempio)"}]
)

if "voci_data_source" not in st.session_state:
    st.session_state.voci_data_source = default_voci.copy()
if "partite_data_source" not in st.session_state:
    st.session_state.partite_data_source = default_partite.copy()
    
if "risultati" not in st.session_state:
    st.session_state.risultati = None
if "active_tab_key" not in st.session_state:
    st.session_state.active_tab_key = 0

def run_js_tab_switch(tab_index):
    """Esegue JavaScript per simulare il click sul tab corretto."""
    js_code = f"""
        <script>
            var tabs = window.parent.document.querySelectorAll('[data-testid="stTabs"] button');
            if (tabs.length > {tab_index}) {{
                tabs[{tab_index}].click();
            }}
        </script>
    """
    st.components.v1.html(js_code, height=0)


# --- LAYOUT PRINCIPALE ---
col_left, col_right = st.columns([1.2, 1.8], gap="medium")

# --- COLONNA SINISTRA (INPUT) --------------------------------------------------------
with col_left:
    st.subheader("✏️ Dati di input")
    
    tab_voci, tab_a3 = st.tabs(["Voci Doganali", "Partite A3"])
    
    # --- VOCI DOGANALI ---
    with tab_voci:
        c1, c2 = st.columns([1, 2]) 
        with c1:
            pdf = st.file_uploader("Carica Bolla Doganale (PDF)", type="pdf", key="pdf_bolla")
            if pdf:
                with st.spinner("Estrazione dal PDF..."):
                    
                    # MODIFICA: la funzione ora ritorna solo 1 df
                    voci_df = estrai_dati_bolla_reale(pdf) 
                    
                    if not voci_df.empty:
                        
                        # Mappa 'Voce' -> 'Voce Doganale' e altri
                        vmap_pdf = {}
                        for c in voci_df.columns:
                            cl = str(c).strip().lower()
                            if ("voce" in cl) or ("taric" in cl):
                                vmap_pdf[c] = "Voce Doganale"
                            if "colli" in cl:
                                vmap_pdf[c] = "Colli"
                            if "peso" in cl:
                                vmap_pdf[c] = "Peso lordo"
                        voci_df_mapped = voci_df.rename(columns=vmap_pdf)

                        st.session_state.voci_data_source = voci_df_mapped.copy() 
                        
                        if 'editor_voci' in st.session_state:
                            del st.session_state.editor_voci
                        
                        st.success(f"✅ {len(voci_df)} voci estratte.")
                        run_js_tab_switch(1) 
                    else:
                        st.warning("Nessuna voce trovata nel PDF.")
        with c2:
            st.caption("Verifica e modifica i dati estratti:")
            
            voci_data_edited = st.data_editor(
                st.session_state.voci_data_source,
                key="editor_voci", 
                num_rows="dynamic",
                height=240,
                column_config={
                    "Voce Doganale": st.column_config.TextColumn(width=200), # Larghezza fissa in px
                    "Colli": st.column_config.NumberColumn(width=80, format="%d"),
                    "Peso lordo": st.column_config.NumberColumn(width=100, format="%.3f")
                }
            )
            st.session_state.voci_final_data = voci_data_edited

    # --- PARTITE A3 ---
    with tab_a3:
        c1, c2 = st.columns([1, 2])
        with c1:
            excel_a3_file = st.file_uploader("Carica A3 (Excel/CSV)", type=["xlsx", "xls", "csv"], key="excel_a3")
            
            if TEMPLATE_BYTES:
                st.download_button(
                    label="📥 Scarica Template A3",
                    data=TEMPLATE_BYTES,
                    file_name="EASYM2_A3_TEMPLATE.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    width="stretch", 
                    type="secondary",
                    key="download_template_a3"
                )
            else:
                if 'TEMPLATE_BYTES' in locals():
                    st.warning("File template non trovato.")

            if excel_a3_file:
                df_in = read_excel_or_csv(excel_a3_file, just_read=False) 
                if not df_in.empty:
                    df3 = select_three_columns(df_in) # Usa il RICONOSCIMENTO AUTOMATICO
                    if not df3.empty:
                         st.session_state.partite_data_source = df3.copy()
                         
                         if 'editor_partite' in st.session_state:
                             del st.session_state.editor_partite
                             
                         st.success(f"✅ {len(df3)} partite importate.")
                             
        with c2:
            st.caption("Controlla/modifica i dati caricati:")

            partite_cols = st.session_state.partite_data_source.columns
            # Definiamo la config in modo più robusto
            partite_config = {
                "Partita A3/MRN": st.column_config.TextColumn(width=150), # Larghezza fissa in px
                "Colli": st.column_config.NumberColumn(width=62, format="%d"),
                "Peso lordo": st.column_config.NumberColumn(width=100, format="%.3f"),
            }
            if "Contenitore" in partite_cols:
                partite_config["Contenitore"] = st.column_config.TextColumn(width=110) # Larghezza fissa in px
            if "MRN-S" in partite_cols:
                partite_config["MRN-S"] = st.column_config.NumberColumn(
                    width=80, format="%d"
                ) # Larghezza fissa in px
            
            partite_data_edited = st.data_editor(
                st.session_state.partite_data_source,
                key="editor_partite",
                num_rows="dynamic",
                height=240,
                column_config=partite_config 
            )
            st.session_state.partite_final_data = partite_data_edited

    # --- AREA DI VERIFICA E CALCOLO (PRE-FLIGHT CHECK) ---
    st.markdown("---") # Separatore visivo
    st.caption("VERIFICA TOTALI (H1 vs A3)")
    
    try:
        voci_data = st.session_state.get('voci_final_data', default_voci)
        partite_data = st.session_state.get('partite_final_data', default_partite)
        
        if not voci_data.empty and 'Colli' in voci_data.columns and 'Peso lordo' in voci_data.columns:
            voci_colli_tot = pd.to_numeric(voci_data['Colli'], errors='coerce').sum()
            voci_peso_tot = pd.to_numeric(voci_data['Peso lordo'], errors='coerce').sum()
        else:
            voci_colli_tot = 0.0
            voci_peso_tot = 0.0

        if not partite_data.empty and 'Colli' in partite_data.columns and 'Peso lordo' in partite_data.columns:
            part_colli_tot = pd.to_numeric(partite_data['Colli'], errors='coerce').sum()
            part_peso_tot = pd.to_numeric(partite_data['Peso lordo'], errors='coerce').sum()
        else:
            part_colli_tot = 0.0
            part_peso_tot = 0.0

        diff_colli = round(voci_colli_tot - part_colli_tot, 0)
        diff_peso = round(voci_peso_tot - part_peso_tot, 3) 

        is_match_colli = (diff_colli == 0)
        is_match_peso = (diff_peso == 0) 
        
        totals_are_zero = (round(voci_colli_tot, 0) == 0 and round(voci_peso_tot, 3) == 0)
        
        if is_match_colli and is_match_peso and not totals_are_zero:
             is_disabled = False
        else:
             is_disabled = True
        
        colli_icon = "✅" if is_match_colli else "❌"
        peso_icon = "✅" if is_match_peso else "❌"

    except Exception as e: 
        is_disabled = True
        diff_colli = 0.0
        diff_peso = 0.0
        is_match_colli = False
        is_match_peso = False
        totals_are_zero = True 
        colli_icon = "❌" 
        peso_icon = "❌"
        st.error(f"Errore nella verifica: {e}") 

    
    # --- Interfaccia di verifica con 3 colonne ---
    check_col1, check_col2, check_col3 = st.columns([0.8, 1, 1])

    with check_col1:
        st.metric(
            label=f"Differenza Colli {colli_icon}", 
            value=f"{diff_colli:,.0f}",
            delta_color="off" 
        )

    with check_col2:
        st.metric(
            label=f"Differenza Pesi (kg) {peso_icon}",
            value=f"{diff_peso:,.3f}", 
            delta_color="off" 
        )

    with check_col3:
        st.markdown("<div style='height: 2.2rem;'></div>", unsafe_allow_html=True) 
        calcola = st.button(
            "⚙️ Calcola M2", 
            type="primary", 
            width="stretch", 
            key="main_calcola_m2",
            disabled=is_disabled 
        )
    
    if is_disabled:
        if totals_are_zero and is_match_colli and is_match_peso:
            st.info("Carica i dati o inserisci valori per abilitare il calcolo.")
        else:
            st.warning("⚠️ I totali non coincidono. Correggi i dati negli editor per abilitare il calcolo.")
    
# --- COLONNA DESTRA (RISULTATI) ---------------------------------------------
with col_right:
    st.subheader("🚀 Risultati in tempo reale")

    # --- LOGICA DI CONTROLLO UNIFICATA E CALCOLO ---
    if calcola: 
        
        with st.spinner("Avvio Calcolo..."):
            
            report_message, result_df_new, residui_new, processing_option = run_processing()
            
            if processing_option != 'singolo_h1':
                st.error(report_message)
                st.session_state.risultati = None
            
            elif report_message.startswith("Errore"):
                st.error(report_message)
                st.session_state.risultati = None
            
            else:
                pass

    ris = st.session_state.risultati
    
    if ris is None:
        st.info("Carica i dati e premi «Calcola M2» nella colonna di sinistra.")
        
    # --- VISUALIZZAZIONE RISULTATO UNIFICATO (Sempre Griglia SolverA3) ---
    elif ris is not None:
        
        # 1. Messaggio di Contesto (SOPRA)
        if "report_message" in st.session_state:
            st.info(st.session_state.report_message)
        
        diff_colli = abs(ris["voci_attuali"]["Colli Attesi"] - ris["voci_attuali"]["Colli Allocati"]).sum()
        diff_pesi = abs(ris["voci_attuali"]["Peso Atteso"] - ris["voci_attuali"]["Peso Allocato"]).sum() 
        
        df_export_long = prepare_data_entry_export(
            ris["griglia_colli"], 
            ris["griglia_peso"],
            st.session_state.solver.partite 
        )

        # 2. La Griglia (CENTRO)
        st.markdown("""
            <style>
            div[data-testid="stDataFrame"] {
                margin-bottom: 0px !important;
            }
            </style>
        """, unsafe_allow_html=True)
        
        st.dataframe(
            df_export_long, 
            width="stretch", 
            hide_index=True
        )
        
        # 3. Blocco Azioni e Conferma (SOTTO)
        
        # Messaggio Quadratura
        if diff_colli < 1 and diff_pesi < 0.01: 
             quad_msg = f"🎯 Quadratura perfetta!"
             msg_color = "#2e7d32" 
        else:
             quad_msg = f"⚠️ Differenze residue – Colli: {diff_colli:.0f}, Pesi: {diff_pesi:.3f})"
             msg_color = "#c62828"
        
        st.markdown("<hr style='margin: 0.5rem 0rem;'>", unsafe_allow_html=True)
        
        col_conf, col_lab, col_pdf, col_xls = st.columns([2.2, 0.8, 0.5, 0.5], vertical_alignment="center") 
        
        with col_conf:
            st.markdown(f'<span style="font-size: 0.95rem; font-weight: 600; color: {msg_color};">{quad_msg}</span>', unsafe_allow_html=True)
        
        with col_lab:
            st.markdown('<span style="font-weight: 600; text-align: right; display: block; margin-right: 10px;">SCARICA:</span>', unsafe_allow_html=True)
        
        with col_pdf:
            pdf_output = create_pdf_from_df(df_export_long)
            st.download_button(
                label="PDF", 
                data=pdf_output, 
                file_name="easy_m2_pdf.pdf", 
                type="secondary", 
                key="dl_pdf",
                width="stretch" 
            )
        
        with col_xls:
            excel_data = io.BytesIO()
            with pd.ExcelWriter(excel_data, engine='xlsxwriter') as writer:
                 df_export_long.to_excel(writer, index=False, sheet_name='Data Entry M2')
                 
                 # 1. Ottieni il foglio di lavoro
                 worksheet = writer.sheets['Data Entry M2']
                 
                 # 2. Itera sulle colonne e imposta la larghezza
                 for i, col in enumerate(df_export_long.columns):
                     # Trova la larghezza massima
                     max_len = max(
                         df_export_long[col].astype(str).map(len).max(), # Larghezza dati
                         len(str(col)) # Larghezza intestazione
                     )
                     # Imposta la larghezza della colonna (con un po' di padding)
                     worksheet.set_column(i, i, max_len + 2)
                     
            excel_data.seek(0)
            
            st.download_button(
                label="EXCEL", 
                data=excel_data, 
                file_name="easy_m2_excel.xlsx", 
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
                type="secondary", 
                key="dl_excel",
                width="stretch" 
            )