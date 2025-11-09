# core_logic.py

import pandas as pd
import numpy as np
import re
import pdfplumber

# --- MOTORE DI SOLVING AUTOMATICO (Logica Sequenziale a Cascata) ---
class SolverA3:
    """
    Logica di solving Riscritte.
    Implementa un'allocazione "a cascata" (greedy sequential fill)
    basata sulla logica di business:
    
    1. Prende la Voce H1 n.1 (con X colli e Y peso).
    2. La riempie usando la Partita A3 n.1 (con A colli e B peso).
    3. Alloca Colli e Peso come due serbatoi indipendenti.
    4. Continua con le Partite A3 n.2, n.3... finché la Voce H1 n.1 è piena.
    5. Passa alla Voce H1 n.2 e ricomincia con le A3 rimanenti.
    
    Questo rispetta i limiti massimi di colli E peso di entrambe le parti.
    """
    def __init__(self, voci, partite):
        self.voci = voci.reset_index(drop=True).copy()
        self.partite = partite.reset_index(drop=True).copy()

        # Tabelle di allocazione iniziali
        self.griglia_colli = pd.DataFrame(
            0.0, index=self.voci["nome"], columns=self.partite["nome"]
        )
        self.griglia_peso = pd.DataFrame(
            0.0, index=self.voci["nome"], columns=self.partite["nome"]
        )

        # Traccia la disponibilità rimanente delle Partite A3 (colonne)
        # Usiamo .to_dict() per un accesso più rapido
        self.partite_colli_disponibili = self.partite.set_index('nome')['colli'].to_dict()
        self.partite_peso_disponibili = self.partite.set_index('nome')['peso'].to_dict()
        
    def risolvi(self):
        
        # Loop 1: Itera su ogni VOCE H1 (Riga) in ordine
        for voce_idx in self.voci.index:
            voce_nome = self.voci.loc[voce_idx, "nome"]
            
            # Usiamo round() per sicurezza con i float
            colli_necessari_voce = round(self.voci.loc[voce_idx, "colli"], 0)
            peso_necessario_voce = round(self.voci.loc[voce_idx, "peso"], 3)

            # Se questa voce H1 non ha bisogno di nulla, salta
            if colli_necessari_voce <= 0 and peso_necessario_voce <= 0.000:
                continue
            
            # Loop 2: Itera su ogni PARTITA A3 (Colonna) per riempire la Voce H1
            for partita_idx in self.partite.index:
                partita_nome = self.partite.loc[partita_idx, "nome"]
                
                # --- 1. Allocazione COLLI (Serbatoio 1) ---
                colli_disponibili_partita = round(self.partite_colli_disponibili.get(partita_nome, 0), 0)
                
                if colli_necessari_voce > 0 and colli_disponibili_partita > 0:
                    colli_da_allocare = min(colli_necessari_voce, colli_disponibili_partita)
                    
                    self.griglia_colli.loc[voce_nome, partita_nome] += colli_da_allocare
                    
                    # Aggiorna i totali rimanenti
                    self.partite_colli_disponibili[partita_nome] -= colli_da_allocare
                    colli_necessari_voce -= colli_da_allocare
                
                # --- 2. Allocazione PESO (Serbatoio 2) ---
                peso_disponibile_partita = round(self.partite_peso_disponibili.get(partita_nome, 0), 3)

                if peso_necessario_voce > 0 and peso_disponibile_partita > 0:
                    peso_da_allocare = min(peso_necessario_voce, peso_disponibile_partita)
                    
                    # Arrotondamento a 3 decimali
                    peso_da_allocare = round(peso_da_allocare, 3)
                    
                    # Check di sicurezza per non allocare più del dovuto (a causa di errori float)
                    if peso_da_allocare > peso_necessario_voce:
                         peso_da_allocare = peso_necessario_voce
                    if peso_da_allocare > peso_disponibile_partita:
                         peso_da_allocare = peso_disponibile_partita

                    self.griglia_peso.loc[voce_nome, partita_nome] += peso_da_allocare
                    
                    # Aggiorna i totali rimanenti
                    self.partite_peso_disponibili[partita_nome] -= peso_da_allocare
                    peso_necessario_voce -= peso_da_allocare
                    
                    # Riarrotonda i residui per evitare errori di precisione float
                    peso_necessario_voce = round(peso_necessario_voce, 3)
                    self.partite_peso_disponibili[partita_nome] = round(self.partite_peso_disponibili[partita_nome], 3)

                # --- 3. Controllo Uscita ---
                # Se questa Voce H1 è piena, smetti di cercare nelle Partite A3
                # e passa alla prossima Voce H1.
                if colli_necessari_voce <= 0 and peso_necessario_voce <= 0.000:
                    break
            
            # (Fine loop partite)
        # (Fine loop voci)
        
        # Pulisci i colli (devono essere interi)
        self.griglia_colli = self.griglia_colli.round(0).astype(int)
        
        return self.griglia_colli, self.griglia_peso


# --- Funzioni di estrazione (Attive) ---

def _pulizia_peso_globale(series_pesi):
    """
    Logica di pulizia che gestisce formati misti:
    - 10.580,00 (punto migliaia, virgola decimale) -> 10580.00
    - 1920.60   (punto decimale) -> 1920.60
    - 8'170.80  (apostrofo migliaia, punto decimale) -> 8170.80
    """
    if not isinstance(series_pesi, pd.Series):
        series_pesi = pd.Series(series_pesi)
        
    # Converte tutto in stringa per sicurezza
    testo_series = series_pesi.astype(str)
    
    # Rimuovi apostrofi (es. 8'170.80 -> 8170.80)
    testo_pulito = testo_series.str.replace("'", "", regex=False)
    
    # Controlla se contiene una virgola (formato europeo 10.580,00)
    # usiamo una copia per evitare warning di pandas
    testo_pulito_copia = testo_pulito.copy()
    contiene_virgola = testo_pulito.str.contains(",", na=False)
    
    # Se contiene una virgola, rimuovi i punti (migliaia) e sostituisci la virgola
    testo_pulito_copia[contiene_virgola] = testo_pulito[contiene_virgola].str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    
    # Se NON contiene una virgola, è formato americano/ISO (1920.60), non fare nulla.
    
    # Converti in numero
    return pd.to_numeric(testo_pulito_copia, errors='coerce')


def estrai_dati_bolla_reale(file_caricato):
    """
    Estrae i dati delle Voci Doganali da un PDF.
    Restituisce solo il DataFrame delle voci.
    """
    voci_list = []
    testo_completo = ""
    try:
        with pdfplumber.open(file_caricato) as pdf:
            for pagina in pdf.pages:
                testo_completo += pagina.extract_text(x_tolerance=2, y_tolerance=2) + "\n"
        
        pattern_splitter = re.compile(r"Sing\.\s+\d+\s+Reg\.\s+40\s+00", re.IGNORECASE)
        pattern_colli = re.compile(r"Colli\s+PK\s+(\d+)", re.IGNORECASE)
        pattern_peso = re.compile(r"P\.lordo\D+([\d'.,]+)", re.IGNORECASE)
        pattern_taric = re.compile(r"Taric\D+(\d+)", re.IGNORECASE)

        blocchi_articolo = pattern_splitter.split(testo_completo)

        if len(blocchi_articolo) < 2:
            # Nessun blocco articolo trovato
            return pd.DataFrame() 

        for i, blocco_testo in enumerate(blocchi_articolo[1:]):
            match_colli = pattern_colli.search(blocco_testo)
            match_peso = pattern_peso.search(blocco_testo)
            match_taric = pattern_taric.search(blocco_testo)
            colli = match_colli.group(1) if match_colli else "0"
            peso = match_peso.group(1) if match_peso else "0"
            desc = match_taric.group(1) if match_taric else f"Taric Sconosciuto {i+1}"
            voci_list.append({'Voce': desc, 'Colli Totali': colli, 'Peso Totale': peso})
        
        voci_estratte_df = pd.DataFrame(voci_list)
        
        # Pulizia Tipi di Dati
        voci_estratte_df['Colli Totali'] = pd.to_numeric(
            voci_estratte_df['Colli Totali'].astype(str).str.replace("'", "", regex=False), 
            errors='coerce'
        ).fillna(0).astype(int)
        
        voci_estratte_df['Peso Totale'] = _pulizia_peso_globale(voci_estratte_df['Peso Totale']).fillna(0.0)
        
        return voci_estratte_df
        
    except Exception:
        # Errore durante l'estrazione
        return pd.DataFrame()