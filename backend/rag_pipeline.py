"""
rag_pipeline.py — RAG pipeline using ChromaDB + Gemini Embedding 2 + Groq.

Embeddings : gemini-embedding-2-preview  (Google AI Studio, free tier)
             RETRIEVAL_DOCUMENT task for indexing
             RETRIEVAL_QUERY    task for searching (better retrieval accuracy)
Vector DB  : ChromaDB  (persists to disk, survives restarts)
LLM        : llama-3.1-8b-instant via Groq API (free tier)
Chat memory: last 6 turns injected as context messages
"""

import os
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_groq import ChatGroq

load_dotenv(dotenv_path="../.env")

CHROMA_DIR      = "chroma_db"
COLLECTION      = "documents"
EMBEDDING_MODEL = "gemini-embedding-2-preview"
EMBED_DIM       = 768
GROQ_MODEL      = "llama-3.1-8b-instant"

_doc_embeddings   = None
_query_embeddings = None
_vectorstore      = None


def _get_google_api_key() -> str:
    key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "GOOGLE_API_KEY not set. "
            "Get a free key at https://aistudio.google.com/apikey and add it to .env"
        )
    return key


def _get_doc_embeddings() -> GoogleGenerativeAIEmbeddings:
    global _doc_embeddings
    if _doc_embeddings is None:
        print("[RAG] Loading Gemini document embeddings...")
        _doc_embeddings = GoogleGenerativeAIEmbeddings(
            model=EMBEDDING_MODEL,
            task_type="RETRIEVAL_DOCUMENT",
            google_api_key=_get_google_api_key(),
            output_dimensionality=EMBED_DIM,
        )
        print("[RAG] Document embeddings ready ✓")
    return _doc_embeddings


def _get_query_embeddings() -> GoogleGenerativeAIEmbeddings:
    global _query_embeddings
    if _query_embeddings is None:
        _query_embeddings = GoogleGenerativeAIEmbeddings(
            model=EMBEDDING_MODEL,
            task_type="RETRIEVAL_QUERY",
            google_api_key=_get_google_api_key(),
            output_dimensionality=EMBED_DIM,
        )
    return _query_embeddings


def build_index(documents: list[Document]) -> dict:
    global _vectorstore

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(documents)

    if not chunks:
        raise ValueError("No content could be extracted from the document.")

    os.makedirs(CHROMA_DIR, exist_ok=True)

    if _vectorstore is not None:
        try:
            _vectorstore.delete_collection()
        except Exception:
            pass

    print(f"[RAG] Embedding {len(chunks)} chunks with {EMBEDDING_MODEL}...")
    _vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=_get_doc_embeddings(),
        persist_directory=CHROMA_DIR,
        collection_name=COLLECTION,
    )
    print("[RAG] ChromaDB index built ✓")

    return {
        "chunks": len(chunks),
        "documents": len(documents),
        "embedding_model": EMBEDDING_MODEL,
        "dimensions": EMBED_DIM,
    }


SYSTEM_TEMPLATE = """\
You are DocuChat — a precise, helpful document analysis assistant.

Rules:
- Answer ONLY using the document context provided below.
- If the answer is not in the context, say: "I couldn't find that in the document."
- Be concise and clear. Reference page numbers when relevant (e.g. "On page 3...").
- For tables, explain the data clearly in plain language.

Document Context:
{context}
"""


def get_answer(question: str, chat_history: list[dict] | None = None) -> dict:
    global _vectorstore

    if _vectorstore is None:
        return {
            "answer": "⚠️ No document loaded. Please upload a PDF or image first.",
            "sources": [],
        }

    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if not groq_key:
        return {
            "answer": "⚠️ GROQ_API_KEY not found. Add it to your .env file.",
            "sources": [],
        }

    try:
        query_vector = _get_query_embeddings().embed_query(question)
    except Exception as e:
        return {
            "answer": f"⚠️ Embedding error: {str(e)}. Check your GOOGLE_API_KEY.",
            "sources": [],
        }

    raw_results = _vectorstore.similarity_search_by_vector_with_relevance_scores(
        embedding=query_vector,
        k=4,
    )

    context_parts, sources = [], []
    for doc, score in raw_results:
        context_parts.append(doc.page_content)
        sources.append({
            "content":   doc.page_content[:250],
            "page":      doc.metadata.get("page", "N/A"),
            "source":    doc.metadata.get("source", ""),
            "type":      doc.metadata.get("type", "text"),
            "relevance": round(max(0.0, (1.0 - float(score))) * 100, 1),
        })

    context = "\n\n---\n\n".join(context_parts)

    messages = [SystemMessage(content=SYSTEM_TEMPLATE.format(context=context))]

    for msg in (chat_history or [])[-6:]:
        role    = msg.get("role", "")
        content = msg.get("content", "")
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "bot":
            messages.append(SystemMessage(content=f"[Your previous answer]: {content}"))

    messages.append(HumanMessage(content=question))

    llm = ChatGroq(
        groq_api_key=groq_key,
        model_name=GROQ_MODEL,
        temperature=0.1,
        max_tokens=1024,
    )
    response = llm.invoke(messages)

    return {
        "answer":  response.content,
        "sources": sources,
    }


def is_loaded() -> bool:
    return _vectorstore is not None