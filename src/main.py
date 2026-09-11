import os

# Raise qwen-agent's per-run LLM call cap BEFORE any qwen_agent import reads
# it. The default (20) silently truncates search-heavy sub-agents mid-loop.
os.environ.setdefault('QWEN_AGENT_MAX_LLM_CALL_PER_RUN', '40')

import argparse

from qwen_agent.log import logger

from src.agent.main_agent import run_3wagent
from src.websearch.supervisor import OpenWebSearchSupervisor


def parse_args():
    parser = argparse.ArgumentParser(description = "3wagent")
    parser.add_argument("-d", "--DEBUG", default=False, action="store_true", help="DEBUG Mode")
    parser.add_argument(
        "--cli",
        action="store_true",
        help="start an interactive terminal session instead of the WebUI",
    )
    parser.add_argument(
        "-p", "--provider", help="LLM provider from the selected LLM config"
    )
    parser.add_argument("-m", "--model", default=None, help="override the provider's model name")
    parser.add_argument(
        "--llm-config",
        default=None,
        help="path to an alternative provider YAML (default: src/config/llm.yaml)",
    )

    return parser.parse_args()

def main():
    args = parse_args()

    # DEBUG Mode; the per-run log file is attached at the start of each run
    if args.DEBUG :
        logger.setLevel('DEBUG')

    with OpenWebSearchSupervisor():
        runner = run_3wagent
        if args.cli:
            # Keep terminal-only use independent of Gradio imports.
            from src.agent.cli import run_cli_3wagent

            runner = run_cli_3wagent
        runner(
            model_name=args.model,
            provider=args.provider,
            config_path=args.llm_config,
        )

if __name__ == "__main__":
    main()
