# app.py
import streamlit as st
import requests

st.set_page_config(page_title="📄 PDF Assistant", layout="wide")
st.title("📄 PDF Assistant with Qdrant & OpenAI")

API_URL = "http://127.0.0.1:8000/ask"  # Change if hosted elsewhere

query = st.text_input("Ask something about your PDF:")

if st.button("Ask") and query.strip():
    with st.spinner("Thinking..."):
        response = requests.post(API_URL, json={"query": query})
        if response.status_code == 200:
            st.markdown("### 🤖 Answer:")
            st.write(response.json().get("answer", "No answer found."))
        else:
            st.error("Something went wrong with the request.")
