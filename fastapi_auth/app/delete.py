# delete.py

import os
import sys
from dotenv import load_dotenv

# Load .env from project root
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(ROOT_DIR, "..", ".env")
ENV_PATH = os.path.abspath(ENV_PATH)

print("Loading ENV from:", ENV_PATH)
load_dotenv(ENV_PATH)

print("DATABASE_URL =", os.getenv("DATABASE_URL"))

# Now imports will use the correct DB
from .database import SessionLocal
from .models import User, StudentProfile


TARGET_EMAIL = "dtuskillop@gmail.com"


def delete_user(email: str):
    db = SessionLocal()
    try:
        print(f"🔍 Searching for: {email}")

        user = db.query(User).filter(User.email == email).first()

        if not user:
            print("✔️ User not found")
            return

        student = db.query(StudentProfile).filter(
            StudentProfile.user_id == user.user_id
        ).first()

        if student:
            print(f"🗑 Deleting StudentProfile ({student.roll_no})")
            db.delete(student)

        print(f"🗑 Deleting User {email}")
        db.delete(user)
        db.commit()

        print("🎉 Successfully deleted user + student")

    except Exception as e:
        db.rollback()
        print("❌ Error:", e)

    finally:
        db.close()


if __name__ == "__main__":
    delete_user(TARGET_EMAIL)
