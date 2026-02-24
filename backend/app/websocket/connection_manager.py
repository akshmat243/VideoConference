import json
import logging
from typing import Dict
from fastapi import WebSocket

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        # Maps room_id to a dictionary of client_id -> WebSocket
        self.rooms: Dict[str, Dict[str, WebSocket]] = {}

    async def connect(self, websocket: WebSocket, room_id: str, client_id: str):
        try:
            await websocket.accept()
            logger.info(f"Handshake accepted for Client: {client_id} in Room: {room_id}")
            
            if room_id not in self.rooms:
                self.rooms[room_id] = {}
            
            self.rooms[room_id][client_id] = websocket
            
            # Notify others in the room
            await self.broadcast(room_id, {
                "type": "new-peer",
                "peerId": client_id
            }, exclude_client=client_id)
        except Exception as e:
            logger.error(f"Failed to accept websocket for {client_id}: {str(e)}")
            raise e

    def disconnect(self, room_id: str, client_id: str):
        if room_id in self.rooms and client_id in self.rooms[room_id]:
            del self.rooms[room_id][client_id]
            logger.info(f"Client {client_id} disconnected from room {room_id}")
            
            # Clean up empty rooms
            if not self.rooms[room_id]:
                del self.rooms[room_id]

    async def broadcast(self, room_id: str, message: dict, exclude_client: str = None):
        if room_id in self.rooms:
            for client_id, connection in list(self.rooms[room_id].items()):
                if client_id != exclude_client:
                    try:
                        await connection.send_text(json.dumps(message))
                    except Exception as e:
                        logger.error(f"Error broadcasting to {client_id}: {e}")
                        # Connection might be dead, cleanup handled by disconnect

    async def send_personal_message(self, message: dict, room_id: str, target_client_id: str):
        if room_id in self.rooms and target_client_id in self.rooms[room_id]:
            try:
                websocket = self.rooms[room_id][target_client_id]
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error sending message to {target_client_id}: {e}")

manager = ConnectionManager()