# Multimodal RAG System

A production-ready Retrieval-Augmented Generation (RAG) system supporting PDF ingestion and intelligent querying using local and cloud-based LLM components.

## 🚀 Features
- PDF upload and processing
- Vector search using ChromaDB
- High-quality semantic embeddings via Gemini (embedding-2-preview)
- Local LLM inference via Ollama (Phi) OR low-latency inference via Groq (Llama 3.1)
- FastAPI backend
- Streamlit frontend

## 🧠 Architecture
Frontend → FastAPI → RAG Pipeline → Vector DB → LLM (Ollama / Groq) → Response

## ⚙️ Setup

### Install dependencies
pip install -r requirements.txt

### For local LLM (Ollama)
ollama pull phi  
ollama pull nomic-embed-text  

### Run backend
uvicorn backend.main:app --reload  

### Run frontend
streamlit run frontend/app.py  
