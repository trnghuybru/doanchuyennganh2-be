import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "mysql+pymysql://root@localhost:3306/dacn2")
    SQLALCHEMY_TRACK_MODIFICATIONS = False  # Fix typo in MODIFICATIONS
    SECRET_KEY = os.getenv("SECRET_KEY", "secret_key")
    SQLALCHEMY_ENGINE_OPTIONS = {
        "connect_args": {
            "charset": "utf8mb4"
        },
        "pool_size": 10,
        "max_overflow": 2,
        "pool_timeout": 30,
        "pool_recycle": 1800
    }
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "jwt-secret-key")

    LAMBDA_IMG_ENDPOINT = os.getenv("LAMBDA_IMG_ENDPOINT")
    