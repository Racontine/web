#!/usr/bin/env python3
"""
ALICE_SON.py - Serveur web léger pour contrôler le volume d'Alice
Sans avoir besoin de basculer en mode hotspot !

Usage:
    sudo python3 /home/alice/ALICE_SON.py

Accès:
    http://<IP_DU_PI>:8080

Le serveur tourne en parallèle d'alice.py et permet de modifier le volume
sans interrompre le WiFi ni l'application principale.
"""

from flask import Flask, render_template_string, request, jsonify
import json
import os
import subprocess
import socket

app = Flask(__name__)

# Configuration
CONFIG_FILE = "/home/alice/media/config.json"
DEFAULT_PORT = 8080

# Fallback local pour développement
if not os.path.exists(CONFIG_FILE):
    CONFIG_FILE = "config.json"
    os.makedirs(os.path.dirname(CONFIG_FILE) or ".", exist_ok=True)


def load_config():
    """Charge la configuration depuis config.json"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        else:
            # Config par défaut
            return {"volume": 90, "wifi_priority": []}
    except Exception as e:
        print(f"⚠️ Erreur chargement config: {e}")
        return {"volume": 90, "wifi_priority": []}


def save_config(config_data):
    """Sauvegarde la configuration dans config.json"""
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE) or ".", exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config_data, f, indent=2)
        print(f"✅ Configuration sauvegardée : {config_data}")
        return True
    except Exception as e:
        print(f"❌ Erreur sauvegarde config: {e}")
        return False


def get_local_ip():
    """Récupère l'IP locale du Raspberry Pi"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"


def restart_alice_service():
    """Redémarre le service Alice pour appliquer les changements"""
    try:
        subprocess.run(["sudo", "systemctl", "restart", "alice.service"], check=True)
        return True
    except Exception as e:
        print(f"⚠️ Impossible de redémarrer alice.service: {e}")

def enable_wifi_setup():
    """Active le mode Hotspot pour la configuration WiFi"""
    try:
        # On lance le script en arrière-plan car il va couper le réseau
        subprocess.Popen(["sudo", "bash", "/home/alice/autohotspot.sh", "force"])
        return True
    except Exception as e:
        print(f"⚠️ Impossible de lancer le hotspot: {e}")
        return False


def get_audio_files():
    """Liste tous les fichiers audio dans /home/alice/media/audio"""
    audio_dir = "/home/alice/media/audio"
    
    # Fallback pour développement
    if not os.path.exists(audio_dir):
        audio_dir = "./media/audio"
        os.makedirs(audio_dir, exist_ok=True)
    
    try:
        files = []
        if os.path.exists(audio_dir):
            for filename in sorted(os.listdir(audio_dir)):
                filepath = os.path.join(audio_dir, filename)
                if os.path.isfile(filepath):
                    # Calculer la taille du fichier
                    size_bytes = os.path.getsize(filepath)
                    size_mb = size_bytes / (1024 * 1024)
                    
                    files.append({
                        'name': filename,
                        'size': f"{size_mb:.2f} MB",
                        'size_bytes': size_bytes
                    })
        return files
    except Exception as e:
        print(f"⚠️ Erreur lors du listage des fichiers: {e}")
        return []


def delete_audio_file(filename):
    """Supprime un fichier audio"""
    audio_dir = "/home/alice/media/audio"
    
    # Fallback pour développement
    if not os.path.exists(audio_dir):
        audio_dir = "./media/audio"
    
    try:
        filepath = os.path.join(audio_dir, filename)
        
        # Vérification de sécurité : le fichier doit être dans le dossier audio
        if not filepath.startswith(audio_dir):
            return False, "Chemin invalide"
        
        if os.path.exists(filepath) and os.path.isfile(filepath):
            os.remove(filepath)
            print(f"🗑️ Fichier supprimé : {filename}")
            return True, f"Fichier {filename} supprimé avec succès"
        else:
            return False, "Fichier introuvable"
    except Exception as e:
        print(f"❌ Erreur suppression : {e}")
        return False, str(e)


# Template HTML avec design moderne
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🔊 Racontine - Contrôle</title>
    
    <!-- Mode hors-ligne : Polices système -->
    <style>
        :root {
            --primary: #9d4edd;
            --primary-glow: #c77dff;
            --secondary: #3c096c;
            --bg-dark: #10002b;
            --text-white: #ffffff;
            --text-gray: #e0e0e0;
            --glass-bg: rgba(255, 255, 255, 0.05);
            --glass-border: rgba(255, 255, 255, 0.1);
            --success: #00b894;
            --danger: #ff7675;
            --warning: #f5a623;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg-dark);
            color: var(--text-white);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
            overflow-x: hidden;
        }
        
        /* Background Animation */
        .background-glow {
            position: fixed;
            width: 600px;
            height: 600px;
            background: radial-gradient(circle, var(--primary-glow) 0%, transparent 70%);
            opacity: 0.2;
            top: -10%;
            right: -10%;
            filter: blur(80px);
            z-index: -1;
            animation: float 10s infinite ease-in-out;
        }
        
        .background-glow::after {
            content: '';
            position: absolute;
            width: 500px;
            height: 500px;
            background: radial-gradient(circle, #4361ee 0%, transparent 70%);
            top: 50%;
            left: -50%;
            animation: float 15s infinite reverse ease-in-out;
        }
        
        @keyframes float {
            0% { transform: translate(0, 0); }
            50% { transform: translate(-20px, 20px); }
            100% { transform: translate(0, 0); }
        }
        
        .container {
            width: 100%;
            max-width: 500px;
            display: flex;
            flex-direction: column;
            gap: 1.5rem;
            z-index: 10;
        }
        
        .glass-panel {
            background: var(--glass-bg);
            border: 1px solid var(--glass-border);
            border-radius: 20px;
            padding: 2rem;
            text-align: center;
            backdrop-filter: blur(20px);
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        }
        
        h1 {
            font-size: 2rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
        }
        
        h1 span {
            color: var(--primary-glow);
        }
        
        .subtitle {
            color: var(--text-gray);
            font-weight: 300;
            margin-bottom: 2rem;
        }
        
        .volume-display {
            font-size: 4em;
            font-weight: 700;
            color: var(--primary-glow);
            margin: 1rem 0;
            text-shadow: 0 0 20px rgba(157, 78, 221, 0.5);
        }
        
        /* Custom Range Slider */
        .slider-container {
            width: 100%;
            margin: 2rem 0;
            position: relative;
        }
        
        input[type=range] {
            -webkit-appearance: none;
            width: 100%;
            height: 8px;
            border-radius: 4px;
            background: rgba(255, 255, 255, 0.1);
            outline: none;
        }

        input[type=range]::-webkit-slider-thumb {
            -webkit-appearance: none;
            width: 28px;
            height: 28px;
            border-radius: 50%;
            background: var(--primary-glow);
            cursor: pointer;
            box-shadow: 0 0 15px rgba(199, 125, 255, 0.6);
            transition: transform 0.2s;
            margin-top: -10px; /* Center thumb */
        }
        
        input[type=range]::-webkit-slider-runnable-track {
             width: 100%;
            height: 8px;
            cursor: pointer;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 4px;
        }

        input[type=range]:active::-webkit-slider-thumb {
            transform: scale(1.2);
        }
        
        .volume-labels {
            display: flex;
            justify-content: space-between;
            margin-top: 15px;
            color: var(--text-gray);
            font-size: 0.9em;
            font-weight: 500;
        }
        
        .quick-buttons {
            display: flex;
            justify-content: center;
            gap: 10px;
            margin-bottom: 1rem;
            flex-wrap: wrap;
        }
        
        .quick-btn {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--glass-border);
            color: var(--text-white);
            padding: 0.6rem 1rem;
            border-radius: 12px;
            cursor: pointer;
            transition: all 0.2s;
            font-family: inherit;
            flex: 1;
            min-width: 60px;
        }
        
        .quick-btn:hover {
            background: rgba(157, 78, 221, 0.3);
            border-color: var(--primary-glow);
            transform: translateY(-2px);
        }
        
        .btn {
            background: var(--primary);
            border: none;
            color: white;
            padding: 1rem 2rem;
            border-radius: 12px;
            cursor: pointer;
            font-weight: 500;
            font-family: inherit;
            width: 100%;
            font-size: 1.1em;
            transition: all 0.2s;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        }
        
        .btn:hover {
            background: var(--primary-glow);
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(157, 78, 221, 0.4);
        }
        
        .status {
            padding: 1rem;
            border-radius: 12px;
            margin-top: 1rem;
            font-weight: 500;
            display: none;
            animation: slideUp 0.3s ease-out;
        }
        
        .status.success {
            background: rgba(0, 184, 148, 0.2);
            border: 1px solid var(--success);
            color: #55efc4;
        }
        
        .status.error {
            background: rgba(255, 118, 117, 0.2);
            border: 1px solid var(--danger);
            color: #fab1a0;
        }
        
        /* Media Section */
        .media-section {
            margin-top: 2rem;
            border-top: 1px solid var(--glass-border);
            padding-top: 2rem;
        }
        
        .media-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
        }
        
        h2 {
            font-size: 1.2rem;
            color: var(--text-white);
        }
        
        .media-count {
            background: rgba(255, 255, 255, 0.1);
            padding: 2px 10px;
            border-radius: 20px;
            font-size: 0.8em;
            color: var(--primary-glow);
        }
        
        .media-list {
            max-height: 300px;
            overflow-y: auto;
            background: rgba(0, 0, 0, 0.2);
            border-radius: 12px;
            padding: 0.5rem;
        }
        
        .media-list::-webkit-scrollbar {
             width: 6px;
        }
        .media-list::-webkit-scrollbar-track {
            background: rgba(0, 0, 0, 0.1);
        }
        .media-list::-webkit-scrollbar-thumb {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 3px;
        }
        
        .media-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.8rem 1rem;
            margin-bottom: 5px;
            border-radius: 8px;
            transition: background 0.2s;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }
        
        .media-item:hover {
            background: rgba(255, 255, 255, 0.05);
        }
        
        .media-info {
            text-align: left;
            flex: 1;
            overflow: hidden;
        }
        
        .media-name {
            font-weight: 500;
            color: var(--text-white);
            margin-bottom: 3px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        
        .media-size {
            font-size: 0.8em;
            color: var(--text-gray);
        }
        
        .delete-btn {
            background: none;
            border: none;
            color: rgba(255, 255, 255, 0.4);
            cursor: pointer;
            padding: 5px 10px;
            font-size: 1.1em;
            transition: all 0.2s;
        }
        
        .delete-btn:hover {
             color: var(--danger);
             background: rgba(255, 118, 117, 0.1);
             border-radius: 8px;
        }
        
        .empty-media {
            padding: 2rem;
            color: var(--text-gray);
            font-style: italic;
        }
        
        .add-media-btn {
            display: block;
            margin-top: 1rem;
            background: linear-gradient(135deg, #00b894 0%, #00cec9 100%);
            color: white;
            text-decoration: none;
            padding: 1rem;
            border-radius: 12px;
            font-weight: 500;
            transition: transform 0.2s;
             box-shadow: 0 4px 15px rgba(0, 184, 148, 0.3);
        }
        
        .add-media-btn:hover {
             transform: translateY(-2px);
             box-shadow: 0 6px 20px rgba(0, 184, 148, 0.4);
        }
        
        .wifi-btn {
            background: transparent;
            border: 1px solid var(--warning);
            color: var(--warning);
            margin-top: 1rem;
            padding: 0.8rem;
            border-radius: 12px;
            width: 100%;
            cursor: pointer;
            font-family: inherit;
            font-weight: 500;
            transition: all 0.2s;
        }
        
        .wifi-btn:hover {
             background: rgba(245, 166, 35, 0.1);
             transform: translateY(-2px);
        }
        
        .info-box {
            margin-top: 2rem;
            text-align: left;
            font-size: 0.9em;
            color: var(--text-gray);
            border-top: 1px solid var(--glass-border);
            padding-top: 1rem;
        }
        
        @keyframes slideUp {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
    </style>
</head>
<body>
    <div class="background-glow"></div>

    <div class="container">
        <div class="glass-panel">
            <h1>Racontine <span>Contrôle</span></h1>
            <p class="subtitle">Gestion du volume et des médias</p>
            
            <div class="volume-display" id="volumeDisplay">{{ current_volume }}%</div>
            
            <div class="quick-buttons">
                <button class="quick-btn" onclick="setVolume(25)">25%</button>
                <button class="quick-btn" onclick="setVolume(50)">50%</button>
                <button class="quick-btn" onclick="setVolume(75)">75%</button>
                <button class="quick-btn" onclick="setVolume(100)">100%</button>
            </div>
            
            <div class="slider-container">
                <input type="range" id="volumeSlider" min="0" max="100" value="{{ current_volume }}" 
                       oninput="updateVolumeDisplay(this.value)">
                <div class="volume-labels">
                    <span>🔇 Muet</span>
                    <span>🔊 Max</span>
                </div>
            </div>
            
            <button class="btn" onclick="saveVolume()">💾 Sauvegarder (Redémarre)</button>
            
            <div id="status" class="status"></div>
        </div>

        <div class="glass-panel">
            <div class="media-header">
                <h2>📚 Bibliothèque</h2>
                <span class="media-count" id="mediaCount">{{ audio_files|length }}</span>
            </div>
            
            <div class="media-list" id="mediaList">
                {% if audio_files %}
                    {% for file in audio_files %}
                    <div class="media-item" id="media-{{ loop.index }}">
                        <div class="media-info">
                            <div class="media-name">🎵 {{ file.name }}</div>
                            <div class="media-size">{{ file.size }}</div>
                        </div>
                        <button class="delete-btn" data-filename="{{ file.name }}" onclick="deleteMedia(this.getAttribute('data-filename'), {{ loop.index }})" title="Supprimer">
                            🗑️
                        </button>
                    </div>
                    {% endfor %}
                {% else %}
                    <div class="empty-media">
                        📭 Aucun fichier audio pour le moment
                    </div>
                {% endif %}
            </div>
            
            <a href="https://lumios-le-jeu.github.io/alice-media/" target="_blank" class="add-media-btn">
                ➕ Ajouter / Générer des Disques
            </a>
            
            <button class="wifi-btn" onclick="startWifiSetup()">📶 Configurer WiFi</button>
        </div>
        
        <div class="info-box">
            <p><strong>IP:</strong> {{ server_ip }}:{{ server_port }}</p>
        </div>
    </div>
    
    <script>
        function updateVolumeDisplay(value) {
            document.getElementById('volumeDisplay').innerText = value + '%';
        }
        
        function setVolume(value) {
            document.getElementById('volumeSlider').value = value;
            updateVolumeDisplay(value);
        }
        
        async function saveVolume() {
            const volume = document.getElementById('volumeSlider').value;
            const statusDiv = document.getElementById('status');
            
            statusDiv.style.display = 'none';
            
            try {
                const response = await fetch('/save', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ volume: parseInt(volume) })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    statusDiv.className = 'status success';
                    statusDiv.innerText = '✅ ' + data.message + ' Redémarrage...';
                } else {
                    statusDiv.className = 'status error';
                    statusDiv.innerText = '❌ Erreur: ' + data.message;
                }
                
                statusDiv.style.display = 'block';
                
            } catch (error) {
                statusDiv.className = 'status error';
                statusDiv.innerText = '❌ Erreur de connexion: ' + error.message;
                statusDiv.style.display = 'block';
            }
        }
        
        async function startWifiSetup() {
            if (!confirm("⚠️ ATTENTION : Cela va couper la connexion actuelle et activer le mode Hotspot.\\n\\nVous devrez vous connecter au WiFi 'ALICE_SETUP' et aller sur http://192.168.50.1 pour configurer le réseau.\\n\\nVoulez-vous continuer ?")) {
                return;
            }
            
            const statusDiv = document.getElementById('status');
            statusDiv.style.display = 'none';
            statusDiv.className = 'status success';
            statusDiv.innerText = '⏳ Activation du mode Hotspot...';
            statusDiv.style.display = 'block';
            
            // Ouvrir la page de configuration dans un nouvel onglet
            window.open('http://192.168.50.1/', '_blank');
            
            try {
                await fetch('/wifi-setup', { method: 'POST' });
            } catch (e) {
                // On ignore l'erreur car la connexion va couper
            }
        }
        
        async function deleteMedia(filename, index) {
            if (!confirm(`Êtes-vous sûr de vouloir supprimer "${filename}" ?`)) {
                return;
            }
            
            const statusDiv = document.getElementById('status');
            statusDiv.style.display = 'none';
            
            try {
                const response = await fetch('/delete', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ filename: filename })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    const mediaItem = document.getElementById('media-' + index);
                    if (mediaItem) {
                        mediaItem.style.opacity = '0';
                        setTimeout(() => {
                            mediaItem.remove();
                            const remaining = document.querySelectorAll('.media-item').length;
                            document.getElementById('mediaCount').innerText = remaining;
                            if (remaining === 0) {
                                document.getElementById('mediaList').innerHTML = 
                                    '<div class="empty-media">📭 Aucun fichier audio pour le moment</div>';
                            }
                        }, 200);
                    }
                    statusDiv.className = 'status success';
                    statusDiv.innerText = '✅ ' + data.message;
                } else {
                    statusDiv.className = 'status error';
                    statusDiv.innerText = '❌ Erreur: ' + data.message;
                }
                statusDiv.style.display = 'block';
            } catch (error) {
                statusDiv.className = 'status error';
                statusDiv.innerText = '❌ Erreur de connexion: ' + error.message;
                statusDiv.style.display = 'block';
            }
        }
        
        // Keyboard shortcuts
        document.addEventListener('keydown', function(e) {
            const slider = document.getElementById('volumeSlider');
            if (e.key === 'ArrowUp' || e.key === '+') {
                slider.value = Math.min(100, parseInt(slider.value) + 5);
                updateVolumeDisplay(slider.value);
            } else if (e.key === 'ArrowDown' || e.key === '-') {
                slider.value = Math.max(0, parseInt(slider.value) - 5);
                updateVolumeDisplay(slider.value);
            } else if (e.key === 'Enter') {
                saveVolume();
            }
        });
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    """Page principale de contrôle du volume"""
    config = load_config()
    current_volume = config.get("volume", 90)
    local_ip = get_local_ip()
    audio_files = get_audio_files()
    
    return render_template_string(
        HTML_TEMPLATE,
        current_volume=current_volume,
        server_ip=local_ip,
        server_port=DEFAULT_PORT,
        audio_files=audio_files
    )


@app.route('/save', methods=['POST'])
def save():
    """API pour sauvegarder le volume"""
    try:
        data = request.get_json()
        volume = int(data.get('volume', 90))
        
        # Validation
        if not 0 <= volume <= 100:
            return jsonify({
                'success': False,
                'message': 'Le volume doit être entre 0 et 100'
            })
        
        # Charger la config existante
        config = load_config()
        config['volume'] = volume
        
        # Sauvegarder
        if save_config(config):
            # Redémarrer Alice pour appliquer
            restart_alice_service()
            
            return jsonify({
                'success': True,
                'message': f'Volume réglé à {volume}%.'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Erreur lors de la sauvegarde'
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        })


@app.route('/api/volume', methods=['GET'])
def get_volume():
    """API pour récupérer le volume actuel"""
    config = load_config()
    return jsonify({
        'volume': config.get('volume', 90)
    })


@app.route('/delete', methods=['POST'])
def delete():
    """API pour supprimer un fichier audio"""
    try:
        data = request.get_json()
        filename = data.get('filename', '')
        
        if not filename:
            return jsonify({
                'success': False,
                'message': 'Nom de fichier manquant'
            })
        
        success, message = delete_audio_file(filename)
        
        return jsonify({
            'success': success,
            'message': message
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        })


@app.route('/wifi-setup', methods=['POST'])
def wifi_setup():
    """API pour activer le mode configuration WiFi"""
    if enable_wifi_setup():
        return jsonify({
            'success': True,
            'message': 'Mode Hotspot activé. Connectez-vous au WiFi "ALICE_SETUP".'
        })
    else:
        return jsonify({
            'success': False,
            'message': 'Erreur lors du lancement du hotspot'
        })


if __name__ == '__main__':
    print("=" * 50)
    print("🔊 RACONTINE_SON - Serveur de contrôle du volume")
    print("=" * 50)
    
    local_ip = get_local_ip()
    print(f"📡 IP locale: {local_ip}")
    print(f"🔗 URL Locale: http://racontine.local:{DEFAULT_PORT} (Recommandé)")
    print(f"🌐 URL Directe: http://{local_ip}:{DEFAULT_PORT}")
    print(f"📁 Fichier config: {CONFIG_FILE}")
    print("=" * 50)
    print("Appuyez sur CTRL+C pour arrêter\n")
    
    # Lancement du serveur
    app.run(host='0.0.0.0', port=DEFAULT_PORT, debug=False)
