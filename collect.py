import requests
import pandas as pd
from datetime import datetime
import os

# Configuration des APIs
TIMETABLE_API_BASE_URL = "https://prim.iledefrance-mobilites.fr/marketplace/estimated-timetable"
PERTURBATION_API_BASE_URL = "https://prim.iledefrance-mobilites.fr/marketplace/general-message"
API_KEY = "bCzqLlT7ohyMDQD5wVi1Pyn1aNUBp6tI"

# Fichier contenant les identifiants des lignes (LineRef)
UNIQUE_VEHICLE_MODES_FILE = "unique_vehicle_modes.csv"

# Dossier de stockage des données
OUTPUT_FOLDER = ""
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Charger les identifiants des lignes (LineRef) depuis un fichier
def load_valid_line_refs():
    if os.path.exists(UNIQUE_VEHICLE_MODES_FILE):
        df = pd.read_csv(UNIQUE_VEHICLE_MODES_FILE)
        return df["LineRef"].dropna().tolist()
    else:
        print(f"Erreur : Le fichier {UNIQUE_VEHICLE_MODES_FILE} est introuvable.")
        return []

# Requête à l'API des perturbations
def fetch_and_save_perturbations(line_refs):
    headers = {"apikey": API_KEY}
    perturbations = []

    for line_ref in line_refs:
        print(f"Requête API Perturbations avec LineRef : {line_ref}")  # Print de LineRef
        params = {"LineRef": line_ref}

        response = requests.get(PERTURBATION_API_BASE_URL, headers=headers, params=params)

        if response.status_code == 200:
            data = response.json()
            delivery = data.get("Siri", {}).get("ServiceDelivery", {}).get("GeneralMessageDelivery", [])
            for message in delivery:
                info_message = message.get("InfoMessage", [])
                for info in info_message:
                    content = info.get("Content", {}).get("Message", [])
                    for msg in content:
                        perturbations.append({
                            "Timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            "LineRef": line_ref,
                            "Message": msg.get("MessageText", {}).get("value", "Aucune perturbation"),
                        })
        else:
            print(f"Erreur API Perturbations (LineRef {line_ref}) : {response.status_code} - {response.text}")

    # Enregistrer les perturbations dans un fichier CSV
    df = pd.DataFrame(perturbations)
    filename = f"{OUTPUT_FOLDER}/perturbations_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.csv"
    df.to_csv(filename, index=False)
    print(f"Perturbations enregistrées dans : {filename}")

# Requête à l'API des horaires
def fetch_and_save_timetables(line_refs):
    headers = {"apikey": API_KEY}
    timetables = []

    for line_ref in line_refs:
        params = {"LineRef": line_ref}
        print(f"Requête API Timetable avec LineRef : {line_ref}")  # Print de LineRef

        response = requests.get(TIMETABLE_API_BASE_URL, headers=headers, params=params)

        if response.status_code == 200:
            data = response.json()
            delivery = data.get("Siri", {}).get("ServiceDelivery", {}).get("EstimatedTimetableDelivery", [])
            for frame in delivery:
                for journey in frame.get("EstimatedJourneyVersionFrame", []):
                    for vehicle in journey.get("EstimatedVehicleJourney", []):
                        calls = vehicle.get("EstimatedCalls", {}).get("EstimatedCall", [])
                        destination = vehicle.get("DestinationName", [{}])[0].get("value", "Inconnue")
                        for call in calls:
                            arrival_time = call.get("ExpectedArrivalTime", None)
                            timetables.append({
                                "Timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                "LineRef": line_ref,
                                "StopPointRef": call.get("StopPointRef", {}).get("value", ""),
                                "ExpectedArrivalTime": arrival_time,
                                "Destination": destination,
                            })
        else:
            print(f"Erreur API Timetable (LineRef {line_ref}) : {response.status_code} - {response.text}")

    # Enregistrer les horaires dans un fichier CSV
    df = pd.DataFrame(timetables)
    filename = f"{OUTPUT_FOLDER}/timetables_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.csv"
    df.to_csv(filename, index=False)
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

# Exécuter le script
if __name__ == "__main__":
    main()
