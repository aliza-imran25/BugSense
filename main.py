from input_parser import InputParser
from prompt_engine import PromptEngine
from agent import BugSenseAgent
from output_formatter import OutputFormatter

def main():
    print("\n🐛  BugSense — AI Bug Analyst")
    print("Paste your code below. Type END on a new line when done.\n")

    # Collect multi-line code from CLI
    lines = []
    while True:
        line = input()
        if line.strip() == "END":
            break
        lines.append(line)
    code_input = "\n".join(lines)

    error_msg = input("\nError message (press Enter to skip): ").strip()

    # Pipeline: parse → prompt → call LLM → format
    parser   = InputParser()
    engine   = PromptEngine()
    agent    = BugSenseAgent()
    renderer = OutputFormatter()

    parsed   = parser.parse(code_input, error_msg)
    prompt   = engine.build(parsed)
    response = agent.run(prompt)
    renderer.display(response)

if __name__ == "__main__":
    main()