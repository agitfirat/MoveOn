import requests
import os
import time
import json
from datetime import datetime
import pandas as pd

# Configuration des APIs
TIMETABLE_API_BASE_URL = "https://prim.iledefrance-mobilites.fr/marketplace/estimated-timetable"
PERTURBATION_API_BASE_URL = "https://prim.iledefrance-mobilites.fr/marketplace/general-message"
API_KEY = "bCzqLlT7ohyMDQD5wVi1Pyn1aNUBp6tI"

# Fichier contenant les identifiants des lignes (LineRef)
UNIQUE_VEHICLE_MODES_FILE = "unique_vehicle_modes.csv"

# Dossier de stockage des données
OUTPUT_FOLDER = os.path.dirname(os.path.abspath(__file__))

# Charger les identifiants des lignes (LineRef) depuis un fichier
def load_valid_line_refs():
    if os.path.exists(UNIQUE_VEHICLE_MODES_FILE):
        df = pd.read_csv(UNIQUE_VEHICLE_MODES_FILE)
        return df["LineRef"].dropna().tolist()
    else:
        print(f"Erreur : Le fichier {UNIQUE_VEHICLE_MODES_FILE} est introuvable.")
        return []

# Fonction pour gérer les requêtes avec gestion des erreurs 429
def make_request_with_retry(url, headers, params, max_retries=5, retry_delay=10):
    retries = 0
    while retries < max_retries:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            return response
        elif response.status_code == 429:
            print(f"Erreur 429 : Limite de requêtes atteinte. Nouvelle tentative dans {retry_delay} secondes...")
            time.sleep(retry_delay)
            retries += 1
        else:
            print(f"Erreur lors de la requête : {response.status_code} - {response.text}")
            return response
    print("Échec après plusieurs tentatives.")
    return None

# Requête à l'API des perturbations
def fetch_and_save_perturbations(line_refs):
    headers = {"apikey": API_KEY}
    all_responses = []

    for line_ref in line_refs:
        print(f"Requête API Perturbations avec LineRef : {line_ref}")
        params = {"LineRef": line_ref}

        response = make_request_with_retry(PERTURBATION_API_BASE_URL, headers, params)
        if response and response.status_code == 200:
            all_responses.append(response.json())
        else:
            print(f"Erreur API Perturbations (LineRef {line_ref}) : {response.status_code if response else 'No response'}")

    # Écraser le fichier JSON existant avec les réponses brutes
    filename = os.path.join(OUTPUT_FOLDER, "perturbations.json")
    
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(all_responses, f, indent=4, ensure_ascii=False)

    print(f"Perturbations enregistrées dans : {filename}")

# Requête à l'API des horaires
def fetch_and_save_timetables(line_refs):
    headers = {"apikey": API_KEY}
    all_responses = []

    for line_ref in line_refs:
        print(f"Requête API Timetable avec LineRef : {line_ref}")
        params = {"LineRef": line_ref}

        response = make_request_with_retry(TIMETABLE_API_BASE_URL, headers, params)
        if response and response.status_code == 200:
            all_responses.append(response.json())
        else:
            print(f"Erreur API Timetable (LineRef {line_ref}) : {response.status_code if response else 'No response'}")

    # Écraser le fichier JSON existant avec les réponses brutes
    filename = os.path.join(OUTPUT_FOLDER, "timetables.json")
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(all_responses, f, indent=4, ensure_ascii=False)

    print(f"Horaires enregistrés dans : {filename}")

# Fonction principale
def main():
    # Charger les identifiants valides des lignes
    line_refs = load_valid_line_refs()
    if not line_refs:
        print("Aucun identifiant de ligne valide n'a été trouvé. Arrêt du script.")
        return

    print("Début de la collecte des perturbations...")
    fetch_and_save_perturbations(line_refs)

    print("Début de la collecte des horaires...")
    fetch_and_save_timetables(line_refs)

    print("Collecte terminée avec succès.")

# Exécuter le script
if __name__ == "__main__":
    main()
