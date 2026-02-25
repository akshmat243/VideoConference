from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from .database import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=True)
    hashed_password = Column(String, nullable=True)
    hashed_mpin = Column(String, nullable=True)
    is_mpin_set = Column(Boolean, default=False)
    mobile_number = Column(String, unique=True, index=True, nullable=True)
    is_mobile_verified = Column(Boolean, default=False)
    aadhar_number = Column(String, unique=True, nullable=True)
    is_aadhar_verified = Column(Boolean, default=False)
    pan_number = Column(String, unique=True, nullable=True)
    is_pan_verified = Column(Boolean, default=False)
    video_kyc_status = Column(String, default="pending") 
    is_admin_approved = Column(Boolean, default=False)
    role = Column(String, default="customer") 

class Account(Base):
    __tablename__ = "accounts"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    account_number = Column(String, unique=True)
    account_type = Column(String) 
    status = Column(String, default="active")
    created_at = Column(DateTime, default=datetime.utcnow)

class Card(Base):
    __tablename__ = "cards"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    card_number = Column(String, unique=True)
    card_type = Column(String) 
    is_blocked = Column(Boolean, default=False)
    status = Column(String, default="active")

class LoanApplication(Base):
    __tablename__ = "loans"
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Integer)
    purpose = Column(String)
    status = Column(String, default="pending") 
    agent_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    applied_at = Column(DateTime, default=datetime.utcnow)

class Ticket(Base):
    __tablename__ = "tickets"
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("users.id"))
    subject = Column(String)
    description = Column(Text)
    status = Column(String, default="open") 
    created_at = Column(DateTime, default=datetime.utcnow)

class KYCSession(Base):
    __tablename__ = "kyc_sessions"
    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(String, unique=True, index=True)
    customer_id = Column(Integer, ForeignKey("users.id"))
    agent_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    service_type = Column(String) # KYC, ACCOUNT_OPENING, LOAN_APPROVAL, CARD_ISSUANCE, CARD_BLOCKING
    status = Column(String, default="requested")
    requested_at = Column(DateTime, default=datetime.utcnow)

class Capture(Base):
    __tablename__ = "captures"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("kyc_sessions.id"))
    label = Column(String)
    image_base64 = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

class OTPTracker(Base):
    __tablename__ = "otps"
    id = Column(Integer, primary_key=True, index=True)
    identifier = Column(String, index=True)
    otp_code = Column(String)
    expires_at = Column(DateTime)
