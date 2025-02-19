import logging
import os
from datetime import datetime
from colorama import Fore, Style
import yaml

def load_settings():
    with open('config.yml', 'r') as file:
        return yaml.safe_load(file)

def setup_logger():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    return logging.getLogger(__name__)

def writeLog(message: str, type: str, writeTofile: bool = True) -> None:
    settings = load_settings()
    loggingLevel = settings.get('debug', {}).get('logging_level', 5)
    log_levels = {
        "ALWAYS": (Fore.CYAN, 0),
        "ERROR": (Fore.RED, 1),
        "WARNING": (Fore.YELLOW, 2),
        "SUCCESS": (Fore.GREEN, 2),
        "INFO": (Fore.WHITE, 3),
        "DEBUG": (Fore.BLUE, 4),
        "TRACE": (Fore.MAGENTA, 5)
    }
    color, level = log_levels.get(type.upper(), (Fore.LIGHTBLACK_EX, 0))
    if loggingLevel >= level:
        print(f"{color}[{type.upper()}][{datetime.now().strftime('%Y%B%d@%H:%M:%S')}] {message}{Style.RESET_ALL}")
        if writeTofile:
            _scriptdir = os.path.dirname(os.path.realpath(__file__))
            log_dir = os.path.join(_scriptdir, "logs")
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            log_file_path = os.path.join(log_dir, f"{datetime.now().strftime('%Y%B%d')}.log")
            with open(log_file_path, "a", encoding="utf-8") as logFile:
                logFile.write(f"[{type.upper()}][{datetime.now().strftime('%Y%B%d@%H:%M:%S')}] {message}\n")