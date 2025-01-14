from datetime import datetime, timedelta
import pandas as pd
import requests
import streamlit as st
import base64
from pyproj import Transformer
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import folium_static
import requests

# Onglets
tab1, tab2 = st.tabs(["Prochains Passages", "Plan des Lignes de Métro"])
# Configuration des APIs

with tab1:
    TIMETABLE_API_BASE_URL = "https://prim.iledefrance-mobilites.fr/marketplace/estimated-timetable"
    PERTURBATION_API_BASE_URL = "https://prim.iledefrance-mobilites.fr/marketplace/general-message"
    API_KEY = "bCzqLlT7ohyMDQD5wVi1Pyn1aNUBp6tI"

    # Chemin du fichier des lignes VTC
    UNIQUE_VEHICLE_MODES_FILE = "unique_vehicle_modes.csv"

    # Couleurs des lignes (codes officiels des lignes de métro parisiennes)
    LINE_COLORS = {
        "1": "#FFD700",  # Jaune
        "2": "#0055FF",  # Bleu
        "3": "#968D4F",  # Marron clair
        "3bis": "#82C8E6",  # Bleu clair
        "4": "#BB4D98",  # Violet
        "5": "#FF8031",  # Orange
        "6": "#76C3B3",  # Vert clair
        "7": "#F59EC2",  # Rose
        "7bis": "#82C8E6",  # Bleu clair
        "8": "#D5A6FF",  # Mauve
        "9": "#B6BD00",  # Vert citron
        "10": "#D9B17E",  # Beige
        "11": "#8C6239",  # Marron foncé
        "12": "#008F62",  # Vert forêt
        "13": "#99D4D4",  # Cyan clair
        "14": "#62259D",  # Violet profond
        "A": "#E2231A",  # Rouge
        "B": "#3083DC",  # Bleu royal
        "C": "#F4D743",  # Jaune pâle
        "D": "#008F62",  # Vert forêt
        "E": "#BF6F7B"   # Rose sombre
    }

    # Charger une image en Base64
    def get_base64_image(image_path):
        with open(image_path, "rb") as file:
            data = file.read()
        return base64.b64encode(data).decode()

    # Ajouter une image de fond
    def set_background_image(image_path):
        base64_image = get_base64_image(image_path)
        st.markdown(
            f"""
            <style>
            .stApp {{
                background-image: url("data:image/png;base64,{base64_image}");
                background-size: cover;
                background-position: center;
                background-repeat: no-repeat;
            }}
            h1, h2, h3, .stTitle, .stHeader {{
                background-color: #367A65;
                color: white;
                font-weight: bold;
                text-shadow: none;
                padding: 20px;
                margin-bottom: 20px;
                border-radius: 5px;
                box-shadow: 4px 4px 10px rgba(255, 255, 255, 0.6);
            }}
            .line-color-box {{
                padding: 10px;
                color: white;
                font-weight: bold;
                text-align: center;
                border-radius: 5px;
                margin-bottom: 20px;
            }}
            button[kind="primary"] {{
                background-color: green !important;
                color: white !important;
                border-radius: 5px;
                padding: 10px 20px;
                font-size: 16px;
                font-weight: bold;
                box-shadow: 4px 4px 10px rgba(255, 255, 255, 0.8);
            }}
            .custom-table {{
                border-collapse: collapse;
                width: 100%;
                margin-top: 20px;
            }}
            .custom-table th, .custom-table td {{
                text-align: left;
                padding: 8px;
                border: 1px solid #ddd;
            }}
            .custom-table th {{
                background-color: #f2f2f2;
                color: black;
                font-weight: bold;
            }}
            .custom-table tr:nth-child(even) {{
                background-color: #f9f9f9;
            }}
            .custom-table tr:hover {{
                background-color: #f1f1f1;
            }}
            </style>
            """,
            unsafe_allow_html=True
        )


    # Appliquer l'image de fond
    set_background_image("image_fond.jpeg")

    # Charger le fichier de référencement des gares
    @st.cache_data
    def load_gare_referencement(file_path="gare_referencement.csv"):
        return pd.read_csv(file_path, encoding="utf-8")

    # Charger le fichier des lignes automatiquement
    @st.cache_data
    def load_unique_vehicle_modes(file_path=UNIQUE_VEHICLE_MODES_FILE):
        return pd.read_csv(file_path)

    # Fonction pour requêter l'API des perturbations
    def get_perturbation_status(line_ref):
        headers = {"apikey": API_KEY}
        params = {"LineRef": line_ref}
        response = requests.get(PERTURBATION_API_BASE_URL, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            delivery = data.get("Siri", {}).get("ServiceDelivery", {}).get("GeneralMessageDelivery", [])
            for message in delivery:
                if message.get("InfoMessage", []):  # Si des messages existent
                    return message.get("InfoMessage")[0]["Content"]["Message"][0]["MessageText"]["value"]
            return "Aucune perturbation signalée."
        else:
            st.error(f"Erreur {response.status_code} lors de la requête API des perturbations : {response.text}")
            return None

    # Fonction pour requêter l'API des horaires
    def get_timetable(line_ref):
        headers = {"apikey": API_KEY}
        params = {"LineRef": line_ref}
        response = requests.get(TIMETABLE_API_BASE_URL, headers=headers, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Erreur {response.status_code} lors de la requête API des horaires : {response.text}")
            return None

    # Fonction pour extraire les arrêts avec informations supplémentaires
    def extract_stop_point_info(api_response):
        rows = []
        delivery = api_response.get("Siri", {}).get("ServiceDelivery", {}).get("EstimatedTimetableDelivery", [])
        for frame in delivery:
            for journey in frame.get("EstimatedJourneyVersionFrame", []):
                for vehicle in journey.get("EstimatedVehicleJourney", []):
                    calls = vehicle.get("EstimatedCalls", {}).get("EstimatedCall", [])
                    destination = vehicle.get("DestinationName", [{}])[0].get("value", "Destination inconnue")
                    for call in calls:
                        arrival_time = call.get("ExpectedArrivalTime", None)
                        if arrival_time:
                            arrival_time = datetime.fromisoformat(arrival_time.replace("Z", ""))
                            local_time = (arrival_time + timedelta(hours=1)).strftime("%H:%M")
                        else:
                            local_time = "Heure inconnue"
                        
                        rows.append({
                            "StopPointRef": call.get("StopPointRef", {}).get("value"),
                            "Prochain Passage": local_time,
                            "Destination": destination,
                        })
        return pd.DataFrame(rows)

    # Fonction pour récupérer la qualité de l'air avec OpenWeatherMap
    def get_air_quality_by_coords(lat, lon):
        api_key = "8d91e66b8be0b88976529ae0b531c6b0"  # Remplacez par votre propre clé API
        url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={api_key}"
        
        response = requests.get(url)
        
        if response.status_code == 200:
            return response.json()  # Données au format JSON
        else:
            return None
    # Fonction pour déterminer la couleur selon l'index AQI
    def get_color_for_aqi(aqi):
        if aqi == 1:
            return "#00FF00"  # Vert
        elif aqi == 2:
            return "#FFFF00"  # Jaune
        elif aqi == 3:
            return "#FFA500"  # Orange
        elif aqi == 4:
            return "#FF4500"  # Rouge
        elif aqi == 5:
            return "#8B0000"  # Rouge foncé
        else:
            return "#800080"  # Pourpre



    # Fonction pour afficher les résultats de la qualité de l'air avec couleur
    def display_air_quality(data):
        if data:
            aqi = data['list'][0]['main']['aqi']
            components = data['list'][0]['components']
            
            # Définir le texte de l'indice de qualité de l'air (AQI)
            if aqi == 1:
                aqi_desc = "Qualité de l'air de la gare de départ : Bonne qualité"
            elif aqi == 2:
                aqi_desc = "Qualité de l'air de la gare de départ : modérée"
            elif aqi == 3:
                aqi_desc = "Qualité de l'air de la gare de départ : dégradée"
            elif aqi == 4:
                aqi_desc = "Qualité de l'air de la gare de départ : très mauvaise"
            elif aqi == 5:
                aqi_desc = "Qualité de l'air de la gare de départ : dangereuse"
            else:
                aqi_desc = "Qualité de l'air de la gare de départ : très dangereuse"
            
            # Affichage avec couleur
            color = get_color_for_aqi(aqi)
            st.markdown(f"<h3 style='color:{color};'>{aqi_desc}</h3>", unsafe_allow_html=True)
            
            # Affichage des niveaux des polluants
            st.write("**Composants de la qualité de l'air** :")
            st.write(f" - CO (Monoxyde de carbone) : {components['co']} µg/m³")
            st.write(f" - NO (Dioxyde d'azote) : {components['no']} µg/m³")
            st.write(f" - NO2 (Dioxyde d'azote) : {components['no2']} µg/m³")
            st.write(f" - O3 (Ozone) : {components['o3']} µg/m³")
            st.write(f" - PM2.5 (Particules fines) : {components['pm2_5']} µg/m³")
            st.write(f" - PM10 (Particules fines) : {components['pm10']} µg/m³")
            st.write(f" - SO2 (Dioxyde de soufre) : {components['so2']} µg/m³")
        else:
            st.error("Erreur lors de la récupération des données de qualité de l'air.")

    # Fonction de conversion de coordonnées EPSG:2154 à WGS84
    def convert_coordinates(epsg2154_lon, epsg2154_lat):
        # Créer un transformateur de Lambert 93 (EPSG:2154) vers WGS84 (EPSG:4326)
        transformer = Transformer.from_crs("EPSG:2154", "EPSG:4326", always_xy=True)
        
        # Effectuer la conversion
        lon_wgs84, lat_wgs84 = transformer.transform(epsg2154_lon, epsg2154_lat)
        
        return lon_wgs84, lat_wgs84

    # Fonction pour récupérer les coordonnées d'une station
    def get_station_coordinates(station_name, station_data):
        station_info = station_data[station_data['StopName'] == station_name]
        if not station_info.empty:
            longitude = station_info.iloc[0]['longitude']
            latitude = station_info.iloc[0]['latitude']
            return longitude, latitude
        else:
            return None, None
        
    # Fonction pour récupérer les stations Vélib' autour d'une position
    def get_velib_stations(lat, lon, radius=500):
        url = "https://opendata.paris.fr/api/records/1.0/search/"
        params = {
            'dataset': 'velib-disponibilite-en-temps-reel',
            'geofilter.distance': f'{lat},{lon},{radius}',
            'rows': 100
        }
        
        response = requests.get(url, params=params)
        
        try:
            data = response.json()
            stations = data['records']
        except ValueError:
            st.error("Erreur lors de la récupération des données.")
            return []
        
        return stations

    # Fonction d'affichage de la carte
    def display_map(lat, lon, stations):
        m = folium.Map(location=[lat, lon], zoom_start=15)
        marker_cluster = MarkerCluster().add_to(m)
        
        # Marquage des stations disponibles
        for station in stations:
            fields = station['fields']
            station_name = fields.get('name', 'Station inconnue')
            bikes_available = fields.get('numbikesavailable', 0)
            docks_available = fields.get('numdocksavailable', 0)
            station_lat, station_lon = fields['coordonnees_geo']
            
            # Ajouter un marqueur uniquement si des vélos sont disponibles
            if bikes_available > 0:
                folium.Marker(
                    location=[station_lat, station_lon],
                    popup=f"<b>{station_name}</b><br>🚲 Vélos disponibles : {bikes_available}<br>🅿️ Bornes disponibles : {docks_available}",
                    icon=folium.Icon(icon="bicycle", color="green")
                ).add_to(marker_cluster)

        return m

    # Fonction pour créer un tableau avec les stations disponibles
    def display_table(stations, line_color):
        table_data = []
        
        for station in stations:
            fields = station['fields']
            station_name = fields.get('name', 'Station inconnue')
            bikes_available = fields.get('numbikesavailable', 0)
            docks_available = fields.get('numdocksavailable', 0)
            
            if bikes_available > 0:
                table_data.append({
                    "Station": station_name,
                    "🚲 Vélos disponibles": bikes_available,
                    "🅿️ Bornes disponibles": docks_available
                })
        
        # Afficher un message si aucune station n'a de vélos disponibles
        if len(table_data) == 0:
            st.warning("Aucune station disponible dans un rayon de 500 mètres.")
        else:
            # Construire le tableau en HTML avec le style dynamique
            df = pd.DataFrame(table_data)
            st.markdown(
                f"""
                <style>
                    .custom-table-velib {{
                        width: 100%;
                        border-collapse: collapse;
                        margin-top: 20px;
                        font-size: 14px; /* Augmente la taille de police */
                        text-align: center;
                    }}
                    .custom-table-velib th {{
                        background-color: {line_color};
                        color: white;
                        font-weight: bold;
                        padding: 10px;
                        border: 2px solid #fff;
                    }}
                    .custom-table-velib td {{
                        padding: 10px;
                        border: 1px solid #ddd;
                    }}
                    .custom-table-velib tr:nth-child(odd) {{
                        background-color: #F9F9F9;
                    }}
                    .custom-table-velib tr:nth-child(even) {{
                        background-color: white;
                    }}
                    .custom-table-velib tr:hover {{
                        background-color: #E0F7E0; /* Couleur survol */
                    }}
                </style>
                """,
                unsafe_allow_html=True,
            )
            
            # Générer le tableau HTML
            st.markdown(
                f"""
                <table class="custom-table-velib">
                    <thead>
                        <tr>
                            <th>Station</th>
                            <th>🚲 Vélos disponibles</th>
                            <th>🅿️ Bornes disponibles</th>
                        </tr>
                    </thead>
                    <tbody>
                        {''.join([f'<tr><td>{row["Station"]}</td><td>{row["🚲 Vélos disponibles"]}</td><td>{row["🅿️ Bornes disponibles"]}</td></tr>' for _, row in df.iterrows()])}
                    </tbody>
                </table>
                """,
                unsafe_allow_html=True,
            )



    # Chargement des fichiers
    gare_referencement = load_gare_referencement()
    unique_vehicle_modes = load_unique_vehicle_modes()

    # Titre de l'application
    st.title("Prochains Passages de votre métro ou RER")

    # Sélection de la ligne
    line_mapping = dict(zip(unique_vehicle_modes["NameLine"], unique_vehicle_modes["LineRef"]))
    sorted_lines = sorted(line_mapping.keys(), key=lambda x: (x.isdigit(), x))
    line_name = st.selectbox("Choisissez une ligne", sorted_lines)
    selected_line_ref = line_mapping[line_name]

    # Afficher un encadré coloré en fonction de la ligne sélectionnée
    if line_name:
        line_color = LINE_COLORS.get(line_name, "#000000")
        st.markdown(
            f"""
            <div class="line-color-box" style="background-color: {line_color};">
                Ligne sélectionnée : {line_name}
            </div>
            """,
            unsafe_allow_html=True
        )

    # Bouton pour valider la ligne
    if st.button("✅ Valider le choix"):
        perturbation_message = get_perturbation_status(selected_line_ref)

        # Appel API pour les horaires
        api_response = get_timetable(selected_line_ref)
        if api_response:
            stop_points_info = extract_stop_point_info(api_response)

            # Vérifier les colonnes nécessaires avant de fusionner
            if "StopPointRef" in stop_points_info.columns and "StopPointRef" in gare_referencement.columns:
                stop_points_with_info = pd.merge(stop_points_info, gare_referencement, on="StopPointRef", how="left")
                st.session_state.stop_points_with_info = stop_points_with_info
            else:
                st.error("Les colonnes nécessaires pour la fusion ne sont pas présentes dans les données.")

            if perturbation_message:
                st.info(f"🚫 Perturbation pour la ligne {line_name} : {perturbation_message}")



    # Tableau des prochains passages avec filtres
    if st.session_state.get("stop_points_with_info") is not None:
        selected_data = st.session_state.stop_points_with_info

        # Ajout des filtres
        stop_name_filter = st.selectbox("Filtrer par gare de départ", ["Toutes"] + selected_data["StopName"].dropna().unique().tolist())
        destination_filter = st.selectbox("Filtrer par gare d'arrivée", ["Toutes"] + selected_data["Destination"].dropna().unique().tolist())

        if stop_name_filter != "Toutes":
            selected_data = selected_data[selected_data["StopName"] == stop_name_filter]
        if destination_filter != "Toutes":
            selected_data = selected_data[selected_data["Destination"] == destination_filter]

        # Ajout de la couleur de fond du tableau en fonction de la ligne
        table_style = f"background-color: {LINE_COLORS.get(line_name, '#FFFFFF')}; color: black;"

        # Affichage dans un tableau amélioré
        st.markdown(
            f"""
            <table class="custom-table" style="{table_style}">
                <thead>
                    <tr>
                        <th>Gare de départ</th>
                        <th>Heure de passage</th>
                        <th>Gare d'arrivée</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join([f'<tr><td>{row.StopName}</td><td>{row._2}</td><td>{row.Destination}</td></tr>' for row in selected_data.itertuples()])}
                </tbody>
            </table>
            <br>
            """,
            unsafe_allow_html=True
        )

        longitude, latitude = get_station_coordinates(stop_name_filter, selected_data)
        lon, lat = convert_coordinates(latitude, longitude)
        data = get_air_quality_by_coords(lat, lon)
        display_air_quality(data)


        stations = get_velib_stations(lat, lon)

        st.write("### 📍 Carte des stations Vélib à proximité de votre gare de départ (rayon de 500 mètres)")
        map = display_map(lat, lon, stations)
        folium_static(map)

        st.write("### 📊 Tableau des stations disponibles à proximité de votre gare de départ")
        display_table(stations, line_color)


    # Footer
    st.markdown("Réalisé par Agit MORCICECK | Gilles GANESHARAJAH | Yassine ACHARGUI | Brahim EL FARH")

# Onglet "Plan des Lignes de Métro"
with tab2:
    import pandas as pd
    import folium
    from folium.plugins import MarkerCluster
    from streamlit_folium import folium_static
    import streamlit as st

    # Charger le fichier Excel
    df = pd.read_excel('Emplacement_gares.xlsx')

    # Dictionnaire des couleurs des lignes
    LINE_COLOR = {
        "1": "#FFD700",  # Jaune
        "2": "#0055FF",  # Bleu
        "3": "#968D4F",  # Marron clair
        "3bis": "#82C8E6",  # Bleu clair
        "4": "#BB4D98",  # Violet
        "5": "#FF8031",  # Orange
        "6": "#76C3B3",  # Vert clair
        "7": "#F59EC2",  # Rose
        "7bis": "#82C8E6",  # Bleu clair
        "8": "#D5A6FF",  # Mauve
        "9": "#B6BD00",  # Vert citron
        "10": "#D9B17E",  # Beige
        "11": "#8C6239",  # Marron foncé
        "12": "#008F62",  # Vert forêt
        "13": "#99D4D4",  # Cyan clair
        "14": "#62259D",  # Violet profond
        "A": "#E2231A",  # Rouge
        "B": "#3083DC",  # Bleu royal
        "C": "#F4D743",  # Jaune pâle
        "D": "#008F62",  # Vert forêt
        "E": "#BF6F7B"   # Rose sombre
    }

    # Créer un dictionnaire des coordonnées par ligne
    line_coordinates = {}
    station_lines = {}
    station_coords = {}

    for index, row in df.iterrows():
        line = row['Ligne']
        station = row['Gare']
        coord = (row['Latitude'], row['Longitude'])

        if line not in line_coordinates:
            line_coordinates[line] = []
        line_coordinates[line].append(coord)

        if station not in station_lines:
            station_lines[station] = []
        station_lines[station].append(line)

        station_coords[station] = coord

    # Interface Streamlit
    st.title("Plan des lignes de métro et RER")

    # Ajouter un sélecteur pour choisir une ligne et filtrer les gares
    selected_line = st.selectbox("Choisissez une ligne à afficher", ["Toutes"] + list(line_coordinates.keys()))

    # Filtrer les gares en fonction de la ligne sélectionnée
    gares_options = ["Toutes"]
    if selected_line == "Toutes":
        gares_options += list(station_lines.keys())
    else:
        gares_options += [station for station, lines in station_lines.items() if selected_line in lines]

    selected_station = st.selectbox("Choisissez une gare", gares_options)

    # Filtrer les lignes en fonction de la gare sélectionnée
    if selected_station != "Toutes":
        lines_through_station = station_lines[selected_station]
        if selected_line == "Toutes":
            filtered_coordinates = {line: line_coordinates[line] for line in lines_through_station}
        else:
            filtered_coordinates = {selected_line: line_coordinates[selected_line]} if selected_line in lines_through_station else {}
    else:
        filtered_coordinates = line_coordinates if selected_line == "Toutes" else {selected_line: line_coordinates[selected_line]}

    # Gestion dynamique du centrage de la carte
    all_coords = [coord for coords in filtered_coordinates.values() for coord in coords]
    if all_coords:
        map_center = [sum(x) / len(x) for x in zip(*all_coords)]
        map = folium.Map(location=map_center, zoom_start=12)

        # Mettre en avant la gare sélectionnée
        if selected_station != "Toutes":
            station_coord = station_coords[selected_station]
            folium.Marker(
                location=station_coord,
                icon=folium.Icon(color='red', icon='info-sign'),
                popup=f"Gare sélectionnée : {selected_station}"
            ).add_to(map)

        # Afficher les lignes et les stations
        for line_name, coords in filtered_coordinates.items():
            line_id = line_name.split()[-1]
            color = LINE_COLOR.get(line_id, "#000000")  # Noir par défaut si la ligne n'est pas définie

            folium.PolyLine(
                locations=coords,
                color=color,
                weight=5,
                tooltip=line_name
            ).add_to(map)

            marker_cluster = MarkerCluster().add_to(map)
            for lat, lon in coords:
                # Afficher le nom de la ligne et de la gare dans l'infobulle
                station_name = [key for key, value in station_coords.items() if value == (lat, lon)]
                station_display = station_name[0] if station_name else "Inconnue"
                folium.CircleMarker(
                    location=[lat, lon],
                    radius=6,
                    color=color,
                    fill=True,
                    fill_color=color,
                    fill_opacity=0.7,
                    popup=f"Ligne: {line_name} - Gare: {station_display}"
                ).add_to(marker_cluster)

        # Afficher la carte dans Streamlit
        folium_static(map)
    else:
        st.error("Aucune ligne disponible pour la sélection actuelle.")

    
    from collections import deque
    
    # Dictionnaire des couleurs des lignes
    LINE_COLOR = {
        "Ligne 1": "#FFD700",  # Jaune
        "Ligne 2": "#0055FF",  # Bleu
        "Ligne 3": "#968D4F",  # Marron clair
        "3bis": "#82C8E6",  # Bleu clair
        "Ligne 4": "#BB4D98",  # Violet
        "Ligne 5": "#FF8031",  # Orange
        "Ligne 6": "#76C3B3",  # Vert clair
        "Ligne 7": "#F59EC2",  # Rose
        "7bis": "#82C8E6",  # Bleu clair
        "Ligne 8": "#D5A6FF",  # Mauve
        "Ligne 9": "#B6BD00",  # Vert citron
        "Ligne 10": "#D9B17E",  # Beige
        "Ligne 11": "#8C6239",  # Marron foncé
        "Ligne 12": "#008F62",  # Vert forêt
        "Ligne 13": "#99D4D4",  # Cyan clair
        "Ligne 14": "#62259D",  # Violet profond
        "A": "#E2231A",  # Rouge
        "B": "#3083DC",  # Bleu royal
        "C": "#F4D743",  # Jaune pâle
        "D": "#008F62",  # Vert forêt
        "E": "#BF6F7B"   # Rose sombre
    }

    # Dictionnaires pour stocker les informations
    line_coordinates = {}
    station_lines = {}
    station_coords = {}
    adjacency_list = {}

    for index, row in df.iterrows():
        line = row['Ligne']
        station = row['Gare']
        coord = (row['Latitude'], row['Longitude'])

        if station not in station_lines:
            station_lines[station] = []
        station_lines[station].append(line)

        station_coords[station] = coord

        if station not in adjacency_list:
            adjacency_list[station] = []
        previous_station = df.iloc[index - 1] if index > 0 else None
        if previous_station is not None and previous_station['Ligne'] == line:
            previous_station_name = previous_station['Gare']
            adjacency_list[station].append(previous_station_name)
            adjacency_list[previous_station_name].append(station)

    # Interface Streamlit
    st.title("Trouvez votre itinéraire")

    # Sélecteurs de gares de départ et d'arrivée
    station_depart = st.selectbox("Choisissez une gare de départ", list(station_coords.keys()))
    station_arrivee = st.selectbox("Choisissez une gare d'arrivée", list(station_coords.keys()))

    # Fonction pour trouver le plus court chemin
    def shortest_path_bfs(graph, start, end):
        queue = deque([[start]])
        visited = set()

        while queue:
            path = queue.popleft()
            station = path[-1]

            if station in visited:
                continue

            visited.add(station)

            if station == end:
                return path

            for neighbor in graph[station]:
                new_path = list(path)
                new_path.append(neighbor)
                queue.append(new_path)

        return None

    # Fonction pour regrouper les gares par ligne
    def group_stations_by_line(path):
        grouped = []
        current_line = None
        segment = []

        for i in range(len(path) - 1):
            station = path[i]
            next_station = path[i + 1]
            common_lines = set(station_lines[station]).intersection(station_lines[next_station])
            line = list(common_lines)[0] if common_lines else None

            if line == current_line:
                segment.append(station)
            else:
                if segment:
                    grouped.append((current_line, segment + [station]))
                current_line = line
                segment = [station]

        segment.append(path[-1])
        grouped.append((current_line, segment))

        return grouped

    # Afficher l'itinéraire
    if st.button("Afficher l'itinéraire"):
        if station_depart == station_arrivee:
            st.warning("La gare de départ et la gare d'arrivée sont identiques !")
        else:
            chemin = shortest_path_bfs(adjacency_list, station_depart, station_arrivee)

            if chemin:
                st.success("Voici l'itinéraire proposé :")
                grouped_path = group_stations_by_line(chemin)

                # Affichage des étapes par segments de lignes
                for line, stations in grouped_path:
                    line_color = LINE_COLOR.get(line, "#000000")
                    start_station = stations[0]
                    end_station = stations[-1]

                    background_style = f"background-color: {line_color}; padding: 15px; border-radius: 10px; margin-bottom: 10px; color: white;"
                    st.markdown(f"<div style='{background_style}; box-shadow: 2px 2px 5px rgba(0, 0, 0, 0.3);'>🚇 **Ligne {line}** : De **{start_station}** à **{end_station}**</div>", unsafe_allow_html=True)

                    # Affichage pour clarifier la marche ou les changements si nécessaire
                    if len(stations) > 2:
                        st.markdown(f"<div style='background-color: rgba(255, 255, 255, 0.9); padding: 10px; border-radius: 5px; margin-top: -5px;'>Stations intermédiaires : {', '.join(stations[1:-1])}</div>", unsafe_allow_html=True)

                st.markdown("<div style='text-align: center; margin-top: 20px;'><b>🏁 Arrivée à destination</b></div>", unsafe_allow_html=True)
            else:
                st.error("Aucun itinéraire trouvé entre ces gares.")
    else:
        st.info("Choisissez une gare de départ et une gare d'arrivée, puis cliquez sur 'Afficher l'itinéraire'.")


