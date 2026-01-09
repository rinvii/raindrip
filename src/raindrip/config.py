import json
from pathlib import Path
from typing import Optional
from pydantic import BaseModel


class Config(BaseModel):
    token: Optional[str] = None


CONFIG_DIR = Path.home() / ".config" / "raindrip"
CONFIG_FILE = CONFIG_DIR / "config.json"


def load_config() -> Config:
    """Load configuration from disk."""
    if not CONFIG_FILE.exists():
        return Config()
    try:
        with open(CONFIG_FILE, "r") as f:
            return Config.model_validate(json.load(f))
    except Exception:
        return Config()


def save_config(config: Config) -> None:
    """Save configuration to disk with secure permissions."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    # Set directory permissions to 700 (drwx------)
    CONFIG_DIR.chmod(0o700)
    
    # Create file with 600 permissions (rw-------)
    if not CONFIG_FILE.exists():
        CONFIG_FILE.touch(mode=0o600)
    else:
        CONFIG_FILE.chmod(0o600)
        
    with open(CONFIG_FILE, "w") as f:
        json.dump(config.model_dump(), f, indent=2)


def delete_config() -> None:
    """Delete the configuration file."""
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()
