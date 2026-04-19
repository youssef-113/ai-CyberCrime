"""Build knowledge base from law PDFs - Run once"""
import json
import chromadb
from chromadb.utils import embedding_functions

def build_knowledge_base():
    """Index law articles into ChromaDB"""
    
    client = chromadb.PersistentClient(path="/data/law_db")
    
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    
    collection = client.get_or_create_collection(
        name="egyptian_law",
        embedding_function=ef
    )
    
    # Load parsed articles
    try:
        with open("/data/law/parsed/articles.json", "r", encoding="utf-8") as f:
            articles = json.load(f)
    except FileNotFoundError:
        print("No articles.json found. Creating sample data...")
        articles = [
            {
                "article_number": "25",
                "law": "Law 175/2018",
                "text": "Punishment by imprisonment and fine for unauthorized access to information systems",
                "penalty_ar": "الحبس و الغرامة"
            },
            {
                "article_number": "26",
                "law": "Law 175/2018",
                "text": "Punishment for illegal interception of communications",
                "penalty_ar": "الحبس مدة لا تقل عن سنة"
            }
        ]
    
    # Index articles
    ids = [f"article_{i}" for i in range(len(articles))]
    texts = [a["text"] for a in articles]
    metadatas = [
        {
            "article_number": a["article_number"],
            "law": a["law"],
            "penalty_ar": a.get("penalty_ar", "")
        } for a in articles
    ]
    
    collection.add(
        ids=ids,
        documents=texts,
        metadatas=metadatas
    )
    
    print(f"Indexed {len(articles)} articles")

if __name__ == "__main__":
    build_knowledge_base()
