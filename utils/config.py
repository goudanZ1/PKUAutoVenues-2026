from pathlib import Path
from datetime import datetime
from configparser import ConfigParser

PROJECT_DIR = Path(__file__).resolve().parent.parent

LOGS_DIR = PROJECT_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOGS_DIR / f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"

CONFIG_FILE = PROJECT_DIR / "config.ini"
CONFIG = ConfigParser()
CONFIG.read(CONFIG_FILE, encoding="utf-8")
