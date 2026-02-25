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
let accessToken = ""; // In real React app, this comes from login state

const rtcConfig = {
    iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
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
        // MOCK LOGIN FOR STATIC DEMO (Real React app calls /api/auth/login)
        // For static demo to work with Secure WS, we need a valid token.
        // I'll assume the user uses Swagger to get a token and we prompt for it here for demo purposes.
        accessToken = prompt("Please enter your JWT Token (obtained from Swagger /api/auth/login or /api/verify/mobile/verify):");
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
        alert("Camera/Mic access denied or Token missing.");
    }
});

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.hostname;
    const port = window.location.port ? `:${window.location.port}` : '';
    
    // SECURE: Passing token in query parameter for WebSocket auth
    const wsUrl = `${protocol}//${host}${port}/ws/${roomId}/${clientId}?token=${accessToken}`;
    
    console.log(`[WS] Connecting to ${wsUrl}`);
    ws = new WebSocket(wsUrl);

    ws.onmessage = async (event) => {
        const message = JSON.parse(event.data);
        
        switch (message.type) {
            case 'peer-joined':
                remoteLabel.innerText = "Peer Connected";
                initPeerConnection(true);
                break;
            case 'offer':
                await handleOffer(message.sdp);
                break;
            case 'answer':
                await handleAnswer(message.sdp);
                break;
            case 'ice-candidate':
                if (peerConnection) await peerConnection.addIceCandidate(new RTCIceCandidate(message.candidate));
                break;
            case 'peer-left':
                remoteLabel.innerText = "Peer Disconnected";
                if (peerConnection) peerConnection.close();
                remoteVideo.srcObject = null;
                break;
            case 'chat':
                appendChatMessage(message.username, message.text, false);
                break;
        }
    };

    ws.onclose = (e) => {
        console.error("WS Closed:", e.reason);
        alert("Connection Closed: " + e.reason);
        location.reload();
    };
}

async function initPeerConnection(isInitiator) {
    peerConnection = new RTCPeerConnection(rtcConfig);
    localStream.getTracks().forEach(track => peerConnection.addTrack(track, localStream));

    peerConnection.ontrack = (event) => {
        remoteVideo.srcObject = event.streams[0];
    };

    peerConnection.onicecandidate = (event) => {
        if (event.candidate) {
            ws.send(JSON.stringify({ type: 'ice-candidate', candidate: event.candidate }));
        }
    };

    if (isInitiator) {
        const offer = await peerConnection.createOffer();
        await peerConnection.setLocalDescription(offer);
        ws.send(JSON.stringify({ type: 'offer', sdp: peerConnection.localDescription }));
    }
}

async function handleOffer(sdp) {
    if (!peerConnection) initPeerConnection(false);
    await peerConnection.setRemoteDescription(new RTCSessionDescription(sdp));
    const answer = await peerConnection.createAnswer();
    await pc.setLocalDescription(answer);
    ws.send(JSON.stringify({ type: 'answer', sdp: peerConnection.localDescription }));
}

async function handleAnswer(sdp) {
    await peerConnection.setRemoteDescription(new RTCSessionDescription(sdp));
}

// CAPTURE FEATURE (Calling Backend API)
window.captureImage = async (label) => {
    if (!remoteVideo.srcObject) {
        alert("No remote video to capture!");
        return;
    }

    const canvas = document.createElement('canvas');
    canvas.width = remoteVideo.videoWidth;
    canvas.height = remoteVideo.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(remoteVideo, 0, 0, canvas.width, canvas.height);
    const dataUrl = canvas.toDataURL('image/png');
    
    try {
        const response = await fetch('/api/session/capture', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${accessToken}`
            },
            body: JSON.stringify({
                room_id: roomId,
                label: label,
                image_data: dataUrl
            })
        });
        
        if (response.ok) {
            const item = document.createElement('div');
            item.className = 'capture-item';
            item.innerHTML = `<img src="${dataUrl}"><p>${label} - Saved to DB</p>`;
            captureGallery.prepend(item);
        } else {
            alert("Failed to save capture to server.");
        }
    } catch (err) {
        console.error("Capture API error:", err);
    }
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
    toggleAudioBtn.innerText = track.enabled ? "Mute Mic" : "Unmute Mic";
});

toggleVideoBtn.addEventListener('click', () => {
    const track = localStream.getVideoTracks()[0];
    track.enabled = !track.enabled;
    toggleVideoBtn.innerText = track.enabled ? "Stop Camera" : "Start Camera";
});

leaveBtn.addEventListener('click', () => {
    location.reload();
});