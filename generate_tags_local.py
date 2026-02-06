import os
import json
import requests
import time
import urllib.parse
import qrcode
import subprocess
import shutil
from PIL import Image, ImageDraw, ImageFont

# Configuration
REPO_OWNER = "Racontine"
REPO_NAME = "commun"
BRANCH = "main"

# URL du fichier ratings.json sur GitHub (Raw)
RATINGS_URL = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/{BRANCH}/ratings.json"
# URL de l'API GitHub pour récupérer l'arbre des fichiers (récursif)
TREE_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/git/trees/{BRANCH}?recursive=1"

# Dossiers et Fichiers Locaux
LOCAL_RATINGS_FILE = "ratings.json"
OUTPUT_QR_DIR = "TAGS_GENERE"

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

def create_rich_tag(url, display_name, short_url, filename):
    """
    Génère une image de tag complète : QR Code + Nom + Lien Court
    """
    if not os.path.exists(OUTPUT_QR_DIR):
        os.makedirs(OUTPUT_QR_DIR)
    
    # 1. Générer le QR Code
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    
    # 2. Créer une image plus grande pour ajouter du texte
    w, h = qr_img.size
    canvas_h = h + 100 # Espace pour le texte sous le QR
    canvas = Image.new('RGB', (w, canvas_h), color=(255, 255, 255))
    canvas.paste(qr_img, (0, 0))
    
    draw = ImageDraw.Draw(canvas)
    
    # Essayer de charger une police (fallback sur default)
    try:
        font_name = ImageFont.truetype("arial.ttf", 20)
        font_link = ImageFont.truetype("arial.ttf", 16)
    except:
        font_name = ImageFont.load_default()
        font_link = ImageFont.load_default()

    # Ajouter le nom du fichier (tronqué si trop long)
    name_text = display_name[:30] + "..." if len(display_name) > 30 else display_name
    draw.text((w/2, h + 10), name_text, fill="black", font=font_name, anchor="mm")
    
    # Ajouter le lien court
    draw.text((w/2, h + 45), short_url, fill="blue", font=font_link, anchor="mm")
    
    # Sauvegarder
    safe_name = "".join([c if c.isalnum() else "_" for c in display_name])
    tag_path = os.path.join(OUTPUT_QR_DIR, f"TAG_{safe_name}.png")
    canvas.save(tag_path)
    return tag_path

def run_cmd(cmd, cwd=None):
    try:
        subprocess.run(cmd, shell=True, check=True, cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return False
    return True

def main():
    print("="*60)
    print("🚀 RACONTINE : GÉNÉRATEUR DE TAGS (TINYURL)")
    print("="*60)

    # 1. Charger ratings.json
    ratings = {}
    print("🔄 Chargement des métadonnées depuis GitHub...")
    try:
        resp = requests.get(RATINGS_URL)
        if resp.status_code == 200:
            ratings = resp.json()
            print(f"✅ ratings.json chargé.")
        else:
            print("⚠️ Fichier ratings.json inexistant sur le serveur.")
    except Exception as e:
        print(f"⚠️ Erreur chargement : {e}")

    # 2. Scanner les fichiers (Récursif)
    print("📂 Scan profond du dépôt media/ (sous-dossiers inclus)...")
    try:
        resp = requests.get(TREE_URL)
        if resp.status_code != 200:
            print(f"❌ Erreur API : {resp.status_code}")
            return
        tree = resp.json().get("tree", [])
    except Exception as e:
        print(f"❌ Erreur connexion : {e}")
        return

    media_files = [
        item for item in tree 
        if item["type"] == "blob" and 
           (item["path"].startswith("media/audio/") or item["path"].startswith("media/video/"))
    ]
    print(f"🔍 {len(media_files)} fichiers media détectés.")

    # 3. Génération
    updated_git = False
    count = 0
    total = len(media_files)

    for i, item in enumerate(media_files, 1):
        full_path = item["path"]
        filename = full_path.split("/")[-1]
        
        metadata = ratings.get(filename, {})
        short_url = metadata.get("shortUrl", "")

        # Si pas de lien court TinyURL valide
        if not short_url or "tinyurl.com" not in short_url:
            print(f"[{i}/{total}] ⚡ Nouveau tag requis : {filename}")
            raw_url = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/{BRANCH}/{full_path}"
            
            short_url = get_short_url(raw_url)
            if short_url:
                ratings[filename] = {
                    "score": metadata.get("score", 0),
                    "type": metadata.get("type", "Livre"),
                    "shortUrl": short_url
                }
                updated_git = True
                print(f"   Lien : {short_url}")
            else:
                print(f"   ❌ Échec TinyURL")
                continue

        # Dans tous les cas, on génère l'image physique en local
        path = create_rich_tag(short_url, filename, short_url, filename)
        count += 1

    # 4. Push GitHub Automatique
    if updated_git:
        with open(LOCAL_RATINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(ratings, f, indent=2, ensure_ascii=False)
        
        print("\n📤 Envoi des nouveaux tags vers GitHub...")
        temp = "temp_git_sync"
        if os.path.exists(temp): shutil.rmtree(temp)
        
        if run_cmd(f"git clone https://github.com/{REPO_OWNER}/{REPO_NAME}.git {temp}"):
            shutil.copy(LOCAL_RATINGS_FILE, os.path.join(temp, LOCAL_RATINGS_FILE))
            if run_cmd("git add ratings.json", cwd=temp):
                if run_cmd('git commit -m "Update short URLs (local script)"', cwd=temp):
                    if run_cmd("git push", cwd=temp):
                        print("✅ Synchronisation réussie !")
        
        if os.path.exists(temp): shutil.rmtree(temp)

    print(f"\n✨ TERMINE ! {count} tags sont disponibles dans le dossier :")
    print(f"� {os.path.abspath(OUTPUT_QR_DIR)}")

if __name__ == "__main__":
    main()
