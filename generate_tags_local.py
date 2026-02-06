import os
import json
import requests
import time
import urllib.parse

# Configuration
REPO_OWNER = "Racontine"
REPO_NAME = "commun"
BRANCH = "main"

# URL du fichier ratings.json sur GitHub (Raw)
RATINGS_URL = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/{BRANCH}/ratings.json"
# URL de l'API GitHub pour récupérer l'arbre des fichiers (récursif)
TREE_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/git/trees/{BRANCH}?recursive=1"

# Fichier local de sortie
LOCAL_RATINGS_FILE = "ratings.json"

def get_short_url(long_url):
    """
    Génère une URL courte via TinyURL.
    """
    try:
        api_url = f"https://tinyurl.com/api-create.php?url={urllib.parse.quote(long_url)}"
        response = requests.get(api_url, timeout=10)
        if response.status_code == 200:
            short_url = response.text.strip()
            if short_url.startswith("http"):
                return short_url
    except Exception as e:
        print(f"❌ Erreur TinyURL : {e}")
    return None

def main():
    print("🔄 Récupération de la liste des fichiers sur GitHub...")
    
    # 1. Récupérer ratings.json existant
    ratings = {}
    try:
        resp = requests.get(RATINGS_URL)
        if resp.status_code == 200:
            ratings = resp.json()
            print(f"✅ ratings.json chargé ({len(ratings)} entrées).")
        else:
            print("⚠️ ratings.json non trouvé ou vide, on commence à zéro.")
    except Exception as e:
        print(f"⚠️ Erreur chargement ratings.json : {e}")

    # 2. Récupérer tous les fichiers du dépôt
    try:
        resp = requests.get(TREE_URL)
        if resp.status_code != 200:
            print(f"❌ Impossible de lire le dépôt : {resp.status_code}")
            return
        
        tree = resp.json().get("tree", [])
    except Exception as e:
        print(f"❌ Erreur API GitHub : {e}")
        return

    # 3. Filtrer les fichiers audio/vidéo
    media_files = [
        item for item in tree 
        if item["type"] == "blob" and 
           (item["path"].startswith("media/audio/") or item["path"].startswith("media/video/"))
    ]
    
    print(f"📂 {len(media_files)} fichiers multimédia trouvés dans le dépôt.")

    # 4. Traitement
    updated = False
    count = 0
    total = len(media_files)

    for item in media_files:
        filename = item["path"].split("/")[-1]
        
        # Vérifier si déjà traité
        metadata = ratings.get(filename, {})
        current_short = metadata.get("shortUrl", "")
        
        if current_short and current_short.startswith("http") and len(current_short) < 50:
            continue  # Déjà fait

        count += 1
        print(f"[{count}/{total}] Traitement de : {filename}")
        
        # Construire l'URL Raw
        raw_url = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/{BRANCH}/{item['path']}"
        
        # Générer le lien court
        short_url = get_short_url(raw_url)
        
        if short_url:
            print(f"   ➜ Lien généré : {short_url}")
            
            # Mise à jour des métadonnées (on préserve score/type si existants)
            ratings[filename] = {
                "score": metadata.get("score", 0),
                "type": metadata.get("type", "Livre"),
                "shortUrl": short_url
            }
            updated = True
            time.sleep(0.5)  # Pause pour éviter le Rate Limit
        else:
            print("   ❌ Échec génération lien court")

    # 5. Sauvegarde et Instructions
    if updated:
        with open(LOCAL_RATINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(ratings, f, indent=2, ensure_ascii=False)
        
        print("\n✨ Terminé ! Le fichier 'ratings.json' a été mis à jour localement.")
        print("🚀 Pour envoyer les changements vers GitHub (dépôt 'commun'), exécutez :")
        print("---------------------------------------------------------------")
        print(f"git clone https://github.com/{REPO_OWNER}/{REPO_NAME}.git temp_commun")
        print(f"copy ratings.json temp_commun\\ratings.json")
        print("cd temp_commun")
        print('git add ratings.json')
        print('git commit -m "Update short URLs"')
        print('git push')
        print("cd ..")
        print("rmdir /s /q temp_commun")
        print("---------------------------------------------------------------")
        print("Ou si vous avez déjà ce dépôt configuré, poussez simplement le fichier.")
    else:
        print("\n✅ Tout est déjà à jour, aucune modification nécessaire.")

if __name__ == "__main__":
    main()
