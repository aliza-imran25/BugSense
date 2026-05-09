🐛 BugSense — AI-Powered Bug Analyst
BugSense is an intelligent debugging companion designed to help developers and students move beyond simple "fix-it" solutions. Built for the modern web, BugSense analyzes code snippets or entire project directories to identify bug types, explain root causes, and provide optimized, corrected code with educational commentary.

🚀 Features
Multi-Input Modes: Paste raw code snippets or upload entire files and project folders.

Deep Semantic Analysis: Powered by the Gemini 3 Flash model to trace logical, syntax, and runtime errors.

Educational Output: Instead of just providing a fix, it breaks down the analysis into:

[Bug Type]: Categorizes the error (e.g., Logic, Precedence, Type).

[Root Cause]: A step-by-step trace of why the failure occurs.

[Corrected Code]: The fixed solution with inline explanations.

Modern Python Stack: Built using uv for lightning-fast dependency management and Streamlit for a sleek web interface.

🛠️ Tech Stack
Language: Python 3.12+

Framework: Streamlit

AI Engine: Google GenAI SDK (Gemini 3 Flash)

Package Manager: uv

📥 Installation
Ensure you have uv installed, then clone the repository and set up the environment:

Bash
# Clone the repo
git clone https://github.com/your-username/bugsense.git
cd bugsense

# Install dependencies and create venv
uv sync

# Set up your environment variables in a .env file
echo "GEMINI_API_KEY=your_api_key_here" > .env
🖥️ Usage
Run the web application locally:

Bash
uv run streamlit run streamlit_app.py
📂 Project Structure
streamlit_app.py: The web interface and file upload logic.

agent.py: Handles communication with the Gemini API and retry logic.

prompt_engine.py: Defines the persona and structural constraints for the AI.

input_parser.py: Sanitizes code inputs and detects programming languages.

output_formatter.py: (Legacy) CLI formatting for terminal-based runs.