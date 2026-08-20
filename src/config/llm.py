import copy
BASIC_CONFIG = {
    # 远程 llama-server（经本地 SSH 隧道 127.0.0.1:11434 转发）
    "model": "",
    "model_server": "http://127.0.0.1:11434/v1",
    "api_key": "EMPTY",
    "generate_cfg": {
        "temperature": 0.15,
        "top_p": 0.85,
    },
}

# Get A Specific Model Config
def load_llm_config(model_name : str):
    new_config = copy.deepcopy(BASIC_CONFIG)
    new_config["model"] = model_name
    return new_config
