import os

import streamlit as st
from dotenv import load_dotenv

from agent import AgentError, BugSenseAgent
from git_diff import collect_git_diff
from input_parser import InputParser
from output_formatter import OutputFormatter

load_dotenv()

st.set_page_config(page_title="BugSense AI", page_icon="🐛", layout="wide")
st.title("🐛 BugSense — AI Bug Analyst")
st.caption(
    "Paste a snippet, analyze several files together, or send a git diff. "
    "Code is sent to the Gemini API."
)


@st.cache_resource
def get_parser() -> InputParser:
    return InputParser()


@st.cache_resource
def get_formatter() -> OutputFormatter:
    return OutputFormatter()


@st.cache_resource
def get_agent() -> BugSenseAgent:
    return BugSenseAgent()


def render_warnings(parsed: dict) -> None:
    for warning in parsed.get("warnings") or []:
        st.warning(warning)


def analyze_parsed(parsed: dict, spinner_label: str) -> None:
    if parsed.get("mode") == "files" and not parsed.get("files"):
        st.warning("No source files to analyze.")
        return
    if parsed.get("mode") == "diff" and not (parsed.get("patches") or parsed.get("code", "").strip()):
        st.warning("No diff hunks to analyze.")
        return
    if parsed.get("mode") == "snippet" and not parsed.get("code", "").strip():
        st.warning("That file or snippet is empty.")
        return
    try:
        with st.spinner(spinner_label):
            response = get_agent().analyze(parsed)
        render_warnings(parsed)
        st.markdown(get_formatter().to_markdown(response))
    except AgentError as exc:
        render_warnings(parsed)
        st.error(str(exc))


def decode_upload(uploaded_file) -> str | None:
    try:
        return uploaded_file.getvalue().decode("utf-8")
    except UnicodeDecodeError:
        st.error(f"Could not decode {uploaded_file.name} as UTF-8.")
        return None


if not BugSenseAgent.api_key_configured():
    st.error(
        "GEMINI_API_KEY is not set. Copy `.env.example` to `.env` in the project root, "
        "paste your key after `GEMINI_API_KEY=`, then restart the app."
    )
    st.info("Get a key at https://aistudio.google.com/apikey")
    st.stop()

parser_limit = get_parser().MAX_LINES
tab1, tab2, tab3 = st.tabs(["🚀 Paste Code", "📁 Multi-file", "🔀 Diff"])

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
            parsed = get_parser().parse(raw_code, error_msg)
            analyze_parsed(parsed, "Analyzing snippet...")
        else:
            st.warning("Please paste some code first.")

with tab2:
    st.subheader("Analyze files as one project")
    st.write(
        "Upload several source files (or a folder). BugSense sends them in **one** request "
        "so it can catch caller/callee and import mismatches."
    )
    upload_mode = st.toggle(
        "Folder upload mode",
        help="Select a directory (Streamlit 1.57+). Only matching source files are kept.",
    )
    together = st.toggle(
        "Analyze together (cross-file bugs)",
        value=True,
        help="Off = each file is analyzed on its own.",
    )
    uploaded_files = st.file_uploader(
        "Select files",
        accept_multiple_files="directory" if upload_mode else True,
        type=["py", "java", "c", "h", "cpp", "cc", "js", "ts"],
    )
    shared_error = st.text_input(
        "Error message (optional):",
        key="upload_error",
        placeholder="e.g., NullPointerException",
    )

    if uploaded_files and st.button("Analyze Files", type="primary"):
        items: list[tuple[str, str]] = []
        for uploaded_file in uploaded_files:
            code_content = decode_upload(uploaded_file)
            if code_content is None:
                continue
            name = uploaded_file.name.replace("\\", "/")
            items.append((name, code_content))

        if not items:
            st.warning("No readable source files.")
        elif together:
            parsed = get_parser().parse_files(items, shared_error)
            st.divider()
            st.caption(" · ".join(name for name, _ in items))
            analyze_parsed(parsed, "Analyzing project files together...")
        else:
            for name, code_content in items:
                with st.expander(f"📄 {name}", expanded=False):
                    parsed = get_parser().parse(
                        code_content,
                        shared_error,
                        filename=os.path.basename(name),
                    )
                    analyze_parsed(parsed, f"Analyzing {name}...")

with tab3:
    st.subheader("Analyze a unified diff")
    st.write(
        "Paste a patch, upload a `.diff` / `.patch` file, or run `git diff` in a local repo. "
        "The model focuses on changed hunks — typical real-bug workflow."
    )
    diff_error = st.text_input(
        "Error message (optional):",
        key="diff_error",
        placeholder="e.g., failing test output",
    )
    pasted_diff = st.text_area(
        "Paste unified diff:",
        height=240,
        placeholder="diff --git a/app.py b/app.py\n...",
        key="pasted_diff",
    )
    patch_file = st.file_uploader(
        "Or upload a patch file",
        type=["diff", "patch", "txt"],
        accept_multiple_files=False,
        key="patch_upload",
    )

    if st.button("Analyze Pasted Diff", type="primary"):
        text = pasted_diff
        source = "pasted diff"
        if patch_file is not None and not text.strip():
            decoded = decode_upload(patch_file)
            text = decoded or ""
            source = patch_file.name
        if not text.strip():
            st.warning("Paste a diff or upload a patch file first.")
        else:
            parsed = get_parser().parse_diff(text, diff_error, source=source)
            st.divider()
            analyze_parsed(parsed, "Analyzing diff...")

    st.divider()
    st.markdown("**Local git diff**")
    repo_path = st.text_input("Repository path", value=".", key="repo_path")
    revision = st.text_input("Compare against revision", value="HEAD", key="git_rev")
    staged_only = st.checkbox("Staged changes only (`git diff --cached`)", key="staged")
    pathspec = st.text_input(
        "Optional path filter",
        placeholder="src/ tests/",
        key="pathspec",
    )

    if st.button("Analyze Git Diff"):
        specs = pathspec.split() if pathspec.strip() else None
        try:
            patch_text, source = collect_git_diff(
                repo=repo_path,
                revision=revision or "HEAD",
                staged=staged_only,
                pathspecs=specs,
            )
        except AgentError as exc:
            st.error(str(exc))
        else:
            if not patch_text.strip():
                st.info("Working tree matches that revision — nothing to analyze.")
            else:
                parsed = get_parser().parse_diff(patch_text, diff_error, source=source)
                st.divider()
                with st.expander("Diff sent to the model", expanded=False):
                    st.code(patch_text, language="diff")
                analyze_parsed(parsed, "Analyzing git diff...")
