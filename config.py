import yaml

def load_config():
    with open('config.yml', 'r') as file:
        return yaml.safe_load(file)

config = load_config()