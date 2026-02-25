# Secure Video KYC & Fintech Platform

A production-ready, 1-to-1 P2P Video KYC system built with **FastAPI**, **WebRTC**, and **SQLAlchemy**.

## 🚀 The 6-Phase Professional Workflow

### 1. Registration & Identity (Self-Service)
- **Agents**: Register with `AgentRegister` schema. Initial state is `Unverified`.
- **Customers**: Verify **Mobile** (OTP) and **Aadhar** (OTP) using the KYC Flow APIs.
- **PAN Verification**: Instant check for both roles.

### 2. Mandatory Security (MPIN)
- Once identity is verified, users **must** call `/api/auth/set-mpin`.
- Every future login **requires** the numeric MPIN.

### 3. Admin Oversight
- Verified Agents enter a "Pending Approval" queue.
- An Admin must call `/api/admin/approve-agent` before the Agent can start working.

### 4. Video KYC Orchestration
- **Customer**: Finished all self-checks? Call `/api/kyc/request` to enter the live queue.
- **Agent**: Call `/api/kyc/pending` to see waiting customers and `/api/kyc/accept/{room_id}` to pick a session.

### 5. Secure Live Session (WebRTC)
- Connection is ONLY allowed if the JWT token is valid AND user is 100% KYC verified.
- **Document Capture**: Agent captures Photo/PAN/Aadhar directly from the live video. Images are saved as Base64 in the database for auditing.

### 6. Final Decision
- Agent calls `/api/kyc/decision` to permanently mark the customer as `verified` or `rejected`.

---

## 🛠️ Tech Stack & API
- **Backend**: Python 3.11+, FastAPI, SQLAlchemy (SQLite), PyJWT, Bcrypt.
- **Signaling**: WebSockets (Secure handshake).
- **Frontend**: Vanilla JS (React-ready API structure).
- **Documentation**: Swagger UI available at `/docs`.

## 🏃 Running the Project
1. Install dependencies: `pip install -r requirements.txt`
2. Start the server:
   ```powershell
   $env:PYTHONPATH = ".\backend"
   python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```
3. Visit `http://localhost:8000/docs` to test the API flow or `http://localhost:8000/` for the UI.
