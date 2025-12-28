import os

class Config:
    # Bot Configuration
    TOKEN = os.getenv("TOKEN")
    PREFIX = os.getenv("PREFIX", "?")

    # Database Configuration
    DATABASE_PATH = os.getenv("DATABASE_PATH", "data/bot.db")

    # Logging Configuration
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", "data/logs/bot.log")
    MOD_LOG_FILE = os.getenv("MOD_LOG_FILE", "data/logs/mod.log")

    # Bot Settings
    EMBED_COLOR = int(os.getenv("EMBED_COLOR", "27d3e8"), 16)
    ERROR_COLOR = int(os.getenv("ERROR_COLOR", "ff0000"), 16)
    SUCCESS_COLOR = int(os.getenv("SUCCESS_COLOR", "00ff00"), 16)
    WARNING_COLOR = int(os.getenv("WARNING_COLOR", "ffaa00"), 16)

    # Cache TTL (in seconds)
    CACHE_TTL = int(os.getenv("CACHE_TTL", "3600"))

    @classmethod
    def validate(cls):
        if not cls.TOKEN:
            raise RuntimeError("TOKEN environment variable is missing")
        return True
