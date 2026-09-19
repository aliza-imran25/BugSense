import os

import streamlit as st
from dotenv import load_dotenv

from agent import AgentError, BugSenseAgent
from input_parser import InputParser
from output_formatter import OutputFormatter

load_dotenv()

st.set_page_config(page_title="BugSense AI", page_icon="🐛", layout="wide")
st.title("🐛 BugSense — AI Bug Analyst")
st.caption("Paste a snippet or upload files. Analysis is sent to the Gemini API.")


@st.cache_resource
def get_parser() -> InputParser:
    return InputParser()


@st.cache_resource
def get_formatter() -> OutputFormatter:
    return OutputFormatter()


@st.cache_resource
def get_agent() -> BugSenseAgent:
    return BugSenseAgent()


def render_result(parsed: dict, response: str) -> None:
    for warning in parsed.get("warnings") or []:
        st.warning(warning)
    st.markdown(get_formatter().to_markdown(response))


def analyze_code(code: str, error: str = "", filename: str = "") -> None:
    parsed = get_parser().parse(code, error, filename=filename)
    if not parsed["code"].strip():
        st.warning("That file or snippet is empty.")
        return
    try:
        with st.spinner(f"Analyzing {filename or 'snippet'}..."):
            response = get_agent().analyze(parsed)
        render_result(parsed, response)
    except AgentError as exc:
        st.error(str(exc))


if not BugSenseAgent.api_key_configured():
    st.error(
        "GEMINI_API_KEY is not set. Copy `.env.example` to `.env` in the project root "
        "and restart the app."
    )
    st.stop()

parser_limit = get_parser().MAX_LINES
tab1, tab2 = st.tabs(["🚀 Paste Code", "📁 Upload Files"])

with tab1:
    st.subheader("Paste your code snippet")
    raw_code = st.text_area(
        "Paste code here:",
        height=300,
        placeholder="def my_function():...",
        help=f"Inputs longer than {parser_limit} lines are truncated.",
    )
    error_msg = st.text_input(
        "Error message (optional):",
        placeholder="e.g., TypeError: ...",
    )

    if st.button("Analyze Snippet", type="primary"):
        if raw_code.strip():
            st.divider()
            analyze_code(raw_code, error_msg)
        else:
            st.warning("Please paste some code first.")

with tab2:
    st.subheader("Upload files or a folder")
    upload_mode = st.toggle(
        "Folder upload mode",
        help="Select a directory (Streamlit 1.57+). Only matching source files are kept.",
    )
    uploaded_files = st.file_uploader(
        "Select files",
        accept_multiple_files="directory" if upload_mode else True,
        type=["py", "java", "c", "h", "cpp", "cc", "js", "ts"],
    )
    shared_error = st.text_input(
        "Shared error message (optional, applied to every file):",
        key="upload_error",
        placeholder="e.g., NullPointerException",
    )

    if uploaded_files and st.button("Analyze All Files", type="primary"):
        for uploaded_file in uploaded_files:
            name = os.path.basename(uploaded_file.name.replace("\\", "/"))
            display_name = uploaded_file.name
            with st.expander(f"📄 {display_name}", expanded=False):
                try:
                    code_content = uploaded_file.getvalue().decode("utf-8")
                except UnicodeDecodeError:
                    st.error(f"Could not decode {display_name} as UTF-8.")
                    continue
                analyze_code(code_content, shared_error, filename=name)
