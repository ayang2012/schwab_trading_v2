"""Schwab API configuration.

This file handles Schwab API credentials and settings.
"""
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
    # Load .env from the project root directory
    env_path = Path(__file__).parent.parent / '.env'
    load_dotenv(env_path)
except ImportError:
    pass  # dotenv is optional


@dataclass
class SchwabConfig:
    """Configuration for Schwab API client."""
    app_key: Optional[str] = None
    app_secret: Optional[str] = None
    redirect_uri: str = "https://localhost:8080"
    token_path: str = "./data/auth/schwab_tokens.json"
    
    @classmethod
    def from_env(cls) -> "SchwabConfig":
        """Load configuration from environment variables or .env file.
        
        Expected environment variables or .env file entries:
        - app_key: Your Schwab API app key
        - app_secret: Your Schwab API app secret  
        - callback_url: OAuth redirect URI (optional)
        - token_path: Path to store tokens (optional)
        """
        return cls(
            app_key=os.getenv("app_key") or os.getenv("SCHWAB_APP_KEY"),
            app_secret=os.getenv("app_secret") or os.getenv("SCHWAB_APP_SECRET"),
            redirect_uri=os.getenv("callback_url") or os.getenv("SCHWAB_REDIRECT_URI", "https://127.0.0.1"),
            token_path=os.getenv("token_path") or os.getenv("SCHWAB_TOKEN_PATH", "./data/auth/schwab_tokens.json")
        )
    
    def is_valid(self) -> bool:
        """Check if configuration has required fields."""
        return bool(self.app_key and self.app_secret)