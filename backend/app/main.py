import logging
import json
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.websocket.connection_manager import manager
from app.core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.PROJECT_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Robust path calculation
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
frontend_dir = os.path.join(BASE_DIR, "frontend")

@app.get("/")
async def root():
    """Redirect root to the video conference UI"""
    return RedirectResponse(url="/static/index.html")

if os.path.exists(frontend_dir):
    logger.info(f"Serving static files from: {frontend_dir}")
    app.mount("/static", StaticFiles(directory=frontend_dir, html=True), name="static")
else:
    logger.error(f"FATAL: Frontend directory NOT FOUND at: {frontend_dir}")

@app.websocket("/ws/{room_id}/{client_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, client_id: str):
    logger.info(f"New connection attempt: Room={room_id}, Client={client_id}")
    await manager.connect(websocket, room_id, client_id)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            target_peer = message.get("targetPeer")
            msg_type = message.get("type")
            
            if msg_type in ["offer", "answer", "ice-candidate"]:
                if target_peer:
                    message["peerId"] = client_id
                    await manager.send_personal_message(message, room_id, target_peer)
            elif msg_type == "chat":
                message["peerId"] = client_id
                await manager.broadcast(room_id, message, exclude_client=client_id)

    except WebSocketDisconnect:
        logger.info(f"Client {client_id} disconnected normally.")
        manager.disconnect(room_id, client_id)
        await manager.broadcast(room_id, {"type": "peer-left", "peerId": client_id})
    except Exception as e:
        logger.error(f"Error for client {client_id}: {str(e)}")
        manager.disconnect(room_id, client_id)