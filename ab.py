import streamlit as st
import os
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
PAGE_TITLE = "PGVCL Smart Assistant"
PRIMARY_COLOR = "#007bff"
SECONDARY_COLOR = "#6c757d"

# --- API Key ---
api_key = os.getenv("GOOGLE_AI_API_KEY")
if not api_key:
    st.error("Please set the GOOGLE_AI_API_KEY environment variable.")
    st.stop()
genai.configure(api_key=api_key)

# --- Model ---
MODEL_NAME = "gemini-1.5-pro-latest"
if "model" not in st.session_state:
    st.session_state["model"] = genai.GenerativeModel(model_name=MODEL_NAME)

# --- Session State ---
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []

if "authentication_status" not in st.session_state:
    st.session_state["authentication_status"] = None  # Possible values: True, False, None

# --- Document Storage ---
UPLOAD_FOLDER = "uploaded_docs"
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# --- System Prompt ---
SYSTEM_PROMPT = """You are a helpful assistant designed to answer questions specifically about the provided PGVCL (Paschim Gujarat Vij Company Limited) document.

*   Answer questions to the point and concisely.
*   If you are unsure about what the user is asking or the question is ambiguous, ask for clarification.
*   **ONLY answer questions related to the content of the provided PGVCL document.** If the user asks about something else, respond with: "I am the PGVCL chatbot. I can only answer questions regarding the content of the document selected."
*   If the information is not found in the document, respond with "I am sorry, but I am unable to find the answer to your question in the provided document."
"""

# --- Authentication ---
ADMIN_USERNAME = "admin"  # Change this!
ADMIN_PASSWORD = "password123"  # NEVER store plain text passwords!  Change this immediately!

def check_password():
    """Authenticates the user and sets session state."""
    if st.session_state["authentication_status"] is None:  # Only show login form if not already authenticated
        username = st.sidebar.text_input("Username")
        password = st.sidebar.text_input("Password", type="password")

        if st.sidebar.button("Login"):
            if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
                st.session_state["authentication_status"] = True
                st.sidebar.success("Logged in as admin")
                st.rerun()  # Rerun to show the admin page
            else:
                st.session_state["authentication_status"] = False
                st.sidebar.error("Incorrect Username/Password")
                return False

        return False  # Return False by default (not logged in)
    elif st.session_state["authentication_status"] == True:
        return True  # Already logged in
    else:
        return False # Login failed

def load_document(document_path):
    """Loads document data from the specified path."""
    try:
        with open(document_path, "rb") as f:
            document_data = f.read()
        return document_data
    except Exception as e:
        st.error(f"Error loading document: {e}")
        return None


def generate_response(prompt, model, document_data=None, system_prompt=None):
    """Generates a response from the Gemini model."""
    try:
        if document_data:
            contents = [
                {
                    "role": "user",
                    "parts": [
                        {"mime_type": "application/pdf", "data": document_data},
                        f"{system_prompt}\n{prompt}",  # combine prompt
                    ],
                },
            ]
        else:
            return "Please select a PGVCL document to ask questions about."

        response = model.generate_content(contents)
        response.resolve()
        if response.prompt_feedback:
            if response.prompt_feedback.block_reason is not None:
                st.warning(
                    f"The query was blocked: {response.prompt_feedback.block_reason}"
                )
                return None
        return response.text

    except Exception as e:
        st.error(f"Error generating response: {e}")
        return None


# --- Admin Page ---
def admin_page():
    st.title("Admin Side - Document Management")
    uploaded_file = st.file_uploader("Upload PGVCL Document (PDF)", type=["pdf"])

    if uploaded_file is not None:
        file_path = os.path.join(UPLOAD_FOLDER, uploaded_file.name)
        try:
            with open(file_path, "wb") as f:
                f.write(uploaded_file.read())
            st.success(f"File '{uploaded_file.name}' saved to '{UPLOAD_FOLDER}'")
        except Exception as e:
            st.error(f"Error saving file: {e}")

    # Display existing files with delete option
    st.subheader("Existing Documents")
    files = [f for f in os.listdir(UPLOAD_FOLDER) if f.endswith(".pdf")]
    if files:
        for filename in files:
            col1, col2 = st.columns([0.8, 0.2])  # Adjust column widths
            with col1:
                st.write(filename)
            with col2:
                if st.button("Delete", key=f"delete_{filename}"):
                    file_path = os.path.join(UPLOAD_FOLDER, filename)
                    try:
                        os.remove(file_path)
                        st.success(f"File '{filename}' deleted.")
                        st.rerun()  # Refresh the page
                    except Exception as e:
                        st.error(f"Error deleting file: {e}")
    else:
        st.info("No documents uploaded yet.")


# --- User Page ---
def user_page():
    st.title("User Side - PGVCL Smart Assistant")

    # Get available documents from the upload folder
    available_documents = [
        f for f in os.listdir(UPLOAD_FOLDER) if f.endswith(".pdf")
    ]

    with st.sidebar:
        st.subheader("Document Selection")
        selected_document = st.selectbox(
            "Select a PGVCL Document:", [""] + available_documents
        )

        document_data = None
        if selected_document:
            document_path = os.path.join(UPLOAD_FOLDER, selected_document)
            document_data = load_document(document_path)
            if document_data is None:
                st.error("Failed to load selected document.")

        # Store document data in session state
        st.session_state["document_data"] = document_data

    if st.session_state.get("document_data") is not None:
        user_prompt = st.text_input(
            "Ask your question about the selected PGVCL document:",
            key="prompt_input",
            placeholder="e.g., What are the charges for a 10kW connection?",
        )

        if user_prompt:
            with st.spinner("Generating response..."):
                gemini_response = generate_response(
                    user_prompt,
                    st.session_state["model"],
                    st.session_state["document_data"],
                    SYSTEM_PROMPT,  # Pass System Prompt
                )

            if gemini_response:
                st.session_state["chat_history"].append({"role": "user", "content": user_prompt})
                st.session_state["chat_history"].append({"role": "model", "content": gemini_response})

        st.subheader("Chat History")
        for message in st.session_state["chat_history"]:
            role = message["role"].capitalize()
            content = message["content"]
            if role == "User":
                st.markdown(
                    f'<div style="text-align: left; margin-bottom: 10px;">'
                    f'<strong style="color: {PRIMARY_COLOR};">{role}:</strong> {content}</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div style="text-align: left; margin-bottom: 10px;">'
                    f'<strong style="color: {SECONDARY_COLOR};">{role}:</strong> {content}</div>',
                    unsafe_allow_html=True,
                )
    else:
        st.info("Please select a PGVCL document from the sidebar to ask questions about.")


# --- Main App Flow ---
st.set_page_config(page_title=PAGE_TITLE, page_icon=":bulb:", layout="wide")

page = st.sidebar.radio("Select Page:", ("User Side", "Admin Side"))

if page == "Admin Side":
    if check_password(): # Check authentication first
        admin_page()
else:
    user_page()