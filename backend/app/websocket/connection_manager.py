import json
import logging
from typing import Dict
from fastapi import WebSocket

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        # Maps room_id -> { "agent": ws, "customer": ws }
        self.rooms: Dict[str, Dict[str, WebSocket]] = {}

    async def connect(self, websocket: WebSocket, room_id: str, client_id: str, role: str):
        if room_id not in self.rooms:
            self.rooms[room_id] = {}
        
        # Enforce 1-to-1 and Role uniqueness
        if len(self.rooms[room_id]) >= 2:
            await websocket.close(code=4001, reason="Room Full")
            return False
        
        if role in self.rooms[room_id]:
            await websocket.close(code=4002, reason=f"An {role} is already in the room")
            return False

        await websocket.accept()
        self.rooms[room_id][role] = websocket
        logger.info(f"{role} ({client_id}) connected to room {room_id}")
        
        # Notify the other peer if they exist
        target_role = "customer" if role == "agent" else "agent"
        if target_role in self.rooms[room_id]:
            await self.send_personal_message(
                {"type": "peer-joined", "role": role}, 
                room_id, 
                target_role
            )
        return True

    def disconnect(self, room_id: str, role: str):
        if room_id in self.rooms and role in self.rooms[room_id]:
            del self.rooms[room_id][role]
            if not self.rooms[room_id]:
                del self.rooms[room_id]

    async def send_personal_message(self, message: dict, room_id: str, target_role: str):
        if room_id in self.rooms and target_role in self.rooms[room_id]:
            try:
                websocket = self.rooms[room_id][target_role]
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error sending to {target_role}: {e}")

    async def broadcast(self, room_id: str, message: dict, exclude_role: str = None):
        if room_id in self.rooms:
            for role, connection in list(self.rooms[room_id].items()):
                if role != exclude_role:
                    await connection.send_text(json.dumps(message))

manager = ConnectionManager()