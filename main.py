from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
# from langchain_community.embeddings import OpenAIEmbeddings
from langchain_openai import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
import os
import io
from pypdf import PdfReader  # Using pypdf instead of PyMuPDF
from dotenv import load_dotenv
import uuid


load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION_NAME = "pdf_collection"
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")


# Init Qdrant
qdrant = QdrantClient(
    url=QDRANT_URL,
    api_key=QDRANT_API_KEY if QDRANT_API_KEY else None
)


# Init embeddings
embeddings = OpenAIEmbeddings(api_key=OPENAI_API_KEY)

# Create collection if it doesn't exist
try:
    if not qdrant.collection_exists(COLLECTION_NAME):
        qdrant.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=1536, distance=Distance.COSINE)
        )
        print(f"Created collection: {COLLECTION_NAME}")
    else:
        print(f"Collection {COLLECTION_NAME} already exists")
except Exception as e:
    print(f"Error with Qdrant collection: {e}")

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    question: str


@app.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    try:
        # Read the uploaded file
        # pdf_content = await file.read()
        MAX_FILE_SIZE = 10 * 1024 * 1024
        file_size = 0
        pdf_contents = await file.read()
        file_size = len(pdf_contents)
        if file_size > MAX_FILE_SIZE:
            return {"status": "error", "message": "File too large. Max allowed size is 10 MB."}
        
        # Create a BytesIO object from the content
        pdf_file = io.BytesIO(pdf_contents)

        # Extract text using pypdf
        reader = PdfReader(pdf_file)
        text = ""
        
        # Extract text from all pages
        for page_num, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                text += f"\n--- Page {page_num + 1} ---\n"
                text += page_text + "\n"
        
        if not text.strip():
            return {"status": "error", "message": "No text could be extracted from the PDF. The PDF might contain only images or be password protected."}

        # Split into chunks
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, 
            chunk_overlap=200,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )
        chunks = splitter.split_text(text)
        
        if not chunks:
            return {"status": "error", "message": "No chunks could be created from the extracted text"}

        # Generate embeddings for all chunks
        print(f"Generating embeddings for {len(chunks)} chunks...")
        vectors = embeddings.embed_documents(chunks)
        
        # Prepare points for Qdrant
        points = []
        for idx, (chunk, vector) in enumerate(zip(chunks, vectors)):
            points.append({
                "id": str(uuid.uuid4()),
                "vector": vector,
                "payload": {
                    "text": chunk,
                    "filename": file.filename,
                    "chunk_index": idx
                }
            })
        
        # Store in Qdrant
        qdrant.upsert(
            collection_name=COLLECTION_NAME,
            points=points
        )
        
        print(f"Successfully stored {len(chunks)} chunks in Qdrant")

        return {
            "status": "success", 
            "chunks_stored": len(chunks),
            "filename": file.filename,
            "text_length": len(text),
            "pages_processed": len(reader.pages)
        }

    except Exception as e:
        print(f"Error in upload_pdf: {str(e)}")
        return {"status": "error", "message": f"Error processing PDF: {str(e)}"}


@app.post("/ask")
async def ask_question(query: QueryRequest):
    try:
        print(f"Processing question: {query.question}")
        
        # Generate embedding for the query
        query_vector = embeddings.embed_query(query.question)

        # Search for similar chunks in Qdrant
        search_result = qdrant.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector,
            limit=5,
            score_threshold=0.1
        )
        
        if not search_result:
            return {
                "answer": "I couldn't find any relevant information in the uploaded PDF to answer your question.",
                "sources_found": 0
            }

        # Combine context from search results
        context_parts = []
        for hit in search_result:
            context_parts.append(f"{hit.payload['text']}")
        
        context = "\n\n".join(context_parts)
        
        # Simple response based on context (you can integrate with OpenAI's GPT here)
        answer = f"Based on the PDF content, here's what I found:\n\n{context[:1000]}{'...' if len(context) > 1000 else ''}"
        
        return {
            "answer": answer,
            "sources_found": len(search_result),
            "context_length": len(context)
        }

    except Exception as e:
        print(f"Error in ask_question: {str(e)}")
        return {"status": "error", "message": f"Error processing query: {str(e)}"}


@app.get("/")
async def root():
    return {"message": "PDF Reader API is running successfully!"}


@app.get("/health")
async def health_check():
    try:
        # Check Qdrant connection
        collections = qdrant.get_collections()
        
        # Check if our collection exists
        collection_exists = qdrant.collection_exists(COLLECTION_NAME)
        
        return {
            "status": "healthy",
            "qdrant_connected": True,
            "collection_exists": collection_exists,
            "total_collections": len(collections.collections)
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


@app.delete("/clear-collection")
async def clear_collection():
    """Clear all data from the PDF collection"""
    try:
        # Delete and recreate the collection
        if qdrant.collection_exists(COLLECTION_NAME):
            qdrant.delete_collection(COLLECTION_NAME)
        
        qdrant.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=1536, distance=Distance.COSINE)
        )
        
        return {"status": "success", "message": "Collection cleared successfully"}
    except Exception as e:
        return {"status": "error", "message": f"Error clearing collection: {str(e)}"}