from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager

# инициализация объектов
db = SQLAlchemy()
jwt = JWTManager()
