import os

class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "mysql+pymysql://root@localhost:3306/dacn2")
    SQLALCHEMY_TRACK_MODFICATIONS = False
    SECRET_KEY = os.getenv("SECRET_KEY", "secret_key")
    SQLALCHEMY_ENGINE_OPTIONS = {"connect_args": {"charset": "utf8mb4"}}
    JWT_SECRET_KEY = "jwt-secret-key"

    LAMBDA_IMG_ENDPOINT = os.getenv("LAMBDA_IMG_ENDPOINT")
