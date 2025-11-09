# data_utils.py

import streamlit as st
import pandas as pd
import io
import re
import unicodedata
import chardet # Necessario per la robustezza del CSV
import numpy as np # Necessario per il check float/int

# --- FUNZIONI DI UTILITÀ (PER PULIZIA DATI) ---

def _normalize(s: str) -> str:
    if not isinstance(s, str):
        s = str(s) if s is not None else ""
    s = s.strip().lower()
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    s = re.sub(r'[^a-z0-9 ]+', ' ', s)
    return re.sub(r'\s+', ' ', s)

def extract_m2_classic_data(df_in: pd.DataFrame) -> pd.DataFrame:
    """
    Questa funzione è un fallback per 'select_three_columns'.
    Viene mantenuta ma modificata per restituire i NUOVI nomi di colonna.
    """
    CONTAINER_REGEX = r'^[A-Z]{4}\d{7}$' 
    
    if df_in is None or df_in.empty:
        raise ValueError("Il DataFrame partite è vuoto.")

    # Normalizza nomi colonna
    norm = {c: re.sub(r'\s+', ' ', str(c)).strip().lower() for c in df_in.columns}
    name_col = None
    colli_col = None
    peso_col = None

    # Mappa per nome colonna (cerca le colonne originali: Sigla Container / Colli / Peso Totale)
    for c, n in norm.items():
        if name_col is None and ("sigla" in n and "container" in n):
             name_col = c
        if colli_col is None and ("colli" in n):
             colli_col = c
        if peso_col is None and ("peso" in n):
             peso_col = c
    
    # Tentativo di fallback se la sigla non è esplicita
    if name_col is None:
        for c in df_in.columns:
             sample = df_in[c].dropna().astype(str).str.strip().str.upper().head(25)
             if sample.str.fullmatch(CONTAINER_REGEX).any():
                  name_col = c
                  break

    if name_col is None or colli_col is None or peso_col is None:
        raise KeyError(
            f"Impossibile individuare colonne 'Sigla Container'/'Colli'/'Peso'. "
            f"Colonne disponibili: {list(df_in.columns)}"
        )

    # --- BLOCCO MODIFICATO ---
    # Crea il DataFrame con i NUOVI nomi di colonna
    df = df_in[[name_col, colli_col, peso_col]].copy()
    df.columns = ['Partita A3/MRN', 'Colli', 'Peso lordo'] # NOMI UNIFICATI
    # --- FINE BLOCCO MODIFICATO ---

    # Pulizia valori
    df['Partita A3/MRN'] = df['Partita A3/MRN'].astype(str).str.strip().str.upper()
    df['Colli'] = pd.to_numeric(df['Colli'], errors='coerce')
    df['Peso lordo'] = pd.to_numeric(df['Peso lordo'], errors='coerce')

    # Filtra solo righe con sigla container valida (AAAA9999999)
    df = df[df['Partita A3/MRN'].str.fullmatch(CONTAINER_REGEX, na=False)]

    # Scarta righe non numeriche o non positive
    df = df[(df['Colli'] > 0) & (df['Peso lordo'] > 0)]
    df = df.dropna(subset=['Colli', 'Peso lordo'])

    # Rimuovi duplicati palesi
    df = df.drop_duplicates(subset=['Partita A3/MRN', 'Colli', 'Peso lordo']).reset_index(drop=True)

    if df.empty:
        raise ValueError("Nessuna riga valida dopo la pulizia. Verifica Sigla/Colli/Peso nel file.")
    
    # Aggiungi colonne Contenitore e MRN-S (nullo) per standardizzare
    df['Contenitore'] = df['Partita A3/MRN']
    df['MRN-S'] = None
    return df

def read_excel_or_csv(uploaded_file, just_read=False):
    """
    Legge un file Excel o CSV (M2 o A3) in modo tollerante e multi-formato.
    """
    if uploaded_file is None:
        return pd.DataFrame()

    name = (uploaded_file.name or "").lower()
    uploaded_file.seek(0)
    raw = io.BytesIO(uploaded_file.read())

    # --- Tentativi multipli di lettura ---
    df_raw = pd.DataFrame()
    read_attempts = [
        ("xls", "xlrd"), ("xlsx", "openpyxl"),
        ("xlsb", "pyxlsb"), ("csv", None)
    ]

    for ext, engine in read_attempts:
        try:
            uploaded_file.seek(0)
            raw.seek(0)
            if name.endswith(f".{ext}") or (ext == "csv" and "," in uploaded_file.name):
                if ext == "csv":
                    raw.seek(0)
                    enc = chardet.detect(raw.read())["encoding"] or "latin-1"
                    raw.seek(0)
                    df_raw = pd.read_csv(raw, header=None, sep=None, engine="python", encoding=enc)
                else:
                    df_raw = pd.read_excel(raw, header=None, engine=engine)
                if not df_raw.empty:
                    break
        except Exception:
            continue

    if df_raw.empty and not just_read:
        st.warning("⚠️ Impossibile leggere il file caricato. Verifica il formato (.xls/.xlsx/.csv).")
        return pd.DataFrame()
    
    if df_raw.empty and just_read:
        return pd.DataFrame()

    # --- Individuazione automatica riga di intestazione ---
    header_row = None
    for i, row in df_raw.iterrows():
        row_text = " ".join(str(x).lower() for x in row.values)
        if all(k in row_text for k in ["colli", "peso"]) or "mrn" in row_text:
            header_row = i
            break
    # NOTA: Rimuovendo 'header_row = 0' si risolve il bug dei file senza intestazione
    
    # --- Ricarica il file con header corretto ---
    uploaded_file.seek(0)
    raw2 = io.BytesIO(uploaded_file.read())
    try:
        if name.endswith(".csv"):
            raw2.seek(0)
            enc = chardet.detect(raw2.read())["encoding"] or "latin-1"
            raw2.seek(0)
            df = pd.read_csv(raw2, header=header_row, sep=None, engine="python", encoding=enc)
        elif name.endswith(".xls"):
            df = pd.read_excel(raw2, header=header_row, engine="xlrd")
        else:
            df = pd.read_excel(raw2, header=header_row, engine="openpyxl")
    except Exception as e:
        if not just_read:
             st.error(f"Errore lettura file: {e}")
        return pd.DataFrame()

    df = df.dropna(how="all")
    df.columns = [str(c).strip() for c in df.columns]
    df = df.loc[:, ~df.columns.duplicated()]
    return df

# ======================================================================
# --- INIZIO BLOCCO RICONOSCIMENTO AUTOMATICO ---
# ======================================================================
def select_three_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Riconosce automaticamente le colonne basandosi sul *contenuto*
    e usa le intestazioni solo come fallback.
    Restituisce i nomi delle colonne UNIFICATI (es. 'Colli', 'Peso lordo').
    """
    
    # --- Helper Interni di Riconoscimento ---
    def check_col_content(series, regex_pattern):
        """Verifica se la maggior parte dei dati in una colonna matcha un pattern."""
        sample = series.dropna().astype(str).str.strip().str.upper()
        if sample.empty:
            return False
        sample = sample.head(20)
        match_rate = sample.str.fullmatch(regex_pattern).mean()
        return match_rate > 0.8 

    def is_decimal_col(series):
        """Verifica se la colonna contiene numeri decimali (float)."""
        try:
            s_cleaned = series.astype(str).str.replace(r'^[0-9]{2}[A-Z]{2}.*$', '', regex=True)
            numeric_series = pd.to_numeric(s_cleaned.dropna(), errors='coerce')
            if numeric_series.empty:
                return False
            return (numeric_series % 1).abs().sum() > 0.001
        except Exception:
            return False

    def is_integer_col(series):
        """Verifica se la colonna contiene numeri interi (non float)."""
        try:
            s_cleaned = series.astype(str).str.replace(r'^[0-9]{2}[A-Z]{2}.*$', '', regex=True)
            numeric_series = pd.to_numeric(s_cleaned.dropna(), errors='coerce')
            if numeric_series.empty:
                return False
            return (numeric_series % 1).abs().sum() < 0.001
        except Exception:
            return False

    # Definizioni dei pattern
    MRN_REGEX = r'^\d{2}[A-Z]{2}[A-Z0-9]{12}[A-Z][0-9]$' # Es. 25IT5C7327204662U4
    CONT_REGEX = r'^[A-Z]{4}\d{7}$' # Es. TCKU4536878
    MRN_SPLIT_REGEX = r'^(\d{2}[A-Z]{2}[A-Z0-9]{12}[A-Z][0-9])-(\d+)$'

    mapped = {}
    available_cols = list(df.columns)
    df_copy = df.copy() 

    # --- FASE 1: Riconoscimento basato sul CONTENUTO ---
    
    # 1a. Trova e splitta la colonna combinata MRN/MRN-S
    found_split_mrn = False
    for c in available_cols:
        if check_col_content(df_copy[c], MRN_SPLIT_REGEX):
            # --- RIGA RIMOSSA --- (Problema 4)
            # st.success(f"Rilevato formato MRN-S combinato nella colonna '{c}'.") 
            extracted = df_copy[c].astype(str).str.extract(MRN_SPLIT_REGEX, expand=True)
            
            col_mrn = f"__mrn_split_{c}"
            col_mrns = f"__mrns_split_{c}"
            
            df_copy[col_mrn] = extracted[0]
            df_copy[col_mrns] = extracted[1]
            
            mapped[col_mrn] = "Partita A3/MRN" # NOME UNIFICATO
            mapped[col_mrns] = "MRN-S"
            
            available_cols.remove(c)
            found_split_mrn = True
            break 

    # 1b. Trova Chiavi (MRN e Container)
    if not found_split_mrn: 
        for c in available_cols:
            if check_col_content(df_copy[c], MRN_REGEX):
                mapped[c] = "Partita A3/MRN" # NOME UNIFICATO
                available_cols.remove(c)
                break 
            
    for c in available_cols:
        if check_col_content(df_copy[c], CONT_REGEX):
            if "Partita A3/MRN" in mapped.values():
                mapped[c] = "Contenitore" 
            else:
                mapped[c] = "Partita A3/MRN" # NOME UNIFICATO
            available_cols.remove(c)
            break 

    # 1c. Trova Pesi (Float/Decimali)
    for c in available_cols:
        if is_decimal_col(df_copy[c]):
            mapped[c] = "Peso lordo" # NOME UNIFICATO
            available_cols.remove(c)
            break 

    # 1d. Trova Colli e MRN-S (Entrambi Interi)
    int_cols = []
    for c in available_cols:
        if is_integer_col(df_copy[c]):
            int_cols.append(c)

    if len(int_cols) == 1:
        mapped[int_cols[0]] = "Colli" # NOME UNIFICATO
        available_cols.remove(int_cols[0])
    elif len(int_cols) > 1:
        if 'MRN-S' not in mapped.values():
            means = {c: pd.to_numeric(df_copy[c], errors='coerce').mean() for c in int_cols}
            colli_col = max(means, key=means.get)
            mrns_col = min(means, key=means.get)
            
            mapped[colli_col] = "Colli" # NOME UNIFICATO
            mapped[mrns_col] = "MRN-S"
            available_cols.remove(colli_col)
            available_cols.remove(mrns_col)
        else: 
            mapped[int_cols[0]] = "Colli" # NOME UNIFICATO
            available_cols.remove(int_cols[0])


    # --- FASE 2: Fallback su Intestazioni (per colonne non trovate) ---
    cols_norm = {c: _normalize(c) for c in available_cols} 
        
    for c, n in cols_norm.items():
        if "Partita A3/MRN" not in mapped.values():
            if ("sigla" in n and "container" in n) or ("mrn" in n and "s" not in n):
                mapped[c] = "Partita A3/MRN" # NOME UNIFICATO
                if c in available_cols: available_cols.remove(c)
                continue

        if "Contenitore" not in mapped.values():
             if ("container" in n or "cont" in n) and "sigla" not in n and "tipo" not in n:
                mapped[c] = "Contenitore"
                if c in available_cols: available_cols.remove(c)
                continue
        
        if "Colli" not in mapped.values():
            if "colli" in n:
                mapped[c] = "Colli" # NOME UNIFICATO
                if c in available_cols: available_cols.remove(c)
                continue

        if "Peso lordo" not in mapped.values():
            if "peso" in n and "netto" not in n:
                mapped[c] = "Peso lordo" # NOME UNIFICATO
                if c in available_cols: available_cols.remove(c)
                continue
        
        if "MRN-S" not in mapped.values():
            if n == "mrn s" or n == "mrns":
                mapped[c] = "MRN-S"
                if c in available_cols: available_cols.remove(c)
                continue

    # --- Pulizia Finale ---
    df_sel = df_copy[[c for c in df_copy.columns if c in mapped]].rename(columns=mapped)
    
    if 'Contenitore' not in df_sel.columns and 'Partita A3/MRN' in df_sel.columns:
        if check_col_content(df_sel['Partita A3/MRN'], CONT_REGEX):
             df_sel['Contenitore'] = df_sel['Partita A3/MRN']

    df_sel = df_sel.loc[:, ~df_sel.columns.duplicated()]
    return df_sel
# ======================================================================
# --- FINE BLOCCO RICONOSCIMENTO AUTOMATICO ---
# ======================================================================