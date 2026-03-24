"""
main.py — FastAPI backend server.

Endpoints:
  POST /auth/register  — Create account
  POST /auth/login     — Sign in
  POST /upload         — Upload and process document
  POST /chat           — Ask a question with chat history
  GET  /health         — Server status
"""
import os
import shutil
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from auth import register_user, login_user
from document_processor import process_file
from rag_pipeline import build_index, get_answer, is_loaded

app = FastAPI(title="DocuChat API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_FOLDER = "uploads"
ALLOWED = {"pdf", "png", "jpg", "jpeg", "bmp", "tiff"}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ── Request Models ─────────────────────────────────────────────────────────────

class AuthRequest(BaseModel):
    username: str
    password: str


class ChatRequest(BaseModel):
    question: str
    chat_history: Optional[list] = []


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "document_loaded": is_loaded()}


@app.post("/auth/register")
def register(req: AuthRequest):
    result = register_user(req.username, req.password)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@app.post("/auth/login")
def login(req: AuthRequest):
    result = login_user(req.username, req.password)
    if not result["success"]:
        raise HTTPException(status_code=401, detail=result["message"])
    return result


@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: .{ext}. Use PDF, PNG, or JPG.")

    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        documents = process_file(file_path)
        stats = build_index(documents)
        stats["filename"] = file.filename
        return {"success": True, "stats": stats}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@app.post("/chat")
def chat(req: ChatRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    if not is_loaded():
        raise HTTPException(status_code=400, detail="No document loaded. Please upload a document first.")
    result = get_answer(req.question, req.chat_history)
    return result