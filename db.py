# db.py
import os
from dotenv import load_dotenv
from pymongo import MongoClient
from passlib.context import CryptContext

load_dotenv()

MONGO_URI = os.getenv("DATABASE_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "campus_admin")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_student_collection():
    return db["students"]


def get_admin_collection():
    return db["admins"]


# Password helpers
def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)
