import streamlit as st
import requests
import time

API_URL = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="PDF Chat Assistant",
    page_icon="📄",
    layout="wide"
)

st.title("📄 Chat with Your PDF")
st.markdown("Upload a PDF document and ask questions about its content!")

# Check API health
def check_api_health():
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        return response.status_code == 200
    except:
        return False

# API Health Status
col1, col2 = st.columns([3, 1])
with col2:
    if check_api_health():
        st.success("🟢 API Connected")
    else:
        st.error("🔴 API Disconnected")
        st.warning("Make sure your FastAPI server is running on port 8000")

# Initialize session state
if 'pdf_uploaded' not in st.session_state:
    st.session_state.pdf_uploaded = False
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

# Upload Section
st.header("1. Upload Your PDF")
pdf_file = st.file_uploader("Choose a PDF file", type=["pdf"])

if pdf_file is not None:
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB in bytes
    if pdf_file.size > MAX_FILE_SIZE:
        st.error("❌ File too large! Max allowed size is 10 MB.")

    else:
        st.info(f"📎 File selected: {pdf_file.name} ({pdf_file.size} bytes)")

        if st.button("🚀 Process PDF", type="primary"):
            with st.spinner("Processing PDF... This may take a moment."):
                try:
                    files = {"file": (pdf_file.name, pdf_file, "application/pdf")}
                    response = requests.post(f"{API_URL}/upload-pdf", files=files, timeout=60)
                    
                    if response.status_code == 200:
                        result = response.json()
                        if result.get("status") == "success":
                            st.success("✅ PDF processed successfully!")
                            st.session_state.pdf_uploaded = True
                            st.info(f"📊 Created {result.get('chunks_stored', 0)} text chunks from your PDF")
                        else:
                            st.error(f"❌ Error: {result.get('message', 'Unknown error')}")
                    else:
                        st.error(f"❌ Server error: {response.status_code}")
                        
                except requests.exceptions.Timeout:
                    st.error("⏱️ Request timed out. Please try again.")
                except requests.exceptions.ConnectionError:
                    st.error("🔌 Cannot connect to the API. Make sure the server is running.")
                except Exception as e:
                    st.error(f"❌ Unexpected error: {str(e)}")

# Chat Section
st.header("2. Ask Questions")

if st.session_state.pdf_uploaded:
    st.success("📖 PDF is ready for questions!")
else:
    st.warning("⚠️ Please upload and process a PDF first.")

# Display chat history
if st.session_state.chat_history:
    st.subheader("💬 Chat History")
    for i, (question, answer) in enumerate(st.session_state.chat_history):
        with st.expander(f"Q{i+1}: {question[:50]}{'...' if len(question) > 50 else ''}"):
            st.write("**Question:**", question)
            st.write("**Answer:**", answer)

# Question input
question = st.text_input("💭 Ask a question about your PDF:", 
                        placeholder="e.g., What is the main topic of this document?")

col1, col2 = st.columns([1, 4])
with col1:
    ask_button = st.button("🔍 Ask", type="primary")

if ask_button and question.strip():
    if not st.session_state.pdf_uploaded:
        st.error("Please upload and process a PDF first!")
    else:
        with st.spinner("Thinking... 🤔"):
            try:
                response = requests.post(
                    f"{API_URL}/ask", 
                    json={"question": question},
                    timeout=30
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get("status") == "error":
                        st.error(f"❌ Error: {result.get('message')}")
                    else:
                        answer = result.get("answer", "No answer received")
                        st.session_state.chat_history.append((question, answer))
                        
                        # Display the answer
                        st.success("✅ Answer found!")
                        st.write("**Answer:**")
                        st.write(answer)
                        
                        # Show additional info if available
                        if "sources_found" in result:
                            st.info(f"📚 Found {result['sources_found']} relevant sections")
                        
                else:
                    st.error(f"❌ Server error: {response.status_code}")
                    
            except requests.exceptions.Timeout:
                st.error("⏱️ Request timed out. Please try again.")
            except requests.exceptions.ConnectionError:
                st.error("🔌 Cannot connect to the API. Make sure the server is running.")
            except Exception as e:
                st.error(f"❌ Unexpected error: {str(e)}")

elif ask_button and not question.strip():
    st.warning("⚠️ Please enter a question!")

# Clear chat history
if st.session_state.chat_history:
    if st.button("🗑️ Clear Chat History"):
        st.session_state.chat_history = []
        st.rerun()

# Footer
st.markdown("---")
st.markdown("💡 **Tips:**")
st.markdown("- Make sure your PDF contains readable text (not just images)")
st.markdown("- Try specific questions for better results")
st.markdown("- The AI will search through your document to find relevant information")