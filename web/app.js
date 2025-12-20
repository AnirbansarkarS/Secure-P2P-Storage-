// Configuration
const COORDINATOR_URL = 'http://localhost:8000';
let selectedFile = null;

// DOM Elements
const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');
const uploadForm = document.getElementById('uploadForm');
const fileInfo = document.getElementById('fileInfo');
const uploadBtn = document.getElementById('uploadBtn');
const uploadPassword = document.getElementById('uploadPassword');
const uploadProgress = document.getElementById('uploadProgress');
const uploadProgressFill = document.getElementById('uploadProgressFill');
const uploadProgressText = document.getElementById('uploadProgressText');
const uploadResult = document.getElementById('uploadResult');
const uploadedFileHash = document.getElementById('uploadedFileHash');
const copyHashBtn = document.getElementById('copyHashBtn');

const fileHashInput = document.getElementById('fileHash');
const downloadPassword = document.getElementById('downloadPassword');
const downloadBtn = document.getElementById('downloadBtn');
const downloadProgress = document.getElementById('downloadProgress');
const downloadProgressFill = document.getElementById('downloadProgressFill');
const downloadProgressText = document.getElementById('downloadProgressText');

const statusIndicator = document.getElementById('statusIndicator');
const statusText = document.getElementById('statusText');
const peerCount = document.getElementById('peerCount');
const storageUsed = document.getElementById('storageUsed');
const fileCount = document.getElementById('fileCount');
const networkHealth = document.getElementById('networkHealth');
const peersList = document.getElementById('peersList');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    checkCoordinatorStatus();
    loadNetworkStats();
    setInterval(loadNetworkStats, 10000); // Update every 10 seconds
});

function setupEventListeners() {
    // Upload area drag and drop
    uploadArea.addEventListener('click', () => fileInput.click());
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('drag-over');
    });
    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('drag-over');
    });
    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('drag-over');
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFileSelect(files[0]);
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileSelect(e.target.files[0]);
        }
    });

    uploadBtn.addEventListener('click', handleUpload);
    downloadBtn.addEventListener('click', handleDownload);
    copyHashBtn.addEventListener('click', copyHashToClipboard);
}

function handleFileSelect(file) {
    selectedFile = file;
    fileInfo.innerHTML = `
        <strong>${file.name}</strong><br>
        <small>Size: ${formatBytes(file.size)}</small>
    `;
    uploadForm.style.display = 'block';
    uploadResult.style.display = 'none';
}

async function handleUpload() {
    if (!selectedFile || !uploadPassword.value) {
        showToast('Please select a file and enter a password', 'error');
        return;
    }

    uploadBtn.disabled = true;
    uploadProgress.style.display = 'block';
    uploadResult.style.display = 'none';

    try {
        // Simulate upload progress (in real implementation, this would be actual progress)
        updateProgress(uploadProgressFill, uploadProgressText, 0, 'Encrypting file...');
        await sleep(500);

        updateProgress(uploadProgressFill, uploadProgressText, 30, 'Creating shards...');
        await sleep(500);

        updateProgress(uploadProgressFill, uploadProgressText, 60, 'Distributing to peers...');

        // In a real implementation, you would:
        // 1. Read the file
        // 2. Send it to the backend API for encryption and distribution
        // 3. Get the file hash back

        // For now, we'll simulate the upload
        const formData = new FormData();
        formData.append('file', selectedFile);
        formData.append('password', uploadPassword.value);

        // This would be the actual API call:
        // const response = await fetch(`${COORDINATOR_URL}/upload`, {
        //     method: 'POST',
        //     body: formData
        // });

        updateProgress(uploadProgressFill, uploadProgressText, 100, 'Upload complete!');
        await sleep(500);

        // Simulate file hash (in real implementation, this comes from the server)
        const fileHash = generateMockHash();

        uploadProgress.style.display = 'none';
        uploadResult.style.display = 'block';
        uploadedFileHash.textContent = fileHash;

        showToast('File uploaded successfully!', 'success');

        // Reset form
        setTimeout(() => {
            uploadForm.style.display = 'none';
            uploadResult.style.display = 'none';
            selectedFile = null;
            fileInput.value = '';
            uploadPassword.value = '';
        }, 10000);

    } catch (error) {
        console.error('Upload error:', error);
        showToast('Upload failed: ' + error.message, 'error');
        uploadProgress.style.display = 'none';
    } finally {
        uploadBtn.disabled = false;
    }
}

async function handleDownload() {
    const hash = fileHashInput.value.trim();
    const password = downloadPassword.value;

    if (!hash || !password) {
        showToast('Please enter file hash and password', 'error');
        return;
    }

    downloadBtn.disabled = true;
    downloadProgress.style.display = 'block';

    try {
        updateProgress(downloadProgressFill, downloadProgressText, 0, 'Locating file...');
        await sleep(500);

        updateProgress(downloadProgressFill, downloadProgressText, 30, 'Downloading shards...');
        await sleep(1000);

        updateProgress(downloadProgressFill, downloadProgressText, 70, 'Reconstructing file...');
        await sleep(500);

        updateProgress(downloadProgressFill, downloadProgressText, 90, 'Decrypting...');
        await sleep(500);

        // In a real implementation:
        // const response = await fetch(`${COORDINATOR_URL}/download/${hash}?password=${password}`);
        // const blob = await response.blob();
        // const url = window.URL.createObjectURL(blob);
        // const a = document.createElement('a');
        // a.href = url;
        // a.download = 'downloaded_file';
        // a.click();

        updateProgress(downloadProgressFill, downloadProgressText, 100, 'Download complete!');
        showToast('File downloaded successfully!', 'success');

        setTimeout(() => {
            downloadProgress.style.display = 'none';
            fileHashInput.value = '';
            downloadPassword.value = '';
        }, 2000);

    } catch (error) {
        console.error('Download error:', error);
        showToast('Download failed: ' + error.message, 'error');
        downloadProgress.style.display = 'none';
    } finally {
        downloadBtn.disabled = false;
    }
}

async function checkCoordinatorStatus() {
    try {
        const response = await fetch(`${COORDINATOR_URL}/peers`);
        if (response.ok) {
            statusIndicator.style.background = '#10b981';
            statusText.textContent = 'Connected';
        } else {
            statusIndicator.style.background = '#f59e0b';
            statusText.textContent = 'Limited Connection';
        }
    } catch (error) {
        statusIndicator.style.background = '#ef4444';
        statusText.textContent = 'Disconnected';
    }
}

async function loadNetworkStats() {
    try {
        // Load peers
        const peersResponse = await fetch(`${COORDINATOR_URL}/peers`);
        if (peersResponse.ok) {
            const peers = await peersResponse.json();
            updatePeersList(peers);
            peerCount.textContent = peers.length;

            // Calculate total storage
            const totalStorage = peers.reduce((sum, peer) => sum + (peer.available_storage || 0), 0);
            storageUsed.textContent = `${(totalStorage / 1024).toFixed(2)} GB`;

            // Calculate network health (average reputation)
            const avgReputation = peers.reduce((sum, peer) => sum + peer.reputation, 0) / peers.length;
            networkHealth.textContent = `${(avgReputation * 100).toFixed(0)}%`;
        }
    } catch (error) {
        console.error('Failed to load network stats:', error);
    }
}

function updatePeersList(peers) {
    if (peers.length === 0) {
        peersList.innerHTML = '<p class="empty-state">No peers connected yet...</p>';
        return;
    }

    peersList.innerHTML = peers.map(peer => `
        <div class="peer-item">
            <div class="peer-header">
                <span class="peer-id">${peer.peer_id.substring(0, 16)}...</span>
                <span class="peer-reputation">Rep: ${(peer.reputation * 100).toFixed(0)}%</span>
            </div>
            <div class="peer-details">
                <span>📍 ${peer.ip_address}:${peer.port}</span>
                <span>💾 ${(peer.available_storage / 1024).toFixed(2)} GB</span>
                <span>⏰ ${formatTimestamp(peer.last_seen)}</span>
            </div>
        </div>
    `).join('');
}

function updateProgress(fillElement, textElement, percent, message) {
    fillElement.style.width = `${percent}%`;
    textElement.textContent = message;
}

function copyHashToClipboard() {
    const hash = uploadedFileHash.textContent;
    navigator.clipboard.writeText(hash).then(() => {
        showToast('Hash copied to clipboard!', 'success');
    }).catch(() => {
        showToast('Failed to copy hash', 'error');
    });
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;

    const container = document.getElementById('toastContainer');
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'slideIn 0.3s ease reverse';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

function formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

function formatTimestamp(timestamp) {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = Math.floor((now - date) / 1000);

    if (diff < 60) return 'Just now';
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
}

function generateMockHash() {
    const chars = '0123456789abcdef';
    let hash = '';
    for (let i = 0; i < 64; i++) {
        hash += chars[Math.floor(Math.random() * chars.length)];
    }
    return hash;
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}
