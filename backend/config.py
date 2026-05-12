import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    SECRET_KEY = os.environ.get('SECRET_KEY', 'annotator-tool-secret-key-2024')
    MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/')
    DB_NAME = os.environ.get('DB_NAME', 'annotator_tool')
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB
    ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv', 'webm'}
    JWT_EXPIRATION_HOURS = 24
    DAM_SERVER_URL = os.environ.get('DAM_SERVER_URL', 'http://localhost:8000')
    EMBEDDING_DIM = int(os.environ.get('EMBEDDING_DIM', '1536'))
    VECTOR_DATA_DIR = os.environ.get('VECTOR_DATA_DIR', os.path.join(BASE_DIR, 'data'))
    FAISS_INDEX_PATH = os.environ.get('FAISS_INDEX_PATH', os.path.join(VECTOR_DATA_DIR, 'faiss.index'))
    FAISS_MAP_PATH = os.environ.get('FAISS_MAP_PATH', os.path.join(VECTOR_DATA_DIR, 'faiss_id_map.pkl'))
    CORS_ORIGINS = [
        origin.strip()
        for origin in os.environ.get(
            'CORS_ORIGINS',
            'https://annotator.stecom.vn,http://localhost:4200,http://127.0.0.1:4200,https://video-labeling.vercel.app',
        ).split(',')
        if origin.strip()
    ]
