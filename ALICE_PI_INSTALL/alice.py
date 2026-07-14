#!/usr/bin/env python3

import time
import cv2
import subprocess
import sys
import socket as _socket
from pathlib import Path
from picamera2 import Picamera2
from pyzbar.pyzbar import decode
from gpiozero import Button


# ======================
# DOWNLOADER LOGIC (Integrated)
# ======================
import os
import urllib.parse
import requests

BASE_DL_DIR = "/home/alice/media"
AUDIO_DIR = f"{BASE_DL_DIR}/audio"
VIDEO_DIR = f"{BASE_DL_DIR}/video"

# Cache local : mémorise short_url → chemin fichier local
# Permet de rejouer un tag déjà scanné même sans internet
URL_CACHE_FILE = f"{BASE_DL_DIR}/url_cache.json"

def _load_url_cache() -> dict:
    try:
        with open(URL_CACHE_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {}

def _save_url_cache(cache: dict):
    try:
        os.makedirs(BASE_DL_DIR, exist_ok=True)
        with open(URL_CACHE_FILE, 'w') as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        print(f"⚠️ Impossible de sauvegarder le cache URL : {e}")

def _normalize_url(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return raw
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    return "https://" + raw

def resolve_final_url(raw_url: str) -> str:
    url = _normalize_url(raw_url)
    try:
        r = requests.head(url, allow_redirects=True, timeout=10)
        if r.url:
            return r.url
    except Exception:
        pass
    r = requests.get(url, allow_redirects=True, stream=True, timeout=15)
    return r.url

def ensure_file(raw_url: str) -> str:
    key = _normalize_url(raw_url)

    # ── ÉTAPE 1 : vérifier le cache local (fonctionne hors-ligne) ──────────
    url_cache = _load_url_cache()
    if key in url_cache:
        cached_path = url_cache[key]
        if os.path.exists(cached_path):
            print(f"📁 Cache local → lecture directe : {cached_path}")
            return cached_path
        else:
            # Le fichier a été supprimé, on retire l'entrée périmée
            print(f"⚠️ Fichier cache introuvable ({cached_path}), re-téléchargement...")
            del url_cache[key]
            _save_url_cache(url_cache)

    # ── ÉTAPE 2 : résoudre le short link et télécharger (nécessite internet) ─
    try:
        final_url = resolve_final_url(key)
    except Exception as e:
        raise RuntimeError(f"Pas de cache et pas d'internet pour : {key} ({e})")

    print(f"🔗 URL finale : {final_url}")

    filename = urllib.parse.urlparse(final_url).path.split("/")[-1]
    ext = os.path.splitext(filename)[1].lower()

    if ext in [".mp3", ".wav"]:
        dest_dir = AUDIO_DIR
    else:
        dest_dir = VIDEO_DIR

    os.makedirs(dest_dir, exist_ok=True)
    local_path = os.path.join(dest_dir, filename)

    if not os.path.exists(local_path):
        print(f"⬇️ Téléchargement : {final_url}")
        r = requests.get(final_url, timeout=30)
        r.raise_for_status()
        with open(local_path, "wb") as f:
            f.write(r.content)
        print(f"✅ Téléchargé : {local_path}")
    else:
        print(f"📁 Déjà présent : {local_path}")

    # ── ÉTAPE 3 : sauvegarder dans le cache pour les prochaines fois ────────
    url_cache[key] = local_path
    _save_url_cache(url_cache)

    return local_path


# ======================
# CONFIG
# ======================
import json

CONFIG_FILE = "/home/alice/media/config.json"
# Fallback local path for dev/windows
if not os.path.exists(CONFIG_FILE) and os.path.exists("config.json"):
    CONFIG_FILE = "config.json"

def load_config():
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ Erreur chargement config: {e}")
        return {}

config_data = load_config()
DEFAULT_VOLUME_PERCENT = config_data.get("volume", 90)
DEFAULT_GAIN = int(8192 * DEFAULT_VOLUME_PERCENT / 100)

COOLDOWN_SEC = 3
WELCOME_AUDIO = "/home/alice/media/audio/welcome_alice_woman.mp3"
DETECTED_AUDIO = "/home/alice/media/audio/carte_detected.mp3"

TOUCH_GPIO = 12        # bouton tactile → play / pause
HAT_BUTTON_GPIO = 17   # bouton HAT → reset scan QR

# Optimization Config
FRAME_SKIP = 3  # Analyze 1 out of every 3 frames


# ======================
# AUDIO PLAYER CLASS  (mpv IPC – pause/reprise à la position exacte)
# ======================
MPV_SOCKET = "/tmp/alice_mpv.sock"

class AudioPlayer:
    def __init__(self):
        self.process = None
        self.paused = False
        self.current_path = None
        self.last_path = None  # Mémorise le dernier fichier joué

    # ------------------------------------------------------------------
    # Envoi d'une commande JSON à mpv via son socket IPC
    # ------------------------------------------------------------------
    def _mpv_cmd(self, *args):
        """Envoie une commande à mpv via le socket IPC. Retourne True si OK."""
        try:
            with _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM) as s:
                s.settimeout(1.0)
                s.connect(MPV_SOCKET)
                msg = json.dumps({"command": list(args)}) + "\n"
                s.sendall(msg.encode())
                return True
        except Exception as e:
            print(f"⚠️ mpv IPC erreur : {e}")
            return False

    # ------------------------------------------------------------------
    # Lecture bloquante (sons courts : welcome, detected)
    # On utilise mpv directement, sans socket IPC
    # ------------------------------------------------------------------
    def play_blocking(self, path: str):
        print(f"▶️  Lecture (bloquante) : {path}")
        vol = DEFAULT_VOLUME_PERCENT
        subprocess.run(
            ["mpv", "--no-video", f"--volume={vol}", "--really-quiet", path],
            check=False
        )

    # ------------------------------------------------------------------
    # Lancement d'un média avec socket IPC (pause/reprise position exacte)
    # ------------------------------------------------------------------
    def start(self, path: str):
        self.stop()
        self.current_path = path
        self.last_path = path
        self.paused = False

        # Supprime l'ancien socket s'il existe
        try:
            os.remove(MPV_SOCKET)
        except FileNotFoundError:
            pass

        vol = DEFAULT_VOLUME_PERCENT
        cmd = [
            "mpv",
            "--no-video",
            f"--volume={vol}",
            "--really-quiet",
            f"--input-ipc-server={MPV_SOCKET}",
            path
        ]
        print(f"▶️  Lecture : {path}")
        self.process = subprocess.Popen(cmd)
        # Attend que mpv crée le socket (max 2 s)
        for _ in range(20):
            if os.path.exists(MPV_SOCKET):
                break
            time.sleep(0.1)

    # ------------------------------------------------------------------
    # Arrêt complet
    # ------------------------------------------------------------------
    def stop(self):
        if self.process:
            if self.process.poll() is None:
                try:
                    self._mpv_cmd("quit")
                    self.process.wait(timeout=2)
                except Exception:
                    self.process.kill()
            self.process = None
        self.paused = False
        self.current_path = None
        try:
            os.remove(MPV_SOCKET)
        except FileNotFoundError:
            pass

    def is_playing(self):
        return self.process is not None and self.process.poll() is None

    # ------------------------------------------------------------------
    # Bascule Pause / Reprise
    # mpv reste vivant en pause → position conservée indéfiniment
    # ------------------------------------------------------------------
    def toggle_pause(self):
        # Cas 1 : mpv n'est plus en vie (fin normale du fichier)
        if self.process is None or self.process.poll() is not None:
            self.process = None
            self.paused = False
            if self.last_path:
                print(f"🔄 Média terminé. Relecture depuis le début : {self.last_path}")
                self.start(self.last_path)
            else:
                print("ℹ️ Aucun média en mémoire")
            return

        # Cas 2 : mpv actif → on bascule pause/reprise via IPC
        # mpv conserve la position exacte pendant la pause, quelle que soit la durée
        ok = self._mpv_cmd("cycle", "pause")
        if ok:
            self.paused = not self.paused
            if self.paused:
                print("⏸️  Pause (position mémorisée par mpv)")
            else:
                print("▶️  Reprise (à la position exacte)")
        else:
            print("⚠️ Impossible de contacter mpv – vérifier que mpv est installé")



# ======================
# GLOBAL STATE
# ======================
player = AudioPlayer()


# ======================
# CAMERA INIT
# ======================
def init_camera():
    cam = Picamera2()
    # Optimized: 640x480 resolution for faster processing
    config = cam.create_still_configuration(
        main={"size": (640, 480), "format": "RGB888"},
        buffer_count=2
    )
    cam.configure(config)
    cam.start()
    time.sleep(0.5)
    return cam


# ======================
# BUTTONS HANDLERS
# ======================
def on_touch_pressed():
    print("👆 Touch → play/pause")
    player.toggle_pause()

def on_hat_pressed():
    print("🔄 Bouton HAT → retour scan QR")
    player.stop()
    player.last_path = None  # On oublie le dernier média pour éviter un replay accidentel
    if Path(DETECTED_AUDIO).exists():
        player.play_blocking(DETECTED_AUDIO)


# ======================
# MAIN LOOP
# ======================
def main():
    cam = init_camera()
    
    # Init Buttons (bouton poussoir GPIO12 : pull_up=True, anti-rebond court)
    touch_button = Button(TOUCH_GPIO, pull_up=True, bounce_time=0.05)
    hat_button = Button(HAT_BUTTON_GPIO, bounce_time=0.2)
    
    touch_button.when_pressed = on_touch_pressed
    hat_button.when_pressed = on_hat_pressed

    print("📸 Alice prête – scan QR optimisé en cours (CTRL+C pour quitter)")

    if Path(WELCOME_AUDIO).exists():
        player.play_blocking(WELCOME_AUDIO)
    else:
        print("⚠️ WELCOME_AUDIO introuvable")

    last_scanned_qr = None
    last_qr_seen_time = 0
    current_playing_qr = None # Stocke le QR en cours de lecture
    frame_count = 0
    
    # Config Timeout (10 secondes)
    RESET_TIMEOUT = 10.0

    try:
        while True:
            # Picamera2 capture
            image = cam.capture_array()
            
            # Optimization: Frame Skipping
            frame_count += 1
            if frame_count % FRAME_SKIP != 0:
                continue

            # Convert to Gray for pyzbar
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
            
            codes = decode(gray)
            
            if not codes:
                # Pas de QR détecté
                # On vérifie si le temps écoulé depuis la dernière vue dépasse 10s
                if last_scanned_qr is not None:
                    elapsed = time.time() - last_qr_seen_time
                    if elapsed > RESET_TIMEOUT:
                        print(f"♻️ Reset du scan (Tag absent depuis {elapsed:.1f}s)")
                        last_scanned_qr = None
                
                time.sleep(0.05)
                continue
            
            # QR Trouvé !
            qr_text = codes[0].data.decode("utf-8").strip()
            
            # On met à jour le "Dernier moment vu" pour maintenir la présence
            last_qr_seen_time = time.time()

            # Smart Detection Logic
            if qr_text == last_scanned_qr:
                # Même QR qu'avant, et on vient de le voir -> on ne fait rien
                continue
            
            # --- Check Nouveau TAG vs Lecture En Cours ---
            if qr_text == current_playing_qr and player.is_playing():
                print(f"🎵 Déjà en lecture : {qr_text} (On continue...)")
                # On met à jour last_scanned_qr pour éviter de spammer ce check
                last_scanned_qr = qr_text
                continue
            # ---------------------------------------------
            
            print(f"🔍 Nouveau QR détecté : {qr_text}")
            last_scanned_qr = qr_text
            current_playing_qr = qr_text # On mémorise ce qu'on lance

            if Path(DETECTED_AUDIO).exists():
               player.play_blocking(DETECTED_AUDIO)

            # Téléchargement si nécessaire (ou lecture depuis cache local)
            try:
                local_path = ensure_file(qr_text)
                player.start(local_path)
            except Exception as e:
                print(f"⚠️ Impossible de charger le média : {e}")
                print("📵 Tag inconnu et pas d'internet – scan ignoré")

    except KeyboardInterrupt:
        print("\n🛑 Arrêt demandé")
    except Exception as e:
        print(f"\n⚠️ Erreur fatale: {e}")
    finally:
        cam.stop()
        player.stop()


if __name__ == "__main__":
    main()
