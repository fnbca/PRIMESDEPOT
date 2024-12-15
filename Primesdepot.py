import streamlit as st
import os
import base64
import requests
from PIL import Image, ImageOps

# Configuration API Fidealis
API_URL = os.getenv("API_URL")
API_KEY = os.getenv("API_KEY")
ACCOUNT_KEY = os.getenv("ACCOUNT_KEY")

# Configuration API Google Maps
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Fonction pour obtenir les coordonnées GPS à partir d'une adresse
def get_coordinates(address):
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={GOOGLE_API_KEY}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if data['status'] == 'OK':
            location = data['results'][0]['geometry']['location']
            return location['lat'], location['lng']
    return None, None

# Fonction pour se connecter à l'API Fidealis
def api_login():
    login_response = requests.get(
        f"{API_URL}?key={API_KEY}&call=loginUserFromAccountKey&accountKey={ACCOUNT_KEY}"
    )
    login_data = login_response.json()
    if 'PHPSESSID' in login_data:
        return login_data["PHPSESSID"]
    return None

# Fonction pour appeler l'API Fidealis
def api_upload_files(description, files, session_id):
    for i in range(0, len(files), 12):
        batch_files = files[i:i + 12]
        data = {
            "key": API_KEY,
            "PHPSESSID": session_id,
            "call": "setDeposit",
            "description": description,
            "type": "deposit",
            "hidden": "0",
            "sendmail": "1",
        }
        for idx, file in enumerate(batch_files, start=1):
            with open(file, "rb") as f:
                encoded_file = base64.b64encode(f.read()).decode("utf-8")
                data[f"filename{idx}"] = os.path.basename(file)
                data[f"file{idx}"] = encoded_file
        requests.post(API_URL, data=data)

# Fonction pour créer un collage
def create_collage(images, output_path, max_images=3):
    min_height = min(img.size[1] for img in images)
    resized_images = [ImageOps.fit(img, (int(img.size[0] * min_height / img.size[1]), min_height)) for img in images]
    total_width = sum(img.size[0] for img in resized_images) + (len(resized_images) - 1) * 20 + 50
    collage = Image.new("RGB", (total_width, min_height + 50), (255, 255, 255))
    x_offset = 25
    for img in resized_images:
        collage.paste(img, (x_offset, 25))
        x_offset += img.size[0] + 20
    collage.save(output_path)

# Fonction pour renommer la première photo directement
def rename_first_file(files, client_name):
    first_file = files[0]
    new_name = os.path.join(os.path.dirname(first_file), f"{client_name}_1.jpg")
    os.rename(first_file, new_name)
    files[0] = new_name  # Met à jour le chemin de la première photo
    return files
    
# Interface utilisateur Streamlit
st.title("Formulaire de dépôt FIDEALIS pour PRIMES ")
session_id = api_login()

if session_id:
    # Appel pour obtenir les crédits pour le client
    credit_url = f"{API_URL}?key={API_KEY}&PHPSESSID={session_id}&call=getCredits&product_ID="
    credit_data = requests.get(credit_url).json()

    if isinstance(credit_data, dict) and "4" in credit_data:
        product_4_quantity = credit_data["4"]["quantity"]
        st.write(f"Crédit restant {product_4_quantity}")
    else:
        st.error("Échec de la récupération des données de crédit.")
else:
    st.error("Échec de la connexion à l'API.")

client_name = st.text_input("Nom du client")
address = st.text_input("Adresse complète (ex: 123 rue Exemple, Paris, France)")

# Initialisation des champs Latitude et Longitude
latitude = st.session_state.get("latitude", "")
longitude = st.session_state.get("longitude", "")

# Bouton pour générer automatiquement les coordonnées GPS
if st.button("Générer les coordonnées GPS"):
    if address:
        lat, lng = get_coordinates(address)
        if lat is not None and lng is not None:
            st.session_state["latitude"] = str(lat)
            st.session_state["longitude"] = str(lng)
            latitude = str(lat)
            longitude = str(lng)
        else:
            st.error("Impossible de générer les coordonnées GPS pour l'adresse fournie.")

# Champs Latitude et Longitude pré-remplis
latitude = st.text_input("Latitude", value=latitude)
longitude = st.text_input("Longitude", value=longitude)

uploaded_files = st.file_uploader("Téléchargez les photos (JPEG/PNG)", accept_multiple_files=True, type=["jpg", "png"])

if st.button("Soumettre"):
    if not client_name or not address or not latitude or not longitude or not uploaded_files:
        st.error("Veuillez remplir tous les champs et télécharger au moins une photo.")
    else:
        st.info("Préparation de l'envoi...")
        
        if session_id:
            # Sauvegarder les fichiers localement et les renommer immédiatement
            saved_files = []
            for idx, file in enumerate(uploaded_files):
                save_path = f"{client_name}_{idx + 1}.jpg"
                with open(save_path, "wb") as f:
                    f.write(file.read())
                saved_files.append(save_path)

            # Créer des collages pour les photos supplémentaires
            if len(saved_files) > 12:
                for i in range(12, len(saved_files), 3):
                    collage_path = f"collage_{i}.jpg"
                    create_collage([Image.open(f) for f in saved_files[i:i + 3]], collage_path)
                    saved_files.append(collage_path)

            # Description avec coordonnées GPS
            description = f"SCELLÉ NUMERIQUE Bénéficiaire: Nom: {client_name}, Adresse: {address}, Coordonnées GPS: Latitude {latitude}, Longitude {longitude}"

            # Appeler l'API avec les fichiers

            st.info("Vérification des données...")
            api_upload_files(description, saved_files, session_id)
            # Affichage unique du dernier message
            st.success("Données envoyées avec succès !")
