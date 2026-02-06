/* Configuration State */
let REPO_OWNER = 'Racontine';
let REPO_NAME = 'commun';
const BRANCH = 'main'; // Could be dynamic too, but main is standard

/* DOM Elements */
const repoOwnerInput = document.getElementById('repoOwner');
const repoNameInput = document.getElementById('repoName');
const tokenInput = document.getElementById('githubToken');
const saveConfigBtn = document.getElementById('saveConfigBtn');
const tokenStatus = document.getElementById('tokenStatus');

const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const uploadSection = document.querySelector('.upload-section');
const resultSection = document.getElementById('resultSection');
const progressContainer = document.getElementById('progressContainer');
const progressFill = document.getElementById('progressFill');
const progressText = document.getElementById('progressText');
const qrContainer = document.getElementById('qrcode');
const uploadedFilename = document.getElementById('uploadedFilename');
const toast = document.getElementById('toast');

/* Storage & Library DOM */
const storageBox = document.getElementById('storageBox');
const storageValue = document.getElementById('storageValue');
const storageFill = document.getElementById('storageFill');
const storageTime = document.getElementById('storageTime');
const libraryList = document.getElementById('libraryList');
const searchInput = document.getElementById('searchInput');
const starFilter = document.getElementById('starFilter');
const typeFilter = document.getElementById('typeFilter');
const toggleConfigBtn = document.getElementById('toggleConfigBtn');
const configForm = document.getElementById('configForm');

/* State */
let availableFiles = [];
let ratings = {};

document.addEventListener('DOMContentLoaded', () => {
    loadConfig();

    toggleConfigBtn.addEventListener('click', () => {
        configForm.classList.toggle('hidden');
    });

    /* Token Help Modal Logic */
    const helpBtn = document.getElementById('tokenHelpBtn');
    const helpModal = document.getElementById('tokenHelpModal');
    const closeBtn = document.querySelector('.close-modal');

    if (helpBtn && helpModal) {
        helpBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            helpModal.classList.remove('hidden');
        });
    }

    if (closeBtn && helpModal) {
        closeBtn.addEventListener('click', () => {
            helpModal.classList.add('hidden');
        });
    }

    window.addEventListener('click', (e) => {
        if (e.target === helpModal) {
            helpModal.classList.add('hidden');
        }
    });
});

saveConfigBtn.addEventListener('click', () => {
    const owner = repoOwnerInput.value.trim();
    const repo = repoNameInput.value.trim();
    const token = tokenInput.value.trim();

    if (owner && repo && token) {
        localStorage.setItem('gh_owner', owner);
        localStorage.setItem('gh_repo', repo);
        localStorage.setItem('gh_pat', token);

        loadConfig(); // Reload state
        showToast('Configuration sauvegardée !');
    } else {
        showToast('Veuillez remplir tous les champs.');
    }
});

function loadConfig() {
    REPO_OWNER = localStorage.getItem('gh_owner') || 'Racontine';
    REPO_NAME = localStorage.getItem('gh_repo') || 'commun';
    const token = localStorage.getItem('gh_pat') || '';

    // Fill inputs
    if (REPO_OWNER) repoOwnerInput.value = REPO_OWNER;
    if (REPO_NAME) repoNameInput.value = REPO_NAME;
    if (token) tokenInput.value = token;

    if (REPO_OWNER && REPO_NAME && token) {
        validateToken(token);
        initLibrary(token);
        fetchRepoUsage(token);
        // Hide config by default if connected
        if (configForm) configForm.classList.add('hidden');
    } else {
        if (configForm) configForm.classList.remove('hidden');
        if (toggleConfigBtn) toggleConfigBtn.style.color = '#ff7675'; // Rouge par défaut
        libraryList.innerHTML = '<div class="loader">Configurez vos accès (Pseudo, Repo, Token) à gauche pour commencer.</div>';
    }
}

/* --- LIBRARY LOGIC --- */
async function initLibrary(token) {
    if (!REPO_OWNER || !REPO_NAME) return;

    libraryList.innerHTML = '<div class="loader">Chargement des sons...</div>';

    // 1. Fetch Ratings
    try {
        const timestamp = new Date().getTime();
        const r = await fetch(`https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/contents/ratings.json?cb=${timestamp}`, {
            headers: { 'Authorization': `Bearer ${token}`, 'If-None-Match': '' }
        });
        if (r.ok) {
            const data = await r.json();
            const content = b64DecodeUnicode(data.content);
            ratings = JSON.parse(content);
        } else {
            ratings = {};
        }
    } catch (e) {
        console.warn("Could not load ratings:", e);
        ratings = {};
    }

    // 2. Fetch Files Recursive
    availableFiles = [];
    try {
        const r = await fetch(`https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/git/trees/${BRANCH}?recursive=1`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (r.ok) {
            const result = await r.json();
            availableFiles = result.tree
                .filter(item => {
                    if (item.type !== 'blob') return false;
                    const path = item.path.toLowerCase();
                    const isMedia = path.startsWith('media/audio/') || path.startsWith('media/video/');
                    const isImage = path.endsWith('.png') || path.endsWith('.jpg') || path.endsWith('.jpeg') || path.endsWith('_qr.png');
                    return isMedia && !isImage;
                })
                .map(item => ({
                    name: item.path.split('/').pop(),
                    url: `https://raw.githubusercontent.com/${REPO_OWNER}/${REPO_NAME}/${BRANCH}/${item.path}`,
                    sha: item.sha,
                    path: item.path
                }));
            renderLibrary();
        } else {
            throw new Error(`Erreur ${r.status}: ${r.statusText}`);
        }
    } catch (e) {
        libraryList.innerHTML = `<div class="loader" style="color:#ff7675">${e.message}</div>`;
    }
}

async function fetchRepoUsage(token) {
    if (!REPO_OWNER || !REPO_NAME) return;
    try {
        const r = await fetch(`https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (r.ok) {
            const data = await r.json();
            const sizeKB = parseInt(data.size) || 0;
            const sizeMBNum = sizeKB / 1024;
            const sizeMBText = sizeMBNum.toFixed(1);
            const limitMB = 1000;
            const percent = Math.min((sizeKB / (limitMB * 1024)) * 100, 100).toFixed(1);

            storageValue.innerText = `${sizeMBText} MB / 1 GB`;
            storageFill.style.width = `${percent}%`;

            // Storage Time Calculation: 1GB = 100h -> 6.0 min/MB
            const remainingMB = Math.max(0, limitMB - sizeMBNum);
            const totalRemainingMin = remainingMB * 6.0;
            const hrs = Math.floor(totalRemainingMin / 60);
            const mins = Math.floor(totalRemainingMin % 60);

            storageTime.innerText = `~ ${hrs}h ${mins}min d'audio restant`;

            if (percent > 90) storageFill.style.backgroundColor = '#ff7675';
            else if (percent > 70) storageFill.style.backgroundColor = '#fdcb6e';
            else storageFill.style.backgroundColor = '#00b894';

            storageBox.classList.remove('hidden');
        }
    } catch (e) {
        console.warn("Repo usage fetch failed", e);
    }
}

function renderLibrary() {
    libraryList.innerHTML = '';

    if (availableFiles.length === 0) {
        libraryList.innerHTML = '<div class="loader">Aucun fichier audio trouvé. Uploadez-en un à gauche !</div>';
        return;
    }

    const term = searchInput ? searchInput.value.toLowerCase() : '';
    const minStars = starFilter ? (parseInt(starFilter.value) || 0) : 0;
    const typeTerm = typeFilter ? typeFilter.value : 'all';

    // Build dynamic folders list
    const folders = new Set();
    availableFiles.forEach(file => {
        const parts = file.path.split('/');
        if (parts.length > 3) { // media/audio/FOLDER/...
            folders.add(parts[2]);
        }
    });

    // Update Type Filter dropdown if it has changed
    if (typeFilter) {
        const currentOptions = Array.from(typeFilter.options).map(o => o.value);
        folders.forEach(folder => {
            if (!currentOptions.includes(folder)) {
                const opt = document.createElement('option');
                opt.value = folder;
                opt.innerText = folder;
                typeFilter.appendChild(opt);
            }
        });
    }

    const filtered = availableFiles.filter(file => {
        const metadata = ratings[file.name] || {};
        const score = typeof metadata === 'number' ? metadata : (metadata.score || 0);
        let type = typeof metadata === 'number' ? 'Livre' : (metadata.type || 'Livre');

        // Check if file is in a subfolder and override type if needed
        const parts = file.path.split('/');
        if (parts.length > 3 && !ratings[file.name]) {
            type = parts[2];
        }

        const matchesName = file.name.toLowerCase().includes(term);
        const matchesStars = (minStars === 5) ? (score === 5) : (score >= minStars);
        const matchesType = (typeTerm === 'all') || (type === typeTerm);

        return matchesName && matchesStars && matchesType;
    });

    if (filtered.length === 0) {
        libraryList.innerHTML = '<div class="loader">Aucun résultat.</div>';
        return;
    }

    filtered.forEach(file => {
        const row = document.createElement('div');
        row.className = 'library-item';

        // Store data for event delegation
        row.dataset.name = file.name;
        row.dataset.url = file.url;
        row.dataset.path = file.path;
        row.dataset.sha = file.sha;

        const metadata = ratings[file.name] || {};
        const score = typeof metadata === 'number' ? metadata : (metadata.score || 0);
        const type = typeof metadata === 'number' ? 'Livre' : (metadata.type || 'Livre');

        row.innerHTML = `
            <div class="item-info action-qr">
                <div class="item-icon">🎵</div>
                <div class="item-column">
                    <div class="item-name" title="${file.name}">${file.name}</div>
                    <span class="item-badge ${type.toLowerCase()} action-toggle-type" 
                          title="Cliquez pour changer le type">${type}</span>
                </div>
            </div>
            <div class="item-right-section">
                <div class="item-rating">
                    ${[1, 2, 3, 4, 5].map(i => `
                        <span class="star ${i <= score ? 'filled' : ''} action-rate" data-value="${i}">★</span>
                    `).join('')}
                </div>
                <button class="download-btn action-download" title="Télécharger l'étiquette">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/>
                    </svg>
                </button>
                <button class="delete-btn action-delete" title="Supprimer">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                    </svg>
                </button>
            </div>
        `;
        libraryList.appendChild(row);
    });
}

// Global Event Delegation for Library
if (libraryList) {
    libraryList.addEventListener('click', (e) => {
        const row = e.target.closest('.library-item');
        if (!row) return;

        const name = row.dataset.name;
        const url = row.dataset.url;
        const path = row.dataset.path;
        const sha = row.dataset.sha;

        // Route actions based on clicked class
        if (e.target.closest('.action-qr')) {
            generateQRFromUrl(url, name);
        } else if (e.target.closest('.action-toggle-type')) {
            toggleFileType(name);
        } else if (e.target.closest('.action-rate')) {
            const val = parseInt(e.target.dataset.value);
            rateFile(name, val);
        } else if (e.target.closest('.action-download')) {
            downloadTag(url, name);
        } else if (e.target.closest('.action-delete')) {
            deleteFile(name, path, sha);
        }
    });
}

if (searchInput) searchInput.addEventListener('input', renderLibrary);
if (starFilter) starFilter.addEventListener('change', renderLibrary);
if (typeFilter) typeFilter.addEventListener('change', renderLibrary);

/* --- TAG DOWNLOAD --- */
async function downloadTag(rawUrl, name) {
    // 1. Check Metadata
    const existing = ratings[name] || {};
    let finalUrl = (existing.shortUrl && existing.shortUrl.length < 50) ? existing.shortUrl : rawUrl;

    // 2. If no short URL, try to generate one locally
    if (finalUrl === rawUrl) {
        showToast("Lien court...");
        const short = await getShortUrl(rawUrl);
        if (short) {
            finalUrl = short;
            saveShortUrl(name, finalUrl);
        }
    }

    // Use a temporary div to render QR
    const tempDiv = document.createElement('div');
    new QRCode(tempDiv, { text: finalUrl, width: 400, height: 400, correctLevel: QRCode.CorrectLevel.H });

    // Wait for QR to render (qrcode.js is synchronous but just in case)
    setTimeout(() => {
        const img = tempDiv.querySelector('img');
        if (img) {
            const link = document.createElement('a');
            link.href = img.src;
            link.download = `${name.split('.')[0]}.png`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            showToast("Étiquette téléchargée !");
        } else {
            showToast("Erreur lors de la génération");
        }
    }, 100);
}

/* --- ACTIONS --- */
async function rateFile(filename, score) {
    const token = localStorage.getItem('gh_pat');
    if (!token || !REPO_OWNER || !REPO_NAME) return;

    // Preserve existing type, default to Livre
    const existing = ratings[filename] || {};
    const type = typeof existing === 'object' ? (existing.type || 'Livre') : 'Livre';

    ratings[filename] = { score: score, type: type };
    renderLibrary();

    try {
        await pushRatings(token);
    } catch (e) {
        console.error("Save rating failed", e);
        showToast("Erreur sauvegarde note");
    }
}

async function toggleFileType(filename) {
    const token = localStorage.getItem('gh_pat');
    if (!token || !REPO_OWNER || !REPO_NAME) return;

    const existing = ratings[filename] || {};
    const currentScore = typeof existing === 'object' ? (existing.score || 0) : existing;
    const currentType = typeof existing === 'object' ? (existing.type || 'Livre') : 'Livre';

    const newType = (currentType === 'Livre') ? 'Chanson' : 'Livre';

    ratings[filename] = { score: currentScore, type: newType };
    renderLibrary();
    showToast(`Type changé en : ${newType}`);

    try {
        await pushRatings(token);
    } catch (e) {
        console.error("Toggle type failed", e);
        showToast("Erreur sauvegarde type");
    }
}

async function pushRatings(token) {
    if (!token || !REPO_OWNER || !REPO_NAME) return;
    try {
        let sha = null;
        try {
            const r = await fetch(`https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/contents/ratings.json`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (r.ok) {
                const data = await r.json();
                sha = data.sha;
            }
        } catch (e) { }

        const content = b64EncodeUnicode(JSON.stringify(ratings, null, 2));
        const body = {
            message: `Update metadata/ratings`,
            content: content,
            branch: BRANCH
        };
        if (sha) body.sha = sha;

        await fetch(`https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/contents/ratings.json`, {
            method: 'PUT',
            headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
    } catch (e) { console.error("Push ratings failed", e); }
}

async function deleteFile(name, path, sha) {
    if (!confirm(`Voulez-vous vraiment supprimer "${name}" ?`)) return;

    const token = localStorage.getItem('gh_pat');
    if (!token || !REPO_OWNER || !REPO_NAME) return;

    availableFiles = availableFiles.filter(f => f.name !== name);
    renderLibrary();

    try {
        const response = await fetch(`https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/contents/${path}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message: `Delete ${name}`,
                sha: sha,
                branch: BRANCH
            })
        });

        if (response.ok) {
            showToast(`${name} supprimé ! 🗑️`);
            fetchRepoUsage(token);
        } else {
            throw new Error(response.statusText);
        }
    } catch (e) {
        showToast(`Erreur suppression: ${e.message}`);
        initLibrary(token);
    }
}

async function generateQRFromUrl(rawUrl, name, size = 0) {
    resetUIForUpload();
    showToast("Génération tag en cours... ⏳");

    // Vérifier si une URL courte existe déjà en cache
    const existing = ratings[name] || {};
    // On accepte toute URL http/https comme valide si elle existe
    if (typeof existing === 'object' && existing.shortUrl && existing.shortUrl.startsWith('http')) {
        updateProgress(100, "Terminé (Cache) !");
        showResult(existing.shortUrl, name);
        return;
    }

    // Sinon, on tente de générer une URL courte
    let finalUrl = rawUrl;
    updateProgress(30, "Génération lien court...");

    const short = await getShortUrl(rawUrl);
    if (short) {
        finalUrl = short;
        saveShortUrl(name, finalUrl);
        showToast("Lien raccourci généré ! ✨");
        updateProgress(100, "Terminé !");
    } else {
        showToast("Échec raccourcisseur : URL standard utilisée ⚠️");
        updateProgress(100, "Terminé (Standard)");
    }

    showResult(finalUrl, name);
}

// Fonction centrale pour raccourcir les URLs avec Fallback
// Fonction centrale pour raccourcir les URLs avec Fallback
async function getShortUrl(rawUrl) {
    // 1. Essai primaire : AllOrigins (Souvent plus stable pour ce type de requête et renvoie du JSON)
    try {
        const target = `https://tinyurl.com/api-create.php?url=${encodeURIComponent(rawUrl)}`;
        const res = await fetch(`https://api.allorigins.win/get?url=${encodeURIComponent(target)}`);
        if (res.ok) {
            const data = await res.json();
            if (data.contents && data.contents.startsWith('http')) return data.contents;
        }
    } catch (e) { console.warn("AllOrigins failed, switching...", e); }

    // 2. Secours : CorsProxy
    try {
        await new Promise(r => setTimeout(r, 500)); // Petit délai avant retry
        const target = `https://tinyurl.com/api-create.php?url=${encodeURIComponent(rawUrl)}`;
        const res = await fetch(`https://corsproxy.io/?${encodeURIComponent(target)}`);
        if (res.ok) {
            const text = await res.text();
            if (text.startsWith('http')) return text;
        }
    } catch (e) { console.warn("CorsProxy failed", e); }

    return null;
}

function saveShortUrl(name, shortUrl) {
    if (typeof ratings[name] !== 'object') {
        ratings[name] = { score: ratings[name] || 0, type: 'Livre' };
    }
    ratings[name].shortUrl = shortUrl;
    const token = localStorage.getItem('gh_pat');
    if (token) pushRatings(token); // Silent background push
}



/* --- AUTH & UPLOAD --- */
async function validateToken(token) {
    if (!token) {
        updateTokenStatus(false);
        return;
    }
    tokenStatus.className = 'status-indicator';
    try {
        const response = await fetch('https://api.github.com/user', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (response.ok) updateTokenStatus(true);
        else updateTokenStatus(false);
    } catch (e) {
        updateTokenStatus(false);
    }
}

function updateTokenStatus(isValid) {
    tokenStatus.className = 'status-indicator';
    const gearBtn = document.getElementById('toggleConfigBtn');

    if (isValid) {
        tokenStatus.classList.add('valid');
        tokenStatus.title = "Token valide";
        if (gearBtn) gearBtn.style.color = '#00b894'; // Vert
    } else {
        tokenStatus.classList.add('invalid');
        tokenStatus.title = "Token invalide";
        if (gearBtn) gearBtn.style.color = '#ff7675'; // Rouge
    }
}

dropZone.addEventListener('click', () => fileInput.click());

['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    dropZone.addEventListener(eventName, preventDefaults, false);
});

function preventDefaults(e) { e.preventDefault(); e.stopPropagation(); }

['dragenter', 'dragover'].forEach(eventName => {
    dropZone.addEventListener(eventName, () => dropZone.classList.add('dragover'), false);
});

['dragleave', 'drop'].forEach(eventName => {
    dropZone.addEventListener(eventName, () => dropZone.classList.remove('dragover'), false);
});

dropZone.addEventListener('drop', (e) => handleFiles(e.dataTransfer.files));
fileInput.addEventListener('change', (e) => handleFiles(e.target.files));

function handleFiles(files) {
    if (files.length > 0) processAndUpload(files[0]);
}

async function processAndUpload(file) {
    const token = localStorage.getItem('gh_pat');
    if (!token || !REPO_OWNER || !REPO_NAME) {
        showToast('Erreur: Configuration incomplète (Token/Repo).');
        return;
    }

    // Certification check
    const isCertified = document.getElementById('certificationCheck').checked;
    if (!isCertified) {
        showToast('Veuillez certifier que l\'audio est bien de vous.');
        return;
    }

    resetUIForUpload();

    try {
        let fileToUpload = file;
        let filename = file.name;
        const ext = filename.split('.').pop().toLowerCase();
        const isAudio = file.type.startsWith('audio/') || ext === 'wav' || ext === 'ogg';
        const isVideo = file.type.startsWith('video/') || ['mp4', 'mpeg', 'avi', 'mov', 'mkv', 'webm'].includes(ext);

        const selectedType = document.querySelector('input[name="uploadType"]:checked').value;

        if ((isAudio || isVideo) && ext !== 'mp3') {
            updateProgress(10, "Compression Audio (64kbps)...");
            try {
                const mp3Blob = await convertToMp3(file);
                const newName = filename.substring(0, filename.lastIndexOf('.')) + ".mp3";
                fileToUpload = new File([mp3Blob], newName, { type: 'audio/mp3' });
                filename = newName;
            } catch (err) {
                if (!isVideo) showToast("Conversion MP3 échouée: Upload original");
            }
        }

        const finalExt = filename.split('.').pop().toLowerCase();
        let folder = 'media/audio';
        if (['mp4', 'mkv', 'avi', 'mov', 'mpeg', 'webm'].includes(finalExt)) {
            folder = 'media/video';
        }
        const sanitizedName = filename.replace(/[^a-zA-Z0-9._-]/g, '_');
        const path = `${folder}/${sanitizedName}`;

        updateProgress(30, "Préparation...");
        const content = await toBase64(fileToUpload);

        let sha = null;
        try {
            const checkReq = await fetch(`https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/contents/${path}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (checkReq.ok) {
                const data = await checkReq.json();
                sha = data.sha;
            }
        } catch (e) { }

        updateProgress(50, "Envoi vers GitHub...");
        const body = {
            message: `Add ${sanitizedName}`,
            content: content,
            branch: BRANCH
        };
        if (sha) body.sha = sha;

        const response = await fetch(`https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/contents/${path}`, {
            method: 'PUT',
            headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });

        if (!response.ok) throw new Error(`Erreur GitHub: ${response.statusText}`);

        updateProgress(80, "Lien court...");
        const rawUrl = `https://raw.githubusercontent.com/${REPO_OWNER}/${REPO_NAME}/${BRANCH}/${path}`;

        let finalUrl = rawUrl;
        const short = await getShortUrl(rawUrl);
        if (short) finalUrl = short;

        updateProgress(90, "Sauvegarde métadonnées...");

        updateProgress(100, "Terminé !");

        // Save metadata locally before pushing ratings.json
        ratings[sanitizedName] = { score: 0, type: selectedType, shortUrl: finalUrl };
        await pushRatings(token);

        showResult(finalUrl, sanitizedName);
        initLibrary(token);
        fetchRepoUsage(token);

    } catch (error) {
        console.error(error);
        showToast(error.message);
        resetApp();
    }
}

function convertToMp3(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = async (e) => {
            try {
                const arrayBuffer = e.target.result;
                const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);
                const mp3Data = encodeBufferToMp3(audioBuffer);
                resolve(new Blob(mp3Data, { type: 'audio/mp3' }));
            } catch (err) { reject(err); }
        };
        reader.onerror = reject;
        reader.readAsArrayBuffer(file);
    });
}

function encodeBufferToMp3(audioBuffer) {
    const channels = 1;
    const sampleRate = audioBuffer.sampleRate;
    const mp3encoder = new lamejs.Mp3Encoder(channels, sampleRate, 64);
    const samples = audioBuffer.getChannelData(0);
    const sampleBlock = new Int16Array(samples.length);
    for (let i = 0; i < samples.length; i++) {
        sampleBlock[i] = samples[i] < 0 ? samples[i] * 0x8000 : samples[i] * 0x7FFF;
    }
    const mp3Data = [];
    const blockSize = 1152;
    for (let i = 0; i < sampleBlock.length; i += blockSize) {
        const chunk = sampleBlock.subarray(i, i + blockSize);
        const mp3buf = mp3encoder.encodeBuffer(chunk);
        if (mp3buf.length > 0) mp3Data.push(mp3buf);
    }
    const endBuf = mp3encoder.flush();
    if (endBuf.length > 0) mp3Data.push(endBuf);
    return mp3Data;
}

function toBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.readAsDataURL(file);
        reader.onload = () => resolve(reader.result.split(',')[1]);
        reader.onerror = reject;
    });
}

function resetUIForUpload() {
    dropZone.classList.add('hidden');
    progressContainer.classList.remove('hidden');
    updateProgress(0, "Démarrage...");
}

function updateProgress(percent, text) {
    progressFill.style.width = `${percent}%`;
    progressText.innerText = text || `${percent}%`;
}

function showResult(url, name) {
    uploadSection.classList.add('hidden');
    resultSection.classList.remove('hidden');
    uploadedFilename.innerText = name;
    qrContainer.innerHTML = '<canvas id="qrCanvas"></canvas>';

    const canvas = document.getElementById('qrCanvas');
    QRCode.toCanvas(canvas, url, {
        width: 200,
        margin: 2,
        color: {
            dark: '#10002b',
            light: '#ffffff'
        },
        errorCorrectionLevel: 'L' // Low pour permettre des URLs plus longues si besoin
    }, function (error) {
        if (error) {
            console.error(error);
            showToast("Erreur QR: URL trop longue ?");
            qrContainer.innerHTML = '<div style="color:red; font-size:0.8rem;">URL trop longue pour le QR Code. Essayez de raccourcir le nom du fichier.</div>';
        }
    });

    const linkContainer = document.createElement('div');
    linkContainer.style.marginTop = '1rem';
    linkContainer.style.fontSize = '0.9rem';
    linkContainer.style.wordBreak = 'break-all';

    const link = document.createElement('a');
    link.href = url;
    link.innerText = url;
    link.target = '_blank';
    link.style.color = '#00b894';

    linkContainer.appendChild(link);
    qrContainer.appendChild(linkContainer);

    // Add Download Tag button to Result Section (outside QR box)
    const existingBtn = resultSection.querySelector('.download-result-btn');
    if (existingBtn) existingBtn.remove();

    const downloadBtn = document.createElement('button');
    const safeName = name.replace(/'/g, "\\'");
    downloadBtn.className = 'download-result-btn';
    downloadBtn.innerHTML = `
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right: 8px;">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/>
        </svg>
        Télécharger l'étiquette
    `;
    downloadBtn.onclick = () => downloadTag(url, safeName);

    // Insert before the filename/reset button
    uploadedFilename.parentNode.insertBefore(downloadBtn, uploadedFilename);
}

function resetApp() {
    uploadSection.classList.remove('hidden');
    dropZone.classList.remove('hidden');
    progressContainer.classList.add('hidden');
    resultSection.classList.add('hidden');
    progressFill.style.width = '0%';
    fileInput.value = '';
}

function showToast(msg) {
    const toast = document.getElementById('toast');
    toast.innerText = msg;
    toast.classList.remove('hidden');
    setTimeout(() => toast.classList.add('hidden'), 3000);
}

/* --- UTILS --- */
function b64EncodeUnicode(str) {
    return btoa(encodeURIComponent(str).replace(/%([0-9A-F]{2})/g, function (match, p1) {
        return String.fromCharCode('0x' + p1);
    }));
}

function b64DecodeUnicode(str) {
    return decodeURIComponent(atob(str).split('').map(function (c) {
        return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
    }).join(''));
}
