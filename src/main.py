from src.agent.MainAgent import run_3wagent
from qwen_agent.log import logger
import argparse
from src.config.logger import SetUpHandler

def parse_args():
    parser = argparse.ArgumentParser(description = "3wagent")
    parser.add_argument("-d", "--DEBUG", default=False, action="store_true", help="DEBUG Mode")
    parser.add_argument("-m", "--model", default="finance-27b", help="model")

    return parser.parse_args()

def main():
    args = parse_args()

    # DEBUG Mode
    if args.DEBUG :
        logger.setLevel('DEBUG')
        logger.addHandler(SetUpHandler(args.model))

    run_3wagent(args.model)

if __name__ == "__main__":
    main()