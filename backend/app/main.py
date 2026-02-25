import logging
import json
import os
import random
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from jose import jwt
from passlib.context import CryptContext
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Query
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.websocket.connection_manager import manager
from app.core.config import settings
from app.core import models, schemas
from app.core.database import engine, get_db

# Initialize Database
models.Base.metadata.create_all(bind=engine)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

tags_metadata = [
    {"name": "1. Authentication & Security", "description": "Registration, Set MPIN, and Secure Login."},
    {"name": "2. Identity Verification (KYC)", "description": "Mobile, Aadhar, and PAN self-verification."},
    {"name": "3. Fintech Services", "description": "Apply for Accounts, Cards, and Loans via Video."},
    {"name": "4. Video KYC Orchestration", "description": "Manage live video queues and signaling."},
    {"name": "5. Support & Admin", "description": "Support tickets and Admin approval ops."},
]

app = FastAPI(title="Video KYC Fintech Ultimate", version="10.0.0", openapi_tags=tags_metadata)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --- HELPERS ---
def create_token(sub: str, role: str):
    return jwt.encode({"sub": sub, "role": role, "exp": datetime.utcnow() + timedelta(days=1)}, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def get_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user = db.query(models.User).filter((models.User.username == payload["sub"]) | (models.User.mobile_number == payload["sub"])).first()
        if not user: raise HTTPException(401)
        return user
    except: raise HTTPException(401)

# ----------------- 1. AUTHENTICATION & SECURITY -----------------

@app.post("/api/auth/agent/register", tags=["1. Authentication & Security"])
async def register_agent(user: schemas.AgentRegister, db: Session = Depends(get_db)):
    """Register an Agent. Returns initial token for verification."""
    hashed = pwd_context.hash(user.password[:50])
    new_user = models.User(username=user.username, mobile_number=user.mobile_number, aadhar_number=user.aadhar_number, pan_number=user.pan_number, role="agent", hashed_password=hashed)
    db.add(new_user); db.commit(); db.refresh(new_user)
    return {"access_token": create_token(user.username, "agent"), "token_type": "bearer"}

@app.post("/api/auth/set-mpin", tags=["1. Authentication & Security"])
async def set_mpin(req: schemas.SetMPIN, current_user: models.User = Depends(get_user), db: Session = Depends(get_db)):
    """Set numeric MPIN after identity verification."""
    current_user.hashed_mpin = pwd_context.hash(req.mpin)
    current_user.is_mpin_set = True
    db.commit()
    return {"message": "MPIN set successfully"}

@app.post("/api/auth/login", response_model=schemas.Token, tags=["1. Authentication & Security"])
async def login(req: schemas.UserLogin, db: Session = Depends(get_db)):
    """Secure Login using Identifier + MPIN."""
    user = db.query(models.User).filter((models.User.username == req.identifier) | (models.User.mobile_number == req.identifier)).first()
    if not user or not user.is_mpin_set or not pwd_context.verify(req.mpin, user.hashed_mpin):
        raise HTTPException(401, "Invalid Credentials or MPIN")
    if user.role == "agent" and not user.is_admin_approved:
        raise HTTPException(403, "Admin approval pending")
    return {"access_token": create_token(user.username or user.mobile_number, user.role), "token_type": "bearer"}

# ----------------- 2. IDENTITY VERIFICATION (KYC) -----------------

@app.post("/api/verify/mobile/request", tags=["2. Identity Verification (KYC)"])
async def request_mobile_otp(req: schemas.MobileRequest, db: Session = Depends(get_db)):
    otp = str(random.randint(100000, 999999))
    db.add(models.OTPTracker(identifier=req.mobile_number, otp_code=otp, expires_at=datetime.utcnow() + timedelta(minutes=5)))
    db.commit(); logger.info(f"OTP: {otp}")
    return {"message": "OTP Sent"}

@app.post("/api/verify/mobile/verify", tags=["2. Identity Verification (KYC)"])
async def verify_mobile_otp(req: schemas.MobileVerify, db: Session = Depends(get_db)):
    tracker = db.query(models.OTPTracker).filter(models.OTPTracker.identifier == req.mobile_number, models.OTPTracker.otp_code == req.otp).first()
    if not tracker: raise HTTPException(400, "Invalid OTP")
    user = db.query(models.User).filter(models.User.mobile_number == req.mobile_number).first()
    if not user:
        user = models.User(mobile_number=req.mobile_number, is_mobile_verified=True, role="customer")
        db.add(user)
    else: user.is_mobile_verified = True
    db.commit(); db.refresh(user)
    return {"access_token": create_token(req.mobile_number, user.role), "token_type": "bearer"}

@app.post("/api/verify/aadhar/request", tags=["2. Identity Verification (KYC)"])
async def request_aadhar_otp(req: schemas.AadharRequest, current_user: models.User = Depends(get_user), db: Session = Depends(get_db)):
    otp = str(random.randint(100000, 999999))
    db.add(models.OTPTracker(identifier=req.aadhar_number, otp_code=otp, expires_at=datetime.utcnow() + timedelta(minutes=5)))
    db.commit(); logger.info(f"AADHAR OTP: {otp}")
    return {"message": "OTP Sent"}

@app.post("/api/verify/aadhar/verify", tags=["2. Identity Verification (KYC)"])
async def verify_aadhar_otp(req: schemas.AadharVerify, current_user: models.User = Depends(get_user), db: Session = Depends(get_db)):
    tracker = db.query(models.OTPTracker).filter(models.OTPTracker.identifier == req.aadhar_number, models.OTPTracker.otp_code == req.otp).first()
    if not tracker: raise HTTPException(400, "Invalid OTP")
    current_user.aadhar_number, current_user.is_aadhar_verified = req.aadhar_number, True
    db.commit()
    return {"message": "Aadhar Verified"}

@app.post("/api/verify/pan/verify", tags=["2. Identity Verification (KYC)"])
async def verify_pan(req: schemas.PANVerify, current_user: models.User = Depends(get_user), db: Session = Depends(get_db)):
    current_user.pan_number, current_user.is_pan_verified = req.pan_number, True
    db.commit()
    return {"message": "PAN Verified"}

# ----------------- 3. FINTECH SERVICES -----------------

@app.post("/api/services/apply/account", tags=["3. Fintech Services"])
async def apply_account(req: schemas.AccountApply, u: models.User = Depends(get_user), db: Session = Depends(get_db)):
    room_id = f"acc-{uuid.uuid4().hex[:6]}"
    db.add(models.KYCSession(room_id=room_id, customer_id=u.id, service_type="ACCOUNT_OPENING"))
    db.commit(); return {"room_id": room_id}

@app.post("/api/services/apply/card", tags=["3. Fintech Services"])
async def apply_card(req: schemas.CardApply, u: models.User = Depends(get_user), db: Session = Depends(get_db)):
    room_id = f"card-{uuid.uuid4().hex[:6]}"
    db.add(models.KYCSession(room_id=room_id, customer_id=u.id, service_type="CARD_ISSUANCE"))
    db.commit(); return {"room_id": room_id}

@app.post("/api/services/apply/loan", tags=["3. Fintech Services"])
async def apply_loan(req: schemas.LoanApply, u: models.User = Depends(get_user), db: Session = Depends(get_db)):
    room_id = f"loan-{uuid.uuid4().hex[:6]}"
    db.add(models.KYCSession(room_id=room_id, customer_id=u.id, service_type="LOAN_APPROVAL"))
    # Pre-create loan entry
    db.add(models.LoanApplication(customer_id=u.id, amount=req.amount, purpose=req.purpose))
    db.commit(); return {"room_id": room_id}

@app.post("/api/services/card/block", tags=["3. Fintech Services"])
async def block_card(req: schemas.CardBlock, u: models.User = Depends(get_user), db: Session = Depends(get_db)):
    room_id = f"block-{uuid.uuid4().hex[:6]}"
    db.add(models.KYCSession(room_id=room_id, customer_id=u.id, service_type="CARD_BLOCKING"))
    db.commit(); return {"room_id": room_id}

# ----------------- 4. VIDEO KYC ORCHESTRATION -----------------

@app.post("/api/kyc/request", tags=["4. Video KYC Orchestration"])
async def request_kyc(u: models.User = Depends(get_user), db: Session = Depends(get_db)):
    room_id = f"kyc-{uuid.uuid4().hex[:6]}"
    db.add(models.KYCSession(room_id=room_id, customer_id=u.id, service_type="KYC"))
    u.video_kyc_status = "requested"
    db.commit(); return {"room_id": room_id}

@app.get("/api/kyc/pending", tags=["4. Video KYC Orchestration"])
async def list_pending(db: Session = Depends(get_db)):
    return db.query(models.KYCSession).filter(models.KYCSession.status == "requested").all()

@app.post("/api/kyc/accept/{room_id}", tags=["4. Video KYC Orchestration"])
async def accept_kyc(room_id: str, u: models.User = Depends(get_user), db: Session = Depends(get_db)):
    s = db.query(models.KYCSession).filter(models.KYCSession.room_id == room_id).first()
    s.agent_id, s.status = u.id, "active"
    db.commit(); return {"message": "Accepted"}

@app.post("/api/session/capture", tags=["4. Video KYC Orchestration"])
async def log_capture(capture: schemas.CaptureLog, db: Session = Depends(get_db)):
    s = db.query(models.KYCSession).filter(models.KYCSession.room_id == capture.room_id).first()
    db.add(models.Capture(session_id=s.id, label=capture.label, image_base64=capture.image_data))
    db.commit(); return {"status": "Saved"}

@app.websocket("/ws/{room_id}/{client_id}")
async def ws_end(websocket: WebSocket, room_id: str, client_id: str, token: str = Query(...)):
    try:
        p = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        await manager.connect(websocket, room_id, client_id, p["role"])
        t = "customer" if p["role"] == "agent" else "agent"
        while True:
            data = await websocket.receive_text()
            m = json.loads(data)
            if m.get("type") in ["offer", "answer", "ice-candidate"]: await manager.send_personal_message(m, room_id, t)
            elif m.get("type") == "chat": await manager.broadcast(room_id, m, exclude_role=p["role"])
    except: await websocket.close(code=1008)

# ----------------- 5. SUPPORT & ADMIN -----------------

@app.post("/api/admin/approve-agent", tags=["5. Support & Admin"])
async def approve_ag(req: schemas.AdminApprove, db: Session = Depends(get_db)):
    agent = db.query(models.User).filter(models.User.id == req.agent_id).first()
    agent.is_admin_approved = req.approve; db.commit(); return {"msg": "Success"}

@app.post("/api/agent/service/decision", tags=["5. Support & Admin"])
async def service_decision(req: schemas.ServiceDecision, db: Session = Depends(get_db)):
    s = db.query(models.KYCSession).filter(models.KYCSession.room_id == req.room_id).first()
    if req.status == "approved":
        if s.service_type == "ACCOUNT_OPENING":
            db.add(models.Account(user_id=s.customer_id, account_number=str(random.randint(10**9, 10**10-1)), account_type="Savings"))
        elif s.service_type == "CARD_ISSUANCE":
            db.add(models.Card(user_id=s.customer_id, card_number=f"4111-{random.randint(1000,9999)}-{random.randint(1000,9999)}", card_type="Debit"))
        elif s.service_type == "LOAN_APPROVAL":
            loan = db.query(models.LoanApplication).filter(models.LoanApplication.customer_id == s.customer_id).order_by(models.LoanApplication.id.desc()).first()
            loan.status = "approved"
        elif s.service_type == "KYC":
            u = db.query(models.User).filter(models.User.id == s.customer_id).first()
            u.video_kyc_status = "verified"
    s.status = "completed" if req.status == "approved" else "rejected"
    db.commit(); return {"message": "Success"}

@app.post("/api/customer/raise-ticket", tags=["5. Support & Admin"])
async def raise_ticket(req: schemas.TicketCreate, u: models.User = Depends(get_user), db: Session = Depends(get_db)):
    db.add(models.Ticket(customer_id=u.id, subject=req.subject, description=req.description))
    db.commit(); return {"msg": "Ticket Raised"}

@app.get("/", include_in_schema=False)
async def r(): return RedirectResponse(url="/static/index.html")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "frontend"), html=True), name="static")
