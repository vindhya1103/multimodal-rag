"""
auth.py — Simple JSON-based authentication with bcrypt hashing.
No database needed. Works on any machine.
"""
import json
import os
import bcrypt
from datetime import datetime

USERS_FILE = "users.json"

# Default credentials (useful for quick testing)
DEFAULT_USER = "demo"
DEFAULT_PASS = "demo123"


def _load() -> dict:
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r") as f:
        return json.load(f)


def _save(users: dict):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)


def _ensure_default_user() -> None:
    """Ensure a default user exists so the app is immediately usable."""
    users = _load()
    if DEFAULT_USER not in users:
        hashed = bcrypt.hashpw(DEFAULT_PASS.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        users[DEFAULT_USER] = {
            "password": hashed,
            "created_at": datetime.now().isoformat(),
        }
        _save(users)


# Ensure we always have at least one user for quick local testing
_ensure_default_user()


def register_user(username: str, password: str) -> dict:
    username = username.strip()
    password = password.strip()

    if len(username) < 3:
        return {"success": False, "message": "Username must be at least 3 characters."}
    if len(password) < 6:
        return {"success": False, "message": "Password must be at least 6 characters."}

    users = _load()
    if username in users:
        return {"success": False, "message": "Username already exists."}

    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    users[username] = {
        "password": hashed,
        "created_at": datetime.now().isoformat(),
    }
    _save(users)
    return {"success": True, "message": "Account created successfully."}


def login_user(username: str, password: str) -> dict:
    username = username.strip()
    password = password.strip()

    if not username or not password:
        return {"success": False, "message": "Username and password cannot be empty."}

    users = _load()
    if username not in users:
        return {"success": False, "message": "Invalid username or password."}
    stored = users[username]["password"].encode("utf-8")
    if bcrypt.checkpw(password.encode("utf-8"), stored):
        return {"success": True, "message": "Login successful."}
    return {"success": False, "message": "Invalid username or password."}