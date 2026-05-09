import streamlit as st
from agent import BugSenseAgent
from input_parser import InputParser
from prompt_engine import PromptEngine

st.set_page_config(page_title="BugSense AI", page_icon="🐛", layout="wide")

st.title("🐛 BugSense — AI Bug Analyst")

# Initialize Logic
parser = InputParser()
engine = PromptEngine()
agent = BugSenseAgent()

# Create Tabs for different input methods
tab1, tab2 = st.tabs(["🚀 Paste Code", "📁 Upload Project"])

with tab1:
    st.subheader("Paste your code snippet")
    raw_code = st.text_area("Paste code here:", height=300, placeholder="def my_function():...")
    error_msg = st.text_input("Error message (optional):", placeholder="e.g., TypeError: ...")
    
    if st.button("Analyze Snippet"):
        if raw_code.strip():
            with st.spinner("Analyzing snippet..."):
                parsed = parser.parse(raw_code, error_msg)
                response = agent.run(engine.build(parsed))
                
                st.divider()
                st.markdown(response) # Renders the [Bug Type], etc.
        else:
            st.warning("Please paste some code first!")

with tab2:
    st.subheader("Upload files or a folder")
    # Streamlit 2026 allows directory and multi-file selection
    upload_mode = st.toggle("Folder Upload Mode", help="Enable to upload entire directories")
    
    uploaded_files = st.file_uploader(
        "Select Files", 
        accept_multiple_files="directory" if upload_mode else True,
        type=["py", "java", "c"]
    )

    if uploaded_files:
        if st.button("Analyze All Files"):
            for uploaded_file in uploaded_files:
                code_content = uploaded_file.getvalue().decode("utf-8")
                
                with st.expander(f"📄 {uploaded_file.name}", expanded=False):
                    parsed = parser.parse(code_content)
                    with st.spinner(f"Analyzing {uploaded_file.name}..."):
                        response = agent.run(engine.build(parsed))
                        st.markdown(response)