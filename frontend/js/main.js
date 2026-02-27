const joinScreen = document.getElementById('join-screen');
const conferenceScreen = document.getElementById('conference-screen');
const joinBtn = document.getElementById('join-btn');
const roomIdInput = document.getElementById('room-id');
const usernameInput = document.getElementById('username');
const userRoleSelect = document.getElementById('user-role');
const sessionTitle = document.getElementById('session-title');
const localVideo = document.getElementById('local-video');
const remoteVideo = document.getElementById('remote-video');
const remoteLabel = document.getElementById('remote-label');
const agentControls = document.getElementById('agent-controls');
const captureGallery = document.getElementById('capture-gallery');

const toggleAudioBtn = document.getElementById('toggle-audio-btn');
const toggleVideoBtn = document.getElementById('toggle-video-btn');
const leaveBtn = document.getElementById('leave-btn');

const chatBox = document.getElementById('chat-box');
const chatInput = document.getElementById('chat-message');
const sendChatBtn = document.getElementById('send-chat-btn');

let localStream;
let ws;
let roomId;
let clientId;
let username;
let userRole;
let peerConnection;
let accessToken = "";
let iceCandidateQueue = [];
let isInitializing = false;

const rtcConfig = {
    iceServers: [
        { urls: 'stun:stun.l.google.com:19302' },
        { urls: 'stun:stun1.l.google.com:19302' },
        { urls: 'stun:stun2.l.google.com:19302' },
        { urls: 'stun:stun3.l.google.com:19302' },
        { urls: 'stun:stun4.l.google.com:19302' }
    ],
    iceCandidatePoolSize: 10
};

function generateId() {
    return Math.random().toString(36).substring(2, 15);
}

joinBtn.addEventListener('click', async () => {
    roomId = roomIdInput.value.trim();
    username = usernameInput.value.trim();
    userRole = userRoleSelect.value;
    
    if (!roomId || !username) {
        alert("Please enter Room ID and Name.");
        return;
    }

    clientId = generateId();
    sessionTitle.innerText = `KYC Session: ${roomId} (${userRole})`;

    try {
        accessToken = prompt("Please enter JWT Token:");
        if (!accessToken) return;

        localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
        localVideo.srcObject = localStream;
        
        joinScreen.classList.add('hidden');
        conferenceScreen.classList.remove('hidden');

        if (userRole === 'agent') {
            agentControls.classList.remove('hidden');
        }

        connectWebSocket();
    } catch (err) {
        console.error("Media access error:", err);
        alert("Camera/Mic access denied.");
    }
});

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.hostname;
    const port = window.location.port ? `:${window.location.port}` : '';
    const wsUrl = `${protocol}//${host}${port}/ws/${roomId}/${clientId}?token=${accessToken}`;
    
    console.log(`[WS] Connecting to ${wsUrl}`);
    ws = new WebSocket(wsUrl);

    ws.onmessage = async (event) => {
        const message = JSON.parse(event.data);
        
        switch (message.type) {
            case 'peer-joined':
                console.log("[P2P] Other peer joined. Initiating connection...");
                if (!peerConnection && !isInitializing) await initPeerConnection(true);
                break;
            case 'offer':
                console.log("[P2P] Received offer.");
                if (!peerConnection && !isInitializing) await initPeerConnection(false);
                await handleOffer(message.sdp);
                break;
            case 'answer':
                console.log("[P2P] Received answer.");
                await handleAnswer(message.sdp);
                break;
            case 'ice-candidate':
                handleRemoteCandidate(message.candidate);
                break;
            case 'media-status':
                remoteLabel.innerText = message.micEnabled ? "Peer Connected" : "Peer Muted";
                remoteLabel.style.color = message.micEnabled ? "white" : "#ff4444";
                break;
            case 'close-session':
            case 'peer-left':
                console.log("[P2P] Session terminated by peer. Cleaning up...");
                cleanupAndExit(false); 
                break;
            case 'chat':
                appendChatMessage(message.username, message.text, false);
                break;
        }
    };

    ws.onclose = (e) => {
        if (e.code === 1008) alert("Security Check Failed: " + e.reason);
    };
}

async function initPeerConnection(isInitiator) {
    if (peerConnection || isInitializing) return;
    isInitializing = true;
    
    console.log("[P2P] Initializing RTCPeerConnection...");
    peerConnection = new RTCPeerConnection(rtcConfig);
    
    localStream.getTracks().forEach(track => peerConnection.addTrack(track, localStream));

    peerConnection.ontrack = (event) => {
        console.log("[P2P] Remote track attached.");
        remoteVideo.srcObject = event.streams[0];
        remoteLabel.innerText = "Peer Connected";
        remoteVideo.play().catch(e => {});
    };

    peerConnection.onicecandidate = (event) => {
        if (event.candidate && ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ice-candidate', candidate: event.candidate }));
        }
    };

    if (isInitiator) {
        const offer = await peerConnection.createOffer();
        await peerConnection.setLocalDescription(offer);
        ws.send(JSON.stringify({ type: 'offer', sdp: peerConnection.localDescription }));
    }
    
    isInitializing = false;
}

async function handleOffer(sdp) {
    if (!peerConnection) return;
    await peerConnection.setRemoteDescription(new RTCSessionDescription(sdp));
    const answer = await peerConnection.createAnswer();
    await peerConnection.setLocalDescription(answer);
    ws.send(JSON.stringify({ type: 'answer', sdp: peerConnection.localDescription }));
    processQueuedCandidates();
}

async function handleAnswer(sdp) {
    if (peerConnection && !peerConnection.remoteDescription) {
        await peerConnection.setRemoteDescription(new RTCSessionDescription(sdp));
        processQueuedCandidates();
    }
}

function handleRemoteCandidate(candidate) {
    if (peerConnection && peerConnection.remoteDescription && peerConnection.remoteDescription.type) {
        peerConnection.addIceCandidate(new RTCIceCandidate(candidate)).catch(e => {});
    } else {
        iceCandidateQueue.push(candidate);
    }
}

function processQueuedCandidates() {
    if (!peerConnection) return;
    while (iceCandidateQueue.length > 0) {
        const candidate = iceCandidateQueue.shift();
        peerConnection.addIceCandidate(new RTCIceCandidate(candidate)).catch(e => {});
    }
}

function cleanupAndExit(notifyPeer = true) {
    // 1. Blackout
    if (localVideo) { localVideo.pause(); localVideo.srcObject = null; localVideo.load(); }
    if (remoteVideo) { remoteVideo.pause(); remoteVideo.srcObject = null; remoteVideo.load(); }

    // 2. Tracks
    if (localStream) {
        localStream.getTracks().forEach(track => { track.stop(); track.enabled = false; });
    }

    // 3. Notify & Wait
    if (notifyPeer && ws && ws.readyState === WebSocket.OPEN) {
        try {
            ws.send(JSON.stringify({ type: 'close-session' }));
        } catch(e) {}
        setTimeout(() => finalizeCleanup(), 300);
    } else {
        finalizeCleanup();
    }
}

function finalizeCleanup() {
    if (peerConnection) { peerConnection.close(); peerConnection = null; }
    if (ws) { ws.onclose = null; ws.close(); }
    location.reload(); 
}

window.captureImage = async (label) => {
    if (!remoteVideo.srcObject) { alert("No remote video!"); return; }
    const canvas = document.createElement('canvas');
    canvas.width = remoteVideo.videoWidth; canvas.height = remoteVideo.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(remoteVideo, 0, 0, canvas.width, canvas.height);
    const dataUrl = canvas.toDataURL('image/png');
    try {
        const res = await fetch('/api/session/capture', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${accessToken}` },
            body: JSON.stringify({ room_id: roomId, label: label, image_data: dataUrl })
        });
        if (res.ok) {
            const item = document.createElement('div');
            item.className = 'capture-item';
            item.innerHTML = `<img src="${dataUrl}"><p>${label} - Saved</p>`;
            captureGallery.prepend(item);
        }
    } catch (err) { console.error(err); }
};

function appendChatMessage(user, text, isSelf) {
    const div = document.createElement('div');
    div.className = `chat-message ${isSelf ? 'self' : ''}`;
    div.innerText = `${user}: ${text}`;
    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight;
}

sendChatBtn.addEventListener('click', () => {
    const text = chatInput.value.trim();
    if (text && ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'chat', username: username, text: text }));
        appendChatMessage("You", text, true);
        chatInput.value = '';
    }
});

toggleAudioBtn.addEventListener('click', () => {
    const track = localStream.getAudioTracks()[0];
    track.enabled = !track.enabled;
    const isEnabled = track.enabled;
    toggleAudioBtn.innerText = isEnabled ? "Mute Mic" : "Unmute Mic";
    toggleAudioBtn.classList.toggle('danger', !isEnabled);
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'media-status', micEnabled: isEnabled }));
    }
});

toggleVideoBtn.addEventListener('click', () => {
    const track = localStream.getVideoTracks()[0];
    track.enabled = !track.enabled;
    toggleVideoBtn.innerText = track.enabled ? "Stop Camera" : "Start Camera";
});

leaveBtn.addEventListener('click', () => { 
    if (confirm("End KYC Session?")) cleanupAndExit(true);
});