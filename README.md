# WebRTC Video Conferencing System

A production-ready video conferencing system using Python (FastAPI) and WebRTC.

## 🏛️ Architecture & Core Concepts

### WebRTC Fundamentals
- **WebRTC (Web Real-Time Communication)** enables peer-to-peer audio, video, and data sharing between browsers without needing intermediate servers for media handling.
- **RTCPeerConnection**: The core API representing a WebRTC connection between the local computer and a remote peer. It handles stream encoding/decoding, network transmission, and security.
- **SDP (Session Description Protocol) Offer/Answer**: A text-based format describing multimedia communication sessions.
  - **Offer**: A peer generates an offer containing its media capabilities (codecs, resolutions).
  - **Answer**: The receiving peer responds with an answer indicating common supported capabilities.
- **ICE (Interactive Connectivity Establishment) Candidates**: Network endpoints (IP/Port). WebRTC uses ICE to find the best path to connect peers, bypassing NATs and Firewalls.
- **DTLS & SRTP**: WebRTC forces encryption. **DTLS** (Datagram Transport Layer Security) is used to exchange keys securely, and **SRTP** (Secure Real-time Transport Protocol) is used to encrypt the audio/video media itself.

### Signaling Flow
WebRTC requires a "Signaling Server" to exchange SDP and ICE candidates before a direct connection can be established.
1. User A joins a room via **WebSocket**.
2. User B joins the room. The WebSocket Server tells User A that User B joined.
3. User A creates an **Offer** and sends it over WebSocket.
4. Server relays the Offer to User B.
5. User B receives the Offer, creates an **Answer**, and sends it back.
6. Server relays Answer to User A.
7. Concurrently, both users gather **ICE Candidates** and exchange them via the WebSocket.
8. Once connection is formed, media flows directly (P2P).

### Networking: STUN vs TURN
- **STUN (Session Traversal Utilities for NAT)**: A lightweight server that tells a client its public IP address and port. Sufficient for most home networks (Full Cone / Restricted Cone NATs).
- **TURN (Traversal Using Relays around NAT)**: Required for restrictive networks (Symmetric NATs, corporate firewalls) where direct P2P fails. It acts as a cloud relay for media traffic.
- **Coturn** is the industry standard open-source STUN/TURN server.

### Scalability: Mesh vs SFU
- **Mesh Architecture (Implemented here)**: Every user connects directly to every other user. Perfect for 2-4 users. Extremely low latency and zero server media costs. However, CPU and bandwidth scale by `O(N^2)`, making it impossible for large meetings.
- **SFU Architecture (Selective Forwarding Unit - Mediasoup / Janus)**: Each client sends their media stream once to the SFU server, which routes it to all other participants. Requires a heavy backend (Node.js/C++) but scales to 50+ users in a room. Use this for Zoom-like scalable meetings.

## 🚀 Setup & Execution

### Local Development (VirtualEnv)
1. Ensure Python 3.11+ is installed.
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the FastAPI server:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```
5. Open your browser to `http://127.0.0.1:8000/static/index.html` (Open two tabs to test!).

### Docker Deployment
Run everything (FastAPI + Turn Server) via Docker Compose:
```bash
docker-compose up --build -d
```
*Note: Ensure to update the Coturn secret and IP configurations in docker-compose.yml for production.*"# VideoConference" 
