import argparse

from qwen_agent.log import logger

from src.agent.main_agent import run_3wagent


def parse_args():
    parser = argparse.ArgumentParser(description = "3wagent")
    parser.add_argument("-d", "--DEBUG", default=False, action="store_true", help="DEBUG Mode")
    parser.add_argument("-m", "--model", default="finance-27b", help="model")

    return parser.parse_args()

def main():
    args = parse_args()

    # DEBUG Mode; the per-run log file is attached at the start of each run
    if args.DEBUG :
        logger.setLevel('DEBUG')

    run_3wagent(args.model)

if __name__ == "__main__":
    main()