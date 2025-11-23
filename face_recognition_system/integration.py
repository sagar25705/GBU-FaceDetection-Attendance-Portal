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

# Import your existing auth system
from fastapi_auth.app.database import get_db
from fastapi_auth.app import auth, models

# Import ultra-simple face recognition
from .pipeline import UltraSimpleFaceRecognition

# Security
security = HTTPBearer()

# Global face recognition system
face_recognition_system = None

def get_face_recognition_system():
    """Get or create ultra-simple face recognition system"""
    global face_recognition_system
    
    if face_recognition_system is None:
        try:
            # Get Pinecone credentials if available
            pinecone_api_key = os.getenv("PINECONE_API_KEY")
            pinecone_environment = os.getenv("PINECONE_ENVIRONMENT")
            
            face_recognition_system = UltraSimpleFaceRecognition(
                pinecone_api_key=pinecone_api_key,
                pinecone_environment=pinecone_environment,
                index_name="face-recognition"
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Face recognition system initialization failed: {str(e)}"
            )
    
    return face_recognition_system

# Create router
router = APIRouter(prefix="/face-recognition", tags=["Face Recognition"])

@router.post("/enroll-student")
async def enroll_student_faces(
    roll_no: str = Form(...),
    files: List[UploadFile] = File(...),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    Enroll student with ultra-simple face recognition
    """
    # Verify authentication
    token = credentials.credentials
    current_user = await auth.get_current_user_simple(token, db)
    
    # Check permissions
    if current_user.role not in [1, 2, 3]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    # Validate input
    if len(files) < 1 or len(files) > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please upload between 1-10 images"
        )
    
    # Check if student exists
    student = db.query(models.StudentProfile).filter(
        models.StudentProfile.roll_no == roll_no
    ).first()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student with roll number {roll_no} not found"
        )
    
    try:
        # Create temporary folder
        temp_dir = Path(f"temp_uploads/{roll_no}_{uuid.uuid4().hex[:8]}")
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Save uploaded files
        for i, file in enumerate(files):
            # Save file with simple name
            file_extension = ".jpg"  # Default extension
            if "." in file.filename:
                file_extension = "." + file.filename.split(".")[-1]
            
            temp_filename = f"image_{i+1}{file_extension}"
            temp_file_path = temp_dir / temp_filename
            
            with open(temp_file_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)
        
        # Get face recognition system
        face_system = get_face_recognition_system()
        
        # Enroll student
        success = face_system.enroll_student(
            roll_no=roll_no,
            student_name=student.name,
            image_folder_path=str(temp_dir)
        )
        
        # Clean up temporary files
        shutil.rmtree(temp_dir, ignore_errors=True)
        
        if success:
            # Log activity
            activity = models.SchoolActivity(
                activity_name=models.ActivityType.add_student,
                user_id=current_user.user_id,
                roll_no=roll_no
            )
            db.add(activity)
            db.commit()
            
            return {
                "success": True,
                "message": f"Student {student.name} ({roll_no}) enrolled successfully",
                "images_processed": len(files),
                "roll_no": roll_no,
                "student_name": student.name,
                "method": "ultra_simple"
            }
        else:
            return {
                "success": False,
                "message": f"Failed to enroll student {roll_no}",
                "roll_no": roll_no
            }
    
    except Exception as e:
        # Clean up on error
        if 'temp_dir' in locals() and temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error during enrollment: {str(e)}"
        )

@router.post("/recognize")
async def recognize_student(
    image: UploadFile = File(...),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    Recognize student using ultra-simple method
    """
    # Verify authentication
    token = credentials.credentials
    current_user = await auth.get_current_user_simple(token, db)
    
    if current_user.role not in [1, 2, 3]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authentication required"
        )
    
    try:
        # Save uploaded image temporarily
        temp_filename = f"recognition_{uuid.uuid4().hex}.jpg"
        temp_path = Path(f"temp_uploads/{temp_filename}")
        temp_path.parent.mkdir(exist_ok=True)
        
        with open(temp_path, "wb") as buffer:
            content = await image.read()
            buffer.write(content)
        
        # Get face recognition system
        face_system = get_face_recognition_system()
        
        # Recognize student
        recognition_results = face_system.recognize_student(str(temp_path), top_k=3)
        
        # Clean up
        temp_path.unlink(missing_ok=True)
        
        # Enhance results with database info
        enhanced_results = []
        for result in recognition_results:
            if result['is_match']:
                student = db.query(models.StudentProfile).filter(
                    models.StudentProfile.roll_no == result['roll_no']
                ).first()
                
                if student:
                    enhanced_result = result.copy()
                    enhanced_result.update({
                        "semester": student.semester,
                        "year": student.year,
                        "email": student.email,
                        "department_id": student.department_id,
                        "school_id": student.school_id
                    })
                    enhanced_results.append(enhanced_result)
                else:
                    enhanced_results.append(result)
            else:
                enhanced_results.append(result)
        
        # Determine status
        if enhanced_results and enhanced_results[0]['is_match']:
            status_msg = "STUDENT_RECOGNIZED"
            best_match = enhanced_results[0]
        else:
            status_msg = "NO_MATCH_FOUND"
            best_match = None
        
        return {
            "recognition_status": status_msg,
            "best_match": best_match,
            "all_matches": enhanced_results,
            "total_candidates": len(enhanced_results),
            "processed_by": current_user.email,
            "method": "ultra_simple",
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        if 'temp_path' in locals() and temp_path.exists():
            temp_path.unlink(missing_ok=True)
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error during recognition: {str(e)}"
        )

@router.get("/student-status/{roll_no}")
async def check_student_status(
    roll_no: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Check student enrollment status"""
    token = credentials.credentials
    current_user = await auth.get_current_user_simple(token, db)
    
    student = db.query(models.StudentProfile).filter(
        models.StudentProfile.roll_no == roll_no
    ).first()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student not found: {roll_no}"
        )
    
    try:
        face_system = get_face_recognition_system()
        stats = face_system.get_system_stats()
        
        return {
            "roll_no": roll_no,
            "student_name": student.name,
            "enrolled_in_database": True,
            "system_operational": stats.get('status') == 'operational',
            "storage_method": stats.get('storage_method', 'unknown'),
            "method": "ultra_simple"
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error checking status: {str(e)}"
        )

@router.get("/stats")
async def get_stats(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Get system statistics"""
    token = credentials.credentials
    current_user = await auth.get_current_user_simple(token, db)
    
    if current_user.role not in [1, 2]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or school access required"
        )
    
    try:
        face_system = get_face_recognition_system()
        face_stats = face_system.get_system_stats()
        
        total_students = db.query(models.StudentProfile).count()
        
        return {
            "face_recognition_stats": face_stats,
            "database_stats": {"total_students": total_students},
            "system_health": {
                "status": "operational",
                "method": "ultra_simple",
                "dependencies": "minimal"
            }
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting stats: {str(e)}"
        )

# Export router
def get_face_recognition_router():
    return router