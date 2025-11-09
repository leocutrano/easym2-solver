# styles.py

import streamlit as st
import pandas as pd
from fpdf import FPDF, XPos, YPos
import io
import re 
import numpy as np 
import os 

# ======================================================================
# FUNZIONE CSS PRINCIPALE
# ======================================================================

def apply_custom_css():
    """Inietta il CSS e gli stili personalizzati nella pagina."""
    # Il tuo codice CSS originale è qui
    custom_css = """
    <style>
    
    /* === CORREZIONI PADDING E LOGO === */
    
    /* 1. Rimuove il padding superiore del contenitore principale */
    div[data-testid="block-container"] {
        padding-top: 1rem !important;
        padding-bottom: 0rem !important; 
    }

    /* 2. Stile per il div del logo (allinea a destra) */
    #logo-container {
        width: 100%; /* Forza il contenitore ad essere a larghezza piena */
        text-align: right;
        margin-top: 0rem;
        margin-bottom: 1rem;
        max-height: 80px; 
    }
    
    /* === CODICE CSS ESISTENTE === */
    
    header[data-testid="stHeader"] { display: none; }
    html, body, [data-testid="stAppViewContainer"], .main {
        height: 100vh;
        max-height: 100vh;
        overflow: hidden;
        margin: 0;
        padding: 0;
    }
    
    .block-container { 
        padding: 0.5rem 1.5rem 1rem 1.5rem !important; 
        max-width: 100%;
        height: calc(100vh - 50px) !important; 
        overflow: hidden;
    }

    .main > div, [data-testid="stAppViewContainer"] > section > div, [data-testid="stColumn"] {
        height: 100% !important; 
        max-height: 100% !important;
        overflow: hidden; 
    }
    
    /* === REGOLE PERFEZIONAMENTO (Sidebar Sinistra) === */
    
    /* Riduce il font-size dei valori st.metric */
    div[data-testid="stMetricValue"] {
        font-size: 1.50rem !important;
    }
    
    /* Riduce lo spazio SOPRA le metriche */
    div[data-testid="stMetric"] {
         margin-top: -0.3rem !important; 
    }
    
    /* === FINE REGOLE PERFEZIONAMENTO === */
    

    .stSuccess, .stWarning, .stInfo {
        margin-top: 0.5rem !important; margin-bottom: 0.5rem !important; 
        padding-top: 0.5rem !important; padding-bottom: 0.5rem !important;
        line-height: 1.2;
    }
    hr { margin-top: 0.5rem !important; margin-bottom: 0.5rem !important; }
    [data-testid="stColumn"] button {
        width: 100%; height: 38px; padding: 0 5px; line-height: 38px; font-size: 0.9rem; 
    }
    
    /* Stile per i pulsanti secondari (PDF, EXCEL, Template) */
    button[kind="secondary"] {
        color: #E57373 !important; /* Rosso chiaro per testo */
        border: 2px solid #E57373 !important; /* Bordo rosso chiaro */
        background-color: transparent !important; 
        font-weight: bold;
    }
    button[kind="secondary"]:hover {
        color: white !important; 
        background-color: #EF5350 !important; /* Rosso leggermente più scuro su hover */
        border-color: #EF5350 !important;
    }

    [data-testid="stFileUploaderDropzone"] button[kind="secondary"] {
        color: #31333F !important; border: 1px solid rgba(49, 51, 63, 0.2) !important; background-color: #F0F2F6 !important; font-weight: normal !important;
    }
    [data-testid="stColumn"] > div > div:has(button[data-testid="stDownloadButton"]) {
        text-align: right !important; display: flex; justify-content: flex-end; 
    }
    #output-grid-container {
        height: calc(100% - 300px) !important; overflow-y: auto !important; max-height: calc(100% - 300px) !important;
    }
    div[data-testid="stDataEditor"] { height: 240px !important; overflow-y: hidden !important; }
    div[data-testid="stVerticalBlock"] { overflow-y: visible; max-height: 100%; }
    
    
    /* === BLOCCO DataEditor CSS === */
    
    /* Regola per le intestazioni (th) */
    div[data-testid="stDataEditor"] th {
        padding: 4px 8px !important;
        white-space: nowrap !important; /* NON ANDARE A CAPO (Come richiesto) */
        text-align: center !important;  /* Centra intestazioni */
        font-size: 0.9rem !important;
    }
    
    /* Regola per le celle (td) */
    div[data-testid="stDataEditor"] td {
        padding: 4px 8px !important;
        white-space: nowrap !important; /* NON ANDARE A CAPO */
        text-align: left !important;    /* Allinea a sinistra il testo (NumberColumn allinea a destra i numeri) */
        font-size: 0.9rem !important;
    }
    
    /* Regola per la griglia di output (stDataFrame) */
    div[data-testid="stDataFrame"] td, div[data-testid="stDataFrame"] th {
        padding: 4px 8px !important; white-space: nowrap !important; text-align: center !important; font-size: 0.9rem !important;
    }
    
    /* === FINE BLOCCO DataEditor CSS === */


    /* === INIZIO NUOVA REGOLA (Corretta) === */
    /* Selettore corretto (stArrowDataframe) e margine ridotto a 0.25rem */
    div[data-testid="stArrowDataframe"] {
        margin-bottom: 0.25rem !important; 
    }
    /* === FINE NUOVA REGOLA === */

    </style>
    """
    st.markdown(custom_css, unsafe_allow_html=True)


# ======================================================================
# FUNZIONI HELPER PER PDF
# ======================================================================

# --- CLASSE PDF HELPER ---
class PDF(FPDF):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logo_path = "LOGO_EASYM2_HOR_1.png" # Assumi che il logo sia nella stessa cartella

    def header(self):
        try:
            # Usiamo un controllo file_exists più robusto
            if self.logo_path and os.path.exists(self.logo_path):
                 self.image(self.logo_path, 10, 8, 33)
        except Exception:
            pass # Non bloccare il PDF se il logo manca
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'Report Allocazione M2', 0, 0, 'C')
        self.ln(20)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Pagina {self.page_no()}', 0, 0, 'C')

    def fancy_table(self, header, data):
        self.set_fill_color(220, 220, 220) # Grigio chiaro per header
        self.set_text_color(0)
        self.set_draw_color(128)
        self.set_line_width(0.3)
        self.set_font('Arial', 'B', 8)
        
        num_cols = len(header)
        if num_cols == 0:
            return 

        # Logica larghezza colonne per il formato "LUNGO"
        total_width = self.w - self.l_margin - self.r_margin
        
        # Header normalizzati per il controllo
        header_norm = [str(h).replace('_', '').upper() for h in header]
        colli_peso_cols = [h for h in header if 'Colli' in str(h) or 'Peso' in str(h)]
        
        # --- INIZIO BLOCCO MODIFICATO ---
        if 'PARTITAA3/MRN' in header_norm and 'MRN-S' in header_norm: # Avanzato completo (6 col)
        # --- FINE BLOCCO MODIFICATO ---
            widths = [
                total_width * 0.20, # Voce Doganale (H1)
                total_width * 0.15, # Contenitore
                total_width * 0.25, # Partita A3/MRN
                total_width * 0.15, # MRN-S
                total_width * 0.10, # Colli Allocati
                total_width * 0.15  # Peso Allocato
            ]
        # --- INIZIO BLOCCO MODIFICATO ---
        elif 'PARTITAA3/MRN' in header_norm: # Avanzato senza MRN-S (5 col)
        # --- FINE BLOCCO MODIFICATO ---
             widths = [
                total_width * 0.25, # Voce Doganale (H1)
                total_width * 0.20, # Contenitore
                total_width * 0.30, # Partita A3/MRN
                total_width * 0.10, # Colli Allocati
                total_width * 0.15  # Peso Allocato
            ]
        elif 'CONTENITORE' in header_norm: # Classico (4 col)
            widths = [
                total_width * 0.30, # Voce Doganale (H1)
                total_width * 0.40, # Contenitore
                total_width * 0.12, # Colli Allocati
                total_width * 0.18  # Peso Allocato
            ]
        else: # Fallback
            col_width = total_width / num_cols
            widths = [col_width] * num_cols

        # Header
        for i, col_name in enumerate(header):
            # Pulisci nomi per PDF
            col_name_clean = str(col_name).replace('_', ' ').replace('H1', '(H1)').replace('MRN S', 'MRN-S')
            self.cell(widths[i], 7, col_name_clean, 1, 0, 'C', 1)
        self.ln()
        
        # Dati
        self.set_font('Arial', '', 8)
        self.set_fill_color(255)
        fill = False
        for row in data:
            for i, item in enumerate(row):
                # Allinea a destra solo colli e peso
                align = 'R' if header[i] in colli_peso_cols else 'L'
                self.cell(widths[i], 6, str(item), 'LR', 0, align, fill)
            self.ln()
            fill = not fill
        self.cell(sum(widths), 0, '', 'T')


def create_pdf_from_df(df_export):
    """Crea un file PDF FPDF dal DataFrame di esportazione (Formato Lungo)."""
    
    # Imposta orientamento a Portrait (Verticale)
    pdf = PDF(orientation='P', unit='mm', format='A4')
    
    pdf.add_page()
    pdf.set_font('Arial', '', 8)
    
    # Prepara dati per la tabella
    # Pulisci i nomi colonna per l'export
    df_export_clean = df_export.copy()
    # Rinomina per un header più pulito nel PDF
    df_export_clean.columns = df_export_clean.columns.str.replace(r'[\(\)]', '', regex=True).str.replace(' ', '_')
    
    header = list(df_export_clean.columns)
    data = df_export_clean.values.tolist()
    
    # Formatta i float nei dati
    formatted_data = []
    for row in data:
        new_row = []
        for item in row:
            if isinstance(item, float):
                # Arrotonda a 3 decimali per coerenza con il solver
                new_row.append(f"{item:.3f}")
            else:
                new_row.append(str(item))
        formatted_data.append(new_row)

    pdf.fancy_table(header, formatted_data)
    
    # Converti 'bytearray' in 'bytes' per st.download_button
    return bytes(pdf.output(dest='S'))

# ======================================================================
# FUNZIONE PREPARAZIONE EXPORT
# ======================================================================

def prepare_data_entry_export(griglia_colli, griglia_peso, partite_df):
    """
    Prepara il DataFrame in formato "lungo", ottimizzato per il data entry.
    Gestisce dinamicamente le colonne (Classico vs Avanzato).
    """
    
    # 1. Determina il modo (Classico vs Avanzato)
    is_avanzato = (partite_df['nome'] != partite_df['Contenitore']).any()
    
    # 2. Imposta il nome della colonna "Partita"
    if is_avanzato:
        # --- INIZIO BLOCCO MODIFICATO ---
        partita_col_name = 'Partita A3/MRN' 
        # --- FINE BLOCCO MODIFICATO ---
    else:
        partita_col_name = 'Contenitore' # Nel modo Classico, 'nome' è il contenitore

    # 3. Mappe (necessarie solo in modo Avanzato)
    if is_avanzato:
        mrn_to_container_map = partite_df.set_index('nome')['Contenitore'].to_dict()
        if 'MRN-S' in partite_df.columns:
            mrn_to_mrns_map = partite_df.set_index('nome')['MRN-S'].to_dict()
        else:
            mrn_to_mrns_map = {} # MRN-S non fornito

    # 4. Resetta indici
    df_c = griglia_colli.reset_index().rename(columns={'nome': 'Voce Doganale (H1)'})
    df_p = griglia_peso.reset_index().rename(columns={'nome': 'Voce Doganale (H1)'})
    
    # 5. Melt usando il nome colonna dinamico
    df_c = df_c.melt(id_vars=['Voce Doganale (H1)'], var_name=partita_col_name, value_name='Colli Allocati')
    df_p = df_p.melt(id_vars=['Voce Doganale (H1)'], var_name=partita_col_name, value_name='Peso Allocato')
    
    # 6. Unisci i dati
    df_merged = pd.merge(df_c, df_p, on=['Voce Doganale (H1)', partita_col_name])
    
    # 7. Filtra righe vuote
    df_merged = df_merged[ (df_merged['Colli Allocati'].abs() > 0.01) | (df_merged['Peso Allocato'].abs() > 0.001) ]

    # 8. Pulisci e formatta i valori
    # Arrotonda a 3 decimali per coerenza con il solver
    df_merged['Peso Allocato'] = df_merged['Peso Allocato'].round(3)
    df_merged['Colli Allocati'] = df_merged['Colli Allocati'].round(0).astype(int)
    
    # 9. Aggiungi colonne extra e definisci l'ordine finale
    if is_avanzato:
        df_merged['Contenitore'] = df_merged[partita_col_name].map(mrn_to_container_map)
        df_merged['MRN-S'] = df_merged[partita_col_name].map(mrn_to_mrns_map)
        
        df_final = df_merged.sort_values(by=['Voce Doganale (H1)', 'Contenitore', partita_col_name]).reset_index(drop=True)
        
        # --- INIZIO BLOCCO MODIFICATO ---
        # Ordine colonne finale Avanzato
        col_order = ['Voce Doganale (H1)', 'Contenitore', 'Partita A3/MRN', 'MRN-S', 'Colli Allocati', 'Peso Allocato']
        # --- FINE BLOCCO MODIFICATO ---
        
        # Rimuovi MRN-S SOLO se la colonna non esiste affatto nel DF finale
        # (non rimuoverla solo perché è vuota)
        if 'MRN-S' not in df_final.columns:
            if 'MRN-S' in col_order: col_order.remove('MRN-S')
            
    else: # Classico
        df_final = df_merged.sort_values(by=['Voce Doganale (H1)', partita_col_name]).reset_index(drop=True)
        # Ordine colonne finale Classico
        col_order = ['Voce Doganale (H1)', 'Contenitore', 'Colli Allocati', 'Peso Allocato']

    # Applica l'ordine colonne
    # Assicura che l'ordine non fallisca se una colonna manca (es. MRN-S in Classico)
    final_col_order = [col for col in col_order if col in df_final.columns]
    df_final = df_final[final_col_order]
    
    return df_final