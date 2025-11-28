from datetime import datetime, timedelta
from jose import jwt
import hashlib
import secrets
from .config import SECRET_KEY, ALGORITHM
from typing import Optional
import random
import string

def get_password_hash(password: str) -> str:
    """Simple SHA256 + salt password hashing"""
    salt = secrets.token_hex(16)
    password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}:{password_hash}"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        salt, stored_hash = hashed_password.split(':')
        password_hash = hashlib.sha256((plain_password + salt).encode()).hexdigest()
        return password_hash == stored_hash
    except:
        # << looks like you have a broken/truncated except block in your real file
        ...
    return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def generate_random_password():
    return secrets.token_urlsafe(8)

