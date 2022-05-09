import json

ENV_FILE="litmus-config/env.json"
DEFAULT_ENV = {
    "clspv": "clspv",
    "cppCompiler": "c++"
}

class LitmusEnv:
    
    ENV_FILE="litmus-config/env.json"
    DEFAULT_ENV = {
        "clspv": "clspv",
        "cppCompiler": "c++"
    }

    def __init__(self):
        with open(self.ENV_FILE, "r") as env_file:
            self.litmus_env = json.loads(env_file.read())

    def get(self, key):
        if key in self.litmus_env:
            return self.litmus_env[key]
        else:
            return self.DEFAULT_ENV[key]
