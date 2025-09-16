import os
from datetime import timedelta


class BaseConfig:
    """Base configuration class with common settings."""
    APP_NAME = "Invoice OCR API"
    VERSION = "1.0.0"
    ENV = os.environ.get("FLASK_ENV", "production")
    DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"

    # Security
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "change-me-in-production")
    API_SECRET_KEY = os.environ.get("API_SECRET_KEY", "")

    # Upload/Output
    BASE_DIR = os.getcwd()
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", os.path.join(BASE_DIR, "uploads"))
    OUTPUT_FOLDER = os.environ.get("OUTPUT_FOLDER", os.path.join(BASE_DIR, "outputs"))
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 50 * 1024 * 1024))  # 50 MB
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf", "bmp", "tiff", "tif", "webp"}

    # Azure OpenAI
    AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
    AZURE_OPENAI_KEY = os.environ.get("AZURE_OPENAI_KEY", "")
    AZURE_DEPLOYMENT_NAME = os.environ.get("AZURE_DEPLOYMENT_NAME", "gpt-4o")
    AZURE_OPENAI_API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")

    # JWT Authentication
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", os.environ.get("FLASK_SECRET_KEY", "change-me"))
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=int(os.environ.get("JWT_ACCESS_MIN", "30")))
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=int(os.environ.get("JWT_REFRESH_DAYS", "7")))

    # Rate limiting
    RATELIMIT_STORAGE_URL = os.environ.get("RATELIMIT_STORAGE_URL", "redis://localhost:6379/2")
    OCR_RATE_LIMIT = os.environ.get("OCR_RATE_LIMIT", "10/minute")
    INVOICE_RATE_LIMIT = os.environ.get("INVOICE_RATE_LIMIT", "5/minute")

    # Redis/Celery
    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", REDIS_URL)
    CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", REDIS_URL)

    # CORS
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")

    # API Configuration
    API_PREFIX = "/api/v1"
    SWAGGER_URL = "/apidocs"
    API_URL = "/api/v1/swagger.json"

    # Pagination
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100


class DevelopmentConfig(BaseConfig):
    """Development configuration."""
    DEBUG = True
    ENV = "development"
    CORS_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001"
    RATELIMIT_STORAGE_URL = "memory://"


class ProductionConfig(BaseConfig):
    """Production configuration."""
    DEBUG = False
    ENV = "production"
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "https://yourdomain.com")


class TestingConfig(BaseConfig):
    """Testing configuration."""
    TESTING = True
    DEBUG = True
    ENV = "testing"
    CORS_ORIGINS = "*"
    RATELIMIT_STORAGE_URL = "memory://"


# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config():
    """Get configuration based on environment."""
    env = os.environ.get('FLASK_ENV', 'development')
    return config.get(env, config['default'])


def ensure_directories(config_class) -> None:
    """Ensure required directories exist."""
    os.makedirs(config_class.UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(config_class.OUTPUT_FOLDER, exist_ok=True)




