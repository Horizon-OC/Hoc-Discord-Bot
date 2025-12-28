import os

class Config:
    # Bot Configuration
    TOKEN = os.environ('TOKEN') 
    PREFIX = os.environ('PREFIX', '?')
    
    # Database Configuration
    DATABASE_PATH = os.environ('DATABASE_PATH', 'data/bot.db')
    
    # Logging Configuration
    LOG_LEVEL = os.environ('LOG_LEVEL', 'INFO')
    LOG_FILE = os.environ('LOG_FILE', 'data/logs/bot.log')
    MOD_LOG_FILE = os.environ('MOD_LOG_FILE', 'data/logs/mod.log')
    
    # Bot Settings
    EMBED_COLOR = int(os.environ('EMBED_COLOR', '27d3e8'), 16)
    ERROR_COLOR = int(os.environ('ERROR_COLOR', 'ff0000'), 16)
    SUCCESS_COLOR = int(os.environ('SUCCESS_COLOR', '00ff00'), 16)
    WARNING_COLOR = int(os.environ('WARNING_COLOR', 'ffaa00'), 16)
    
    # Cache TTL (in seconds)
    CACHE_TTL = int(os.environ('CACHE_TTL', 3600))
    
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        if not cls.TOKEN:
            raise ValueError("TOKEN is required in environment variables")
        return True

