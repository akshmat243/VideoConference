from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class Token(BaseModel):
    access_token: str
    token_type: str

class UserLogin(BaseModel):
    identifier: str
    mpin: str
    role: str

class SetMPIN(BaseModel):
    mpin: str = Field(..., min_length=4, max_length=6)

class AgentRegister(BaseModel):
    username: str
    password: str
    mobile_number: str
    aadhar_number: str
    pan_number: str

# --- Fintech Services ---
class AccountApply(BaseModel):
    account_type: str
class CardApply(BaseModel):
    card_type: str
class CardBlock(BaseModel):
    card_number: str
    reason: str
class LoanApply(BaseModel):
    amount: int
    purpose: str
class TicketCreate(BaseModel):
    subject: str
    description: str

# --- Decisions & Admin ---
class ServiceDecision(BaseModel):
    room_id: str
    status: str # 'approved' or 'rejected'
    notes: Optional[str] = None
class AdminApprove(BaseModel):
    agent_id: int
    approve: bool

# --- Identity Verification ---
class MobileRequest(BaseModel):
    mobile_number: str
class MobileVerify(BaseModel):
    mobile_number: str
    otp: str
class AadharRequest(BaseModel):
    aadhar_number: str
class AadharVerify(BaseModel):
    aadhar_number: str
    otp: str
class PANVerify(BaseModel):
    pan_number: str

# --- Live Session ---
class CaptureLog(BaseModel):
    room_id: str
    label: str
    image_data: str
class RoomStatus(BaseModel):
    room_id: str
    is_active: bool
    participants: List[str]
