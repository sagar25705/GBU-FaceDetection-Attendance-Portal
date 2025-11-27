"""
FastAPI Integration for Ultra-Simple Face Recognition
Works with minimal dependencies
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import List, Dict
import shutil
from pathlib import Path
import uuid
import os
from datetime import datetime

# Import existing backend components
from fastapi_auth.app.database import get_db
from fastapi_auth.app import auth, models

# Ultra Simple Face Recognition
from .pipeline import UltraSimpleFaceRecognition

# Security
security = HTTPBearer()

# ===============================
# FACE RECO SYSTEM INITIALIZATION
# ===============================

face_recognition_system = None

def get_face_recognition_system():
    """Initialize or return the active face-recognition engine"""
    global face_recognition_system

    if face_recognition_system is None:
        try:
            pinecone_api_key = os.getenv("PINECONE_API_KEY")
            pinecone_environment = os.getenv("PINECONE_ENVIRONMENT")

            face_recognition_system = UltraSimpleFaceRecognition(
                pinecone_api_key=pinecone_api_key,
                pinecone_environment=pinecone_environment,
                index_name="face-recognition"
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Face recognition initialization failed: {str(e)}"
            )

    return face_recognition_system

# Router
router = APIRouter(prefix="/face-recognition", tags=["Face Recognition"])

# =====================================
#          1. ENROLL STUDENT FACES
# =====================================

@router.post("/enroll-student")
async def enroll_student_faces(
    roll_no: str = Form(...),
    files: List[UploadFile] = File(...),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    token = credentials.credentials
    current_user = await auth.get_current_user_simple(token, db)

    if current_user.role not in [1, 2, 3]:
        raise HTTPException(403, "Insufficient permissions")

    if len(files) < 1 or len(files) > 10:
        raise HTTPException(400, "Upload between 1-10 images")

    student = db.query(models.StudentProfile).filter(
        models.StudentProfile.roll_no == roll_no
    ).first()

    if not student:
        raise HTTPException(404, f"Student {roll_no} not found")

    try:
        temp_dir = Path(f"temp_uploads/{roll_no}_{uuid.uuid4().hex[:8]}")
        temp_dir.mkdir(parents=True, exist_ok=True)

        # save images
        for i, file in enumerate(files):
            ext = file.filename.split(".")[-1]
            temp_path = temp_dir / f"image_{i+1}.{ext}"

            with open(temp_path, "wb") as buffer:
                buffer.write(await file.read())

        face_system = get_face_recognition_system()

        success = face_system.enroll_student(
            roll_no=roll_no,
            student_name=student.name,
            image_folder_path=str(temp_dir)
        )

        shutil.rmtree(temp_dir, ignore_errors=True)

        if not success:
            raise HTTPException(500, f"Face enrollment failed for {roll_no}")

        # log activity
        activity = models.SchoolActivity(
            activity_name=models.ActivityType.add_student,
            user_id=current_user.user_id,
            roll_no=roll_no
        )
        db.add(activity)
        db.commit()

        return {
            "success": True,
            "message": f"Enrolled {student.name} ({roll_no})",
            "images_processed": len(files),
            "method": "ultra_simple"
        }

    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(500, f"Enrollment error: {str(e)}")

# =====================================
#   2. **UPLOAD MULTIPLE STUDENT IMAGES**
#       (Recommended over enroll endpoint)
# =====================================

@router.post("/upload-student-images")
async def upload_student_photos(
    roll_no: str = Form(...),
    images: List[UploadFile] = File(...),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    token = credentials.credentials
    current_user = await auth.get_current_user_simple(token, db)

    if current_user.role not in [1, 2, 3]:
        raise HTTPException(403, "Not authorized")

    student = db.query(models.StudentProfile).filter(
        models.StudentProfile.roll_no == roll_no
    ).first()

    if not student:
        raise HTTPException(404, "Student not found")

    if len(images) < 3:
        raise HTTPException(400, "At least 3 images required")

    temp_dir = Path(f"temp_uploads/{roll_no}_{uuid.uuid4().hex[:6]}")
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        saved = []
        for i, img in enumerate(images):
            ext = img.filename.split(".")[-1]
            save_path = temp_dir / f"{roll_no}_{i}.{ext}"
            with open(save_path, "wb") as f:
                shutil.copyfileobj(img.file, f)
            saved.append(str(save_path))

        face_system = get_face_recognition_system()

        success = face_system.enroll_student(
            roll_no=roll_no,
            student_name=student.name,
            image_folder_path=str(temp_dir)
        )

        shutil.rmtree(temp_dir, ignore_errors=True)

        if not success:
            raise HTTPException(500, "Face enrollment failed")

        return {
            "success": True,
            "message": f"{len(saved)} images processed",
            "roll_no": roll_no,
            "student_name": student.name
        }

    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(500, f"Upload failed: {str(e)}")

# =====================================
#           3. RECOGNITION
# =====================================

@router.post("/recognize")
async def recognize_student(
    image: UploadFile = File(...),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    token = credentials.credentials
    current_user = await auth.get_current_user_simple(token, db)

    if current_user.role not in [1, 2, 3]:
        raise HTTPException(403, "Authentication required")

    try:
        temp_path = Path(f"temp_uploads/{uuid.uuid4().hex}.jpg")
        temp_path.parent.mkdir(exist_ok=True)

        with open(temp_path, "wb") as f:
            f.write(await image.read())

        face_system = get_face_recognition_system()

        results = face_system.recognize_student(str(temp_path))
        temp_path.unlink(missing_ok=True)

        enhanced = []
        for r in results:
            if r["is_match"]:
                student = db.query(models.StudentProfile).filter(
                    models.StudentProfile.roll_no == r["roll_no"]
                ).first()

                if student:
                    r.update({
                        "email": student.email,
                        "semester": student.semester,
                        "year": student.year,
                        "department_id": student.department_id
                    })
            enhanced.append(r)

        return {
            "status": "recognized" if enhanced and enhanced[0]["is_match"] else "no_match",
            "best_match": enhanced[0] if enhanced else None,
            "all_matches": enhanced,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(500, f"Recognition error: {str(e)}")

# =====================================
#           4. STUDENT STATUS
# =====================================

@router.get("/student-status/{roll_no}")
async def student_status(
    roll_no: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    student = db.query(models.StudentProfile).filter(
        models.StudentProfile.roll_no == roll_no
    ).first()

    if not student:
        raise HTTPException(404, f"{roll_no} not found")

    system = get_face_recognition_system()
    stats = system.get_system_stats()

    return {
        "roll_no": roll_no,
        "name": student.name,
        "system": stats
    }

# =====================================
#               5. STATS
# =====================================

@router.get("/stats")
async def stats(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    token = credentials.credentials
    current_user = await auth.get_current_user_simple(token, db)

    if current_user.role not in [1, 2]:
        raise HTTPException(403, "Admin or school only")

    system = get_face_recognition_system()
    face_stats = system.get_system_stats()
    total_students = db.query(models.StudentProfile).count()

    return {
        "face_recognition": face_stats,
        "database_total_students": total_students
    }

# Export
def get_face_recognition_router():
    return router
