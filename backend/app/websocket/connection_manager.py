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
        role = role.lower().strip()
        logger.info(f"Join Attempt: Room={room_id}, Role={role}")

        # 1. INITIALIZE ROOM (ONLY FOR CUSTOMER)
        if room_id not in self.rooms:
            if role != "customer":
                logger.warning(f"BLOCKED: {role} tried to create room {room_id}")
                await websocket.close(code=4003, reason="Only a Customer can start a room.")
                return False
            self.rooms[room_id] = {}

        # 2. AGENT JOIN CHECK
        if role == "agent" and "customer" not in self.rooms[room_id]:
            logger.warning(f"BLOCKED: Agent {client_id} tried to join room {room_id} without a Customer.")
            # Safety: If room was empty/broken, delete it
            if not self.rooms[room_id]: del self.rooms[room_id]
            await websocket.close(code=4003, reason="Customer is not in this room.")
            return False
        
        # 3. CAPACITY CHECK
        if len(self.rooms[room_id]) >= 2:
            await websocket.close(code=4001, reason="Room is full.")
            return False
        
        if role in self.rooms[room_id]:
            await websocket.close(code=4002, reason=f"An {role} is already present.")
            return False

        # SUCCESS
        await websocket.accept()
        self.rooms[room_id][role] = websocket
        logger.info(f"ACTIVE: {role} connected to room {room_id}")
        
        target_role = "customer" if role == "agent" else "agent"
        if target_role in self.rooms[room_id]:
            await self.send_personal_message({"type": "peer-joined", "role": role}, room_id, target_role)
        return True

    def disconnect(self, room_id: str, role: str):
        role = role.lower().strip()
        if room_id in self.rooms and role in self.rooms[room_id]:
            del self.rooms[room_id][role]
            logger.info(f"Disconnected: {role} from room {room_id}")
            if not self.rooms[room_id]:
                del self.rooms[room_id]
                logger.info(f"Room {room_id} deleted because it is empty.")

    async def send_personal_message(self, message: dict, room_id: str, target_role: str):
        target_role = target_role.lower().strip()
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