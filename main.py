# main.py
from fastapi import FastAPI
from pydantic import BaseModel
from langchain_qdrant import QdrantVectorStore
from langchain_openai import OpenAIEmbeddings
from openai import OpenAI
from dotenv import load_dotenv
import os

# Load env variables
load_dotenv()

app = FastAPI()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Initialize embeddings & vector store
embedding_model = OpenAIEmbeddings(model="text-embedding-3-large")

vector_db = QdrantVectorStore.from_existing_collection(
    url=os.getenv("QDRANT_URL"),
    api_key=os.getenv("QDRANT_API_KEY"),
    collection_name="learning_vector_store",
    embedding=embedding_model
)

class QueryRequest(BaseModel):
    query: str

@app.post("/ask")
def ask_question(request: QueryRequest):
    query = request.query

    # Vector search
    search_results = vector_db.similarity_search(query=query)

    context = "\n\n".join([
        f"Page Content: {r.page_content}\nPage Number: {r.metadata['page_label']}\nFile Location: {r.metadata['source']}"
        for r in search_results
    ])

    # System Prompt
    SYSTEM_PROMPT = f"""
        You are a helpful assistant who answers user query based on the context retrieved from a PDF file along with page_contents and page number.
        You should only answer based on the following context and navigate the user to open the right page number to know more.
        Context:
        {context}
    """

    chat_completion = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": query}
        ]
    )

    return {"answer": chat_completion.choices[0].message.content}

# Run with: uvicorn main:app --reload --port 8000
