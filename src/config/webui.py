import os

_LOGO_PATH = os.path.join(os.path.dirname(__file__), '..', 'agent', 'assets', 'logo.png')

WEBUI_CHATBOT_CONFIG = {
    "agent.avatar": os.path.abspath(_LOGO_PATH),
    "prompt.suggestions": [
        "hello",
        "hi"
    ]
}
