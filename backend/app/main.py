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
    {"name": "2. Identity Verification (KYC)", "description": "Mobile (with Resend), Aadhar, and PAN verification."},
    {"name": "3. Fintech Services", "description": "Apply for Accounts, Cards, and Loans via Video."},
    {"name": "4. Video KYC Orchestration", "description": "Manage live video queues and signaling."},
    {"name": "5. Support & Admin", "description": "Support tickets and Admin approval ops."},
]

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import traceback

app = FastAPI(title="Video KYC Fintech Ultimate Pro", version="11.0.0", openapi_tags=tags_metadata)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --- DEBUGGERS ---
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(status_code=422, content={"detail": "JSON Body Incorrect", "missing_or_wrong_fields": exc.errors()})

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error", "reason": str(exc)})

# --- HELPERS ---
def create_token(sub: str, role: str):
    return jwt.encode({"sub": sub, "role": role, "exp": datetime.utcnow() + timedelta(days=1)}, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def get_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    # 1. Check if token is blacklisted
    blacklisted = db.query(models.TokenBlacklist).filter(models.TokenBlacklist.token == token).first()
    if blacklisted:
        raise HTTPException(status_code=401, detail="Token has been logged out")

    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user = db.query(models.User).filter((models.User.username == payload["sub"]) | (models.User.mobile_number == payload["sub"])).first()
        if not user: raise HTTPException(401)
        return user
    except: raise HTTPException(401)

# ----------------- 1. AUTHENTICATION & SECURITY -----------------


@app.post("/api/auth/agent/register", tags=["1. Authentication & Security"])
async def register_agent(user: schemas.AgentRegister, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter((models.User.username == user.username) | (models.User.mobile_number == user.mobile_number) | (models.User.aadhar_number == user.aadhar_number) | (models.User.pan_number == user.pan_number)).first()
    if existing: raise HTTPException(status_code=400, detail="Data already exists")
    hashed = pwd_context.hash(user.password[:50])
    new_user = models.User(username=user.username, mobile_number=user.mobile_number, aadhar_number=user.aadhar_number, pan_number=user.pan_number, role="agent", hashed_password=hashed)
    db.add(new_user); db.commit(); db.refresh(new_user)
    return {"access_token": create_token(user.username, "agent"), "token_type": "bearer", "user_id": new_user.id}

@app.post("/api/auth/set-mpin", tags=["1. Authentication & Security"])
async def set_mpin(req: schemas.SetMPIN, current_user: models.User = Depends(get_user), db: Session = Depends(get_db)):
    current_user.hashed_mpin = pwd_context.hash(req.mpin); current_user.is_mpin_set = True; db.commit()
    return {"message": "MPIN set successfully"}

@app.post("/api/auth/login", response_model=schemas.Token, tags=["1. Authentication & Security"])
async def login(req: schemas.UserLogin, db: Session = Depends(get_db)):
    """Secure Login: Role is automatically detected from the database."""
    user = db.query(models.User).filter((models.User.username == req.identifier) | (models.User.mobile_number == req.identifier)).first()
    
    if not user or not user.is_mpin_set or not pwd_context.verify(req.mpin, user.hashed_mpin):
        raise HTTPException(401, "Invalid Credentials or MPIN")
    
    # Check for Agent specific gate
    if user.role == "agent" and not user.is_admin_approved:
        raise HTTPException(403, detail=f"Waiting for Admin Approval. Your Agent ID is: {user.id}")
        
    return {
        "access_token": create_token(user.username or user.mobile_number, user.role), 
        "token_type": "bearer",
        "role": user.role # Returning the verified role
    }

@app.post("/api/auth/logout", tags=["1. Authentication & Security"])
async def logout(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """Add current token to blacklist to prevent further use."""
    # Check if already blacklisted
    exists = db.query(models.TokenBlacklist).filter(models.TokenBlacklist.token == token).first()
    if not exists:
        db.add(models.TokenBlacklist(token=token))
        db.commit()
    return {"message": "Logged out successfully"}

# ----------------- 2. IDENTITY VERIFICATION (KYC) -----------------

@app.post("/api/verify/mobile/request", tags=["2. Identity Verification (KYC)"])
async def request_mobile_otp(req: schemas.MobileRequest, db: Session = Depends(get_db)):
    otp = str(random.randint(100000, 999999))
    db.add(models.OTPTracker(identifier=req.mobile_number, otp_code=otp, expires_at=datetime.utcnow() + timedelta(minutes=10)))
    db.commit(); logger.info(f"OTP: {otp}")
    return {"message": "OTP Sent"}

@app.post("/api/verify/mobile/resend", tags=["2. Identity Verification (KYC)"])
async def resend_mobile_otp(req: schemas.MobileRequest, db: Session = Depends(get_db)):
    return await request_mobile_otp(req, db)

@app.post("/api/verify/mobile/verify", tags=["2. Identity Verification (KYC)"])
async def verify_mobile_otp(req: schemas.MobileVerify, db: Session = Depends(get_db)):
    tracker = db.query(models.OTPTracker).filter(models.OTPTracker.identifier == req.mobile_number, models.OTPTracker.otp_code == req.otp, models.OTPTracker.expires_at > datetime.utcnow()).first()
    if not tracker: raise HTTPException(400, "Invalid OTP")
    dup = db.query(models.User).filter(models.User.mobile_number == req.mobile_number, models.User.is_mobile_verified == True).first()
    if dup: raise HTTPException(400, detail="Mobile number already linked to another account")
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
    db.add(models.OTPTracker(identifier=req.aadhar_number, otp_code=otp, expires_at=datetime.utcnow() + timedelta(minutes=10)))
    db.commit(); logger.info(f"OTP: {otp}")
    return {"message": "Aadhar OTP Sent"}

@app.post("/api/verify/aadhar/verify", tags=["2. Identity Verification (KYC)"])
async def verify_aadhar_otp(req: schemas.AadharVerify, current_user: models.User = Depends(get_user), db: Session = Depends(get_db)):
    dup = db.query(models.User).filter(models.User.aadhar_number == req.aadhar_number, models.User.id != current_user.id).first()
    if dup: raise HTTPException(400, detail="Aadhar number already linked to another account")
    tracker = db.query(models.OTPTracker).filter(models.OTPTracker.identifier == req.aadhar_number, models.OTPTracker.otp_code == req.otp, models.OTPTracker.expires_at > datetime.utcnow()).first()
    if not tracker: raise HTTPException(400, "Invalid OTP")
    current_user.aadhar_number, current_user.is_aadhar_verified = req.aadhar_number, True
    db.commit()
    return {"message": "Aadhar Verified"}

@app.post("/api/verify/pan/verify", tags=["2. Identity Verification (KYC)"])
async def verify_pan(req: schemas.PANVerify, current_user: models.User = Depends(get_user), db: Session = Depends(get_db)):
    dup = db.query(models.User).filter(models.User.pan_number == req.pan_number, models.User.id != current_user.id).first()
    if dup: raise HTTPException(400, detail="PAN number already linked to another account")
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
    db.add(models.LoanApplication(customer_id=u.id, amount=req.amount, purpose=req.purpose))
    db.commit(); return {"room_id": room_id}

@app.post("/api/services/card/block", tags=["3. Fintech Services"])
async def block_card(req: schemas.CardBlock, u: models.User = Depends(get_user), db: Session = Depends(get_db)):
    room_id = f"block-{uuid.uuid4().hex[:6]}"
    db.add(models.KYCSession(room_id=room_id, customer_id=u.id, service_type="CARD_BLOCKING"))
    db.commit(); return {"room_id": room_id}

# ----------------- 4. VIDEO KYC ORCHESTRATION -----------------

@app.get("/api/kyc/pending", tags=["4. Video KYC Orchestration"])
async def list_pending(db: Session = Depends(get_db)):
    """List requested sessions. Shows if customer is online or not."""
    all_req = db.query(models.KYCSession).filter(models.KYCSession.status == "requested").all()
    results = []
    for s in all_req:
        is_online = s.room_id in manager.rooms and "customer" in manager.rooms[s.room_id]
        results.append({
            "room_id": s.room_id,
            "service_type": s.service_type,
            "status": s.status,
            "is_customer_online": is_online
        })
    return results

@app.delete("/api/kyc/clear-all", tags=["4. Video KYC Orchestration"])
async def clear_all_pending(current_user: models.User = Depends(get_user), db: Session = Depends(get_db)):
    if current_user.role != "agent": raise HTTPException(403)
    db.query(models.KYCSession).filter(models.KYCSession.status == "requested").delete()
    db.commit()
    return {"message": "Success"}

@app.post("/api/kyc/accept/{room_id}", tags=["4. Video KYC Orchestration"])
async def accept_kyc(room_id: str, u: models.User = Depends(get_user), db: Session = Depends(get_db)):
    s = db.query(models.KYCSession).filter(models.KYCSession.room_id == room_id).first()
    if not s: raise HTTPException(404)
    s.agent_id, s.status = u.id, "active"
    db.commit(); return {"message": "Accepted"}

@app.post("/api/session/capture", tags=["4. Video KYC Orchestration"])
async def log_capture(capture: schemas.CaptureLog, db: Session = Depends(get_db)):
    s = db.query(models.KYCSession).filter(models.KYCSession.room_id == capture.room_id).first()
    if not s:
        s = models.KYCSession(room_id=capture.room_id, status="active")
        db.add(s); db.commit(); db.refresh(s)
    db.add(models.Capture(session_id=s.id, label=capture.label, image_base64=capture.image_data))
    db.commit(); return {"status": "Saved"}

@app.websocket("/ws/{room_id}/{client_id}")
async def ws_end(websocket: WebSocket, room_id: str, client_id: str, token: str = Query(...)):
    user_role = "customer" # Default
    try:
        p = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        db = next(get_db())
        user = db.query(models.User).filter((models.User.username == p["sub"]) | (models.User.mobile_number == p["sub"])).first()
        if not user or not user.is_mpin_set: await websocket.close(code=1008); return
        
        user_role = user.role.lower().strip()
        db_session = db.query(models.KYCSession).filter(models.KYCSession.room_id == room_id).first()
        if not db_session: await websocket.close(code=4003); return

        success = await manager.connect(websocket, room_id, client_id, user_role)
        if not success: return

        t = "customer" if user_role == "agent" else "agent"
        while True:
            data = await websocket.receive_text()
            m = json.loads(data)
            if m.get("type") in ["offer", "answer", "ice-candidate", "media-status", "close-session"]:
                await manager.send_personal_message(m, room_id, t)
            elif m.get("type") == "chat": await manager.broadcast(room_id, m, exclude_role=user_role)
    except WebSocketDisconnect:
        manager.disconnect(room_id, user_role)
        if user_role == "customer":
            # Auto-purge DB session if customer leaves
            db = next(get_db())
            s = db.query(models.KYCSession).filter(models.KYCSession.room_id == room_id).first()
            if s and s.status != "completed": db.delete(s); db.commit()
        await manager.send_personal_message({"type": "close-session"}, room_id, "agent" if user_role=="customer" else "customer")
    except: await websocket.close(code=1008)

# ----------------- 5. SUPPORT & ADMIN -----------------

@app.get("/api/admin/all-users", tags=["5. Support & Admin"])
async def list_all_users(db: Session = Depends(get_db)):
    return db.query(models.User).all()

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
            if loan: loan.status = "approved"
        elif s.service_type == "KYC":
            u = db.query(models.User).filter(models.User.id == s.customer_id).first()
            if u: u.video_kyc_status = "verified"
    s.status = "completed" if req.status == "approved" else "rejected"
    db.commit(); return {"message": "Success"}

@app.post("/api/customer/raise-ticket", tags=["5. Support & Admin"])
async def raise_ticket(req: schemas.TicketCreate, u: models.User = Depends(get_user), db: Session = Depends(get_db)):
    db.add(models.Ticket(customer_id=u.id, subject=req.subject, description=req.description))
    db.commit(); return {"msg": "Ticket Raised Successfully"}

@app.get("/api/customer/my-tickets", tags=["5. Support & Admin"])
async def get_my_tickets(u: models.User = Depends(get_user), db: Session = Depends(get_db)):
    """Customer: View the status and feedback of my tickets."""
    return db.query(models.Ticket).filter(models.Ticket.customer_id == u.id).all()

@app.get("/api/agent/tickets/pending", tags=["5. Support & Admin"])
async def list_pending_tickets(u: models.User = Depends(get_user), db: Session = Depends(get_db)):
    """Agent: See all open support tickets."""
    if u.role != "agent": raise HTTPException(403)
    return db.query(models.Ticket).filter(models.Ticket.status == "open").all()

@app.post("/api/agent/tickets/resolve", tags=["5. Support & Admin"])
async def resolve_ticket(req: schemas.TicketResolve, u: models.User = Depends(get_user), db: Session = Depends(get_db)):
    """Agent: Resolve a ticket and provide feedback."""
    if u.role != "agent": raise HTTPException(403)
    ticket = db.query(models.Ticket).filter(models.Ticket.id == req.ticket_id).first()
    if not ticket: raise HTTPException(404)
    
    ticket.status = req.status
    ticket.agent_feedback = req.feedback
    db.commit()
    return {"message": "Ticket resolved and feedback sent"}

@app.get("/", include_in_schema=False)
async def r(): return RedirectResponse(url="/static/index.html")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "frontend"), html=True), name="static")
