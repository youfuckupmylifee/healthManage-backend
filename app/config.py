import os

class Config:
    SQLALCHEMY_DATABASE_URI = 'sqlite:///healthManager.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.urandom(24)
    JWT_SECRET_KEY = os.urandom(24)