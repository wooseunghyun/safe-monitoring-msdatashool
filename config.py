import os
from dotenv import load_dotenv
load_dotenv()

class Settings:
    KAKAO_MAP_API_KEY = os.getenv("KAKAO_MAP_API_KEY")
    OSRM_URL = os.getenv("OSRM_URL", "http://router.project-osrm.org")
    # Blob
    AZURE_STORAGE_ACCOUNT_NAME = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
    AZURE_STORAGE_ACCOUNT_KEY  = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")
    VOICE_CONTAINER = os.getenv("VOICE_CONTAINER", "voice-uploads")
    # Event Hub
    EH_CONN_STRING = os.getenv("EH_CONN_STRING")
    EH_HUB_NAME    = os.getenv("EH_HUB_NAME")
    # Auth
    JWT_SECRET = os.getenv("JWT_SECRET")
    ALLOW_ANON_UPLOAD = os.getenv("ALLOW_ANON_UPLOAD", "true").lower() == "true"
    # DB
    SQLITE_PATH = os.getenv("SQLITE_PATH", "uploads.db")
