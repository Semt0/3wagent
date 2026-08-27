import argparse

from qwen_agent.log import logger

from src.agent.main_agent import run_3wagent
from src.config.logger import SetUpHandler
from src.websearch.supervisor import OpenWebSearchSupervisor


def parse_args():
    parser = argparse.ArgumentParser(description = "3wagent")
    parser.add_argument("-d", "--DEBUG", default=False, action="store_true", help="DEBUG Mode")
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

    # DEBUG Mode
    if args.DEBUG :
        logger.setLevel('DEBUG')
        logger.addHandler(SetUpHandler(args.model or args.provider or "llm"))

    with OpenWebSearchSupervisor():
        run_3wagent(
            model_name=args.model,
            provider=args.provider,
            config_path=args.llm_config,
        )

if __name__ == "__main__":
    main()
