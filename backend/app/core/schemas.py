from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class Token(BaseModel):
    access_token: str
    token_type: str

class UserLogin(BaseModel):
    identifier: str
    mpin: str = Field(..., min_length=4, max_length=6)
    role: str

class SetMPIN(BaseModel):
    mpin: str = Field(..., min_length=4, max_length=6)

class AgentRegister(BaseModel):
    username: str
    password: str
    mobile_number: str = Field(..., pattern=r"^\d{10}$", description="Must be exactly 10 digits")
    aadhar_number: str = Field(..., pattern=r"^\d{12}$", description="Must be exactly 12 digits")
    pan_number: str = Field(..., pattern=r"^[A-Z0-9]{10}$", description="Must be 10 Alphanumeric Capitals")

# --- Identity Verification ---
class MobileRequest(BaseModel):
    mobile_number: str = Field(..., pattern=r"^\d{10}$")

class MobileVerify(BaseModel):
    mobile_number: str = Field(..., pattern=r"^\d{10}$")
    otp: str = Field(..., min_length=6, max_length=6)

class AadharRequest(BaseModel):
    aadhar_number: str = Field(..., pattern=r"^\d{12}$")

class AadharVerify(BaseModel):
    aadhar_number: str = Field(..., pattern=r"^\d{12}$")
    otp: str = Field(..., min_length=6, max_length=6)

class PANVerify(BaseModel):
    pan_number: str = Field(..., pattern=r"^[A-Z0-9]{10}$")

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
    status: str 
    notes: Optional[str] = None
class AdminApprove(BaseModel):
    agent_id: int
    approve: bool

# --- Live Session ---
class CaptureLog(BaseModel):
    room_id: str
    label: str
    image_data: str
class RoomStatus(BaseModel):
    room_id: str
    is_active: bool
    participants: List[str]
