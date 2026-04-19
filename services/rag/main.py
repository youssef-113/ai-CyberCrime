"""RAG Service - Stage 3b: Legal Retrieval"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import chromadb
from chromadb.utils import embedding_functions
import os

app = FastAPI(title="RAG Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize ChromaDB
chroma_client = chromadb.PersistentClient(path="/data/law_db")

default_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)

# Get or create collection
collection = chroma_client.get_or_create_collection(
    name="egyptian_law",
    embedding_function=default_ef
)

class RetrieveRequest(BaseModel):
    query: str
    crime_type: str
    top_k: int = 5

class LawArticle(BaseModel):
    article_number: str
    law: str
    text: str
    relevance_score: float
    penalty_ar: Optional[str] = None

class RetrieveResponse(BaseModel):
    articles: List[LawArticle]

@app.get("/health")
def health():
    count = collection.count()
    return {"status": "healthy", "service": "rag", "articles_indexed": count}

@app.post("/retrieve", response_model=RetrieveResponse)
async def retrieve(request: RetrieveRequest):
    """Retrieve relevant law articles"""
    
    # Enhance query with crime type
    enhanced_query = f"{request.crime_type}: {request.query}"
    
    # Query ChromaDB
    results = collection.query(
        query_texts=[enhanced_query],
        n_results=request.top_k,
        include=["documents", "metadatas", "distances"]
    )
    
    articles = []
    for i, (doc, meta, dist) in enumerate(zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0]
    )):
        articles.append(LawArticle(
            article_number=meta.get("article_number", "Unknown"),
            law=meta.get("law", "Unknown"),
            text=doc,
            relevance_score=round(1 - dist, 3),  # Convert distance to similarity
            penalty_ar=meta.get("penalty_ar")
        ))
    
    return RetrieveResponse(articles=articles)

@app.post("/index")
async def index_articles(articles: List[dict]):
    """Index law articles (run once)"""
    
    ids = [f"article_{i}" for i in range(len(articles))]
    texts = [a["text"] for a in articles]
    metadatas = [{"article_number": a["article_number"], "law": a["law"]} for a in articles]
    
    collection.add(
        ids=ids,
        documents=texts,
        metadatas=metadatas
    )
    
    return {"indexed": len(articles)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
