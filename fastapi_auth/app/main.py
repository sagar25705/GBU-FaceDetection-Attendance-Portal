
# from fastapi import FastAPI, Depends, HTTPException, status
# from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
# from fastapi.middleware.cors import CORSMiddleware  # ✅ NEW IMPORT
# from sqlalchemy.orm import Session
# from typing import Optional
# import uuid
# from datetime import timedelta
# import os
# from contextlib import asynccontextmanager

# # Local imports
# from . import models, schemas, utils, auth
# from .database import Base, get_db
# from .config import ACCESS_TOKEN_EXPIRE_MINUTES

# # Import create_engine
# from sqlalchemy import create_engine, func

# # Get DATABASE_URL from environment variable
# DATABASE_URL = os.getenv("DATABASE_URL")

# if not DATABASE_URL:
#     raise ValueError("DATABASE_URL environment variable not set")

# # Create engine with connection pooling
# engine = create_engine(
#     DATABASE_URL,
#     pool_size=10,
#     max_overflow=20,
#     pool_timeout=60,
#     pool_recycle=3600,
#     pool_pre_ping=True
# )

# # FIXED - Try multiple import paths:
# try:
#     import sys
#     import os
    
#     # Add the project root to Python path
#     project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#     if project_root not in sys.path:
#         sys.path.append(project_root)
    
#     from face_recognition_system.integration import get_face_recognition_router
#     FACE_RECOGNITION_AVAILABLE = True
#     print("✅ Face Recognition import successful!")
# except ImportError as e:
#     FACE_RECOGNITION_AVAILABLE = False
#     print(f"❌ Face Recognition import failed: {str(e)}")

# security = HTTPBearer()

# # Lifespan context manager - replaces deprecated @app.on_event("startup")
# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     """
#     Lifespan context manager for startup and shutdown events.
#     Code before yield runs on startup, code after yield runs on shutdown.
#     """
#     # STARTUP: Create all database tables
#     Base.metadata.create_all(bind=engine)
#     print("✅ Database initialized successfully!")
    
#     if FACE_RECOGNITION_AVAILABLE:
#         print("✅ Face Recognition system available!")
#     else:
#         print("⚠️  Face Recognition system not available!")
    
#     # Add face recognition routes if available
#     if FACE_RECOGNITION_AVAILABLE:
#         try:
#             face_router = get_face_recognition_router()
#             app.include_router(face_router)
#             print("✅ Face Recognition routes added!")
#         except Exception as e:
#             print(f"❌ Failed to add face recognition routes: {str(e)}")
    
#     yield  # Application runs here
    
#     # SHUTDOWN: Add cleanup code here if needed
#     print("🔴 Application shutting down...")


# main.py (patch - top of file)
import os
import sys
import random
import traceback
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError  # <- missing before
from sqlalchemy.orm import Session

# Local imports (ensure package init makes these importable)
from . import models, schemas, utils, auth
from .database import Base, get_db, engine  # <- import engine from database.py (see next section)
from .config import ACCESS_TOKEN_EXPIRE_MINUTES

# Face recognition import attempt (unchanged)
try:
    # Add project root if needed (you already had something similar)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.append(project_root)

    from face_recognition_system.integration import get_face_recognition_router
    FACE_RECOGNITION_AVAILABLE = True
    print("✅ Face Recognition import successful!")
except Exception as e:
    FACE_RECOGNITION_AVAILABLE = False
    print(f"❌ Face Recognition import failed: {str(e)}")

security = HTTPBearer()

# Lifespan: create tables using the engine we import from database.py
@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    print("✅ Database initialized successfully!")
    if FACE_RECOGNITION_AVAILABLE:
        print("✅ Face Recognition system available!")
    else:
        print("⚠️ Face Recognition system not available!")

    if FACE_RECOGNITION_AVAILABLE:
        try:
            face_router = get_face_recognition_router()
            app.include_router(face_router)
            print("✅ Face Recognition routes added!")
        except Exception as e:
            print(f"❌ Failed to add face recognition routes: {str(e)}")

    yield
    print("🔴 Application shutting down...")


# Initialize FastAPI app with lifespan
app = FastAPI(
    title="School Management System with Face Recognition",
    version="2.1.0",
    description="School management system with integrated face recognition for student attendance",
    lifespan=lifespan
)

# ✅ NEW: CORS Configuration
# Frontend URLs ko yaha define karo
origins = [
     "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://gbu-facelearn.vercel.app"
]

# CORS Middleware add karo
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,                # Allowed origins
    allow_credentials=True,               # Allow cookies/auth headers
    allow_methods=["*"],                  # Allow all HTTP methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],                  # Allow all headers
)

print("✅ CORS configured successfully!")
# ✅ END OF CORS CONFIGURATION

@app.get("/", summary="API root")
def root():
    endpoints = {
        "add_teacher": "POST /add-teacher (Bearer token required)",
        "add_student": "POST /add-student (Bearer token required)"
    }
    
    if FACE_RECOGNITION_AVAILABLE:
        endpoints.update({
            "face_recognition": {
                "enroll_student": "POST /face-recognition/enroll-student",
                "recognize": "POST /face-recognition/recognize", 
                "student_status": "GET /face-recognition/student-status/{roll_no}",
                "remove_student": "DELETE /face-recognition/student/{roll_no}",
                "stats": "GET /face-recognition/stats"
            }
        })
    
    return {
        "message": "🚀 School Management System with Face Recognition is running!",
        "endpoints": endpoints,
        "face_recognition_available": FACE_RECOGNITION_AVAILABLE,
        "cors_enabled": True  # ✅ NEW: Indicate CORS is enabled
    }

@app.post(
    "/add-teacher",
    response_model=schemas.TeacherResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a new teacher with user account"
)
async def add_teacher(
    teacher_data: schemas.TeacherCreate,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    token = credentials.credentials
    current_user = await auth.get_current_user_simple(token, db)

    if current_user.role not in [1, 2]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admin or school users can add teachers")

    # Double-check email not already in users table (auth.get_user_by_email should handle it)
    if auth.get_user_by_email(db, teacher_data.email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    # verify school exists
    school = db.query(models.School).filter(models.School.school_id == teacher_data.school_id).first()
    if not school:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"School with ID {teacher_data.school_id} not found")

    try:
        hashed_password = utils.get_password_hash(teacher_data.password)
        new_user = models.User(
            email=teacher_data.email,
            password_hash=hashed_password,
            role=2,
            name=teacher_data.name,
            phone_number=teacher_data.phone_number
        )
        db.add(new_user)
        db.flush()  # assign PK (UUID) without commit

        new_teacher = models.TeacherProfile(
            user_id=new_user.user_id,
            school_id=teacher_data.school_id,
            teacher_name=teacher_data.name,
            teacher_email=teacher_data.email,
            department=teacher_data.department,
            subject_specialisation=teacher_data.subject_specialisation
        )
        db.add(new_teacher)

        activity = models.SchoolActivity(
            activity_name=models.ActivityType.add_teacher,
            user_id=current_user.user_id
        )
        db.add(activity)

        db.commit()
        db.refresh(new_teacher)
        return {
            "teacher_id": new_teacher.teacher_id,
            "user_id": new_user.user_id,
            "name": new_teacher.teacher_name,
            "email": new_teacher.teacher_email,
            "school_id": new_teacher.school_id,
            "phone_number": new_user.phone_number,
            "department": new_teacher.department,
            "subject_specialisation": new_teacher.subject_specialisation,
            "message": "Teacher added successfully"
        }

    except IntegrityError as ie:
        db.rollback()
        # Unique constraint or FK error -> helpful message
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Database integrity error: {str(ie.orig)}")
    except Exception as e:
        db.rollback()
        print("❌ add_teacher exception:", e)
        traceback.print_exc()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error adding teacher: {str(e)}")

@app.get("/teachers")
def get_teachers(db: Session = Depends(get_db)):
    teachers = db.query(models.TeacherProfile).all()
    result = []
    for t in teachers:
        result.append({
            "teacher_id": t.teacher_id,
            "user_id": t.user_id,
            "name": t.teacher_name,
            "email": t.teacher_email,
            "phone_number": t.user.phone_number,
            "school_id": t.school_id,
            "department": t.department,
            "subject_specialisation": t.subject_specialisation,
        })
    return result

@app.put("/teachers/{teacher_id}")
def update_teacher(teacher_id: int, data: schemas.TeacherUpdate, db: Session = Depends(get_db)):

    teacher = db.query(models.TeacherProfile).filter(models.TeacherProfile.teacher_id == teacher_id).first()
    if not teacher:
        raise HTTPException(404, "Teacher not found")

    user = teacher.user

    # update email in both user & teacher_profile
    if data.email:
        user.email = data.email
        teacher.teacher_email = data.email

    if data.name:
        teacher.teacher_name = data.name
        user.name = data.name

    if data.phone_number:
        user.phone_number = data.phone_number

    if data.department is not None:
        teacher.department = data.department

    if data.subject_specialisation is not None:
        teacher.subject_specialisation = data.subject_specialisation

    if data.school_id:
        teacher.school_id = data.school_id

    db.commit()
    db.refresh(teacher)

    return {"message": "Teacher updated", "teacher": teacher}



@app.delete("/teachers/{teacher_id}")
def delete_teacher(teacher_id: int, db: Session = Depends(get_db)):
    teacher = db.query(models.TeacherProfile).filter(models.TeacherProfile.teacher_id == teacher_id).first()
    if not teacher:
        raise HTTPException(404, "Teacher not found")

    db.delete(teacher)
    db.commit()
    return {"message": "Teacher deleted"}


@app.get("/teacher/attendance/{unique_code}")
def get_live_attendance(unique_code: str, db: Session = Depends(get_db)):
    reg = db.query(models.AttendanceRegister).filter_by(unique_code=unique_code).first()
    if not reg:
        raise HTTPException(status_code=404, detail="Class code not found")

    # fetch attendance logs joined with student info if available
    logs = (
        db.query(models.AttendanceLog, models.StudentProfile)
          .join(models.StudentProfile, models.AttendanceLog.roll_no == models.StudentProfile.roll_no, isouter=True)
          .filter(models.AttendanceLog.unique_code == unique_code)
          .order_by(models.AttendanceLog.created_at.asc())
          .all()
    )

    result = []
    for log, student in logs:
        result.append({
            "attendance_id": log.attendance_id,
            "roll_no": log.roll_no,
            "student_name": student.name if student else None,
            "is_manual": log.is_manual,
            "created_at": log.created_at.isoformat()
        })

    return {
        "class_code": unique_code,
        "course_code": reg.course_code,
        "teacher_id": reg.teacher_id,
        "logs": result
    }

@app.post("/attendance/generate")
async def generate_attendance(
    data: schemas.AttendanceGenerate,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):

    user = await auth.get_current_user_simple(credentials.credentials, db)

    if user.role != 2:
        raise HTTPException(403, "Only teachers can generate class code")

    import random
    unique_code = str(random.randint(100000, 999999))

    teacher_profile = (
        db.query(models.TeacherProfile)
        .filter_by(user_id=user.user_id)
        .first()
    )
    if not teacher_profile:
        raise HTTPException(400, "Teacher profile not found")

    register = models.AttendanceRegister(
        unique_code=unique_code,
        user_id=user.user_id,
        course_code=data.course_code,
        class_id=data.class_id,
        teacher_id=teacher_profile.teacher_id
    )

    db.add(register)
    db.commit()
    db.refresh(register)

    return {
        "unique_code": unique_code,
        "expires_in": 300
    }


@app.get("/attendance/validate/{code}")
def validate_code(code: str, db: Session = Depends(get_db)):
    reg = db.query(models.AttendanceRegister).filter_by(unique_code=code).first()
    if not reg:
        raise HTTPException(404, "Invalid class code")

    return {
        "valid": True,
        "subject": reg.subject.subject_name,
        "subject_code": reg.course_code,
        "teacher": reg.teacher.teacher_name
    }


@app.post("/attendance/mark")
def mark_attendance(data: schemas.MarkAttendance, db: Session = Depends(get_db)):

    reg = db.query(models.AttendanceRegister).filter_by(unique_code=data.unique_code).first()
    if not reg:
        raise HTTPException(404, "Invalid class code")

    # Prevent duplicate marking
    existing = db.query(models.AttendanceLog).filter_by(
        unique_code=data.unique_code,
        roll_no=data.roll_no
    ).first()

    if existing:
        raise HTTPException(400, "Attendance already marked")

    entry = models.AttendanceLog(
        unique_code=data.unique_code,
        roll_no=data.roll_no,
        is_manual=data.is_manual
    )

    db.add(entry)
    db.commit()
    db.refresh(entry)

    return {"message": "Attendance marked"}



@app.post(
    "/register",
    response_model=schemas.UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user"
)
def register(user_data: schemas.UserCreate, db: Session = Depends(get_db)):
    """Register a new user with email and password only."""
    
    # Check if email already exists
    if auth.get_user_by_email(db, user_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Email already registered"
        )

    # Hash password and create user
    hashed_password = utils.get_password_hash(user_data.password)
    new_user = models.User(
        email=user_data.email,
        password_hash=hashed_password,
        role=2,  # Default role: teacher
        name=user_data.email.split('@')[0]  # Use email prefix as name
    )

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Database error: {str(e)}"
        )

    return new_user

# Simple JSON login - no OAuth2 form complexity
@app.post("/login", response_model=schemas.Token, summary="Login with email and password")
def login(user_credentials: schemas.LoginRequest, db: Session = Depends(get_db)):

    user = auth.authenticate_user(db, user_credentials.email, user_credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = utils.create_access_token(
        data={"sub": user.email},
        expires_delta=access_token_expires
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": str(user.user_id),
        "email": user.email,
        "name": user.name,
        "role": user.role,
    }


@app.get(
    "/users/me",
    response_model=schemas.UserResponse,
    summary="Get current user (Bearer token required)"
)
@app.get("/users/me", response_model=schemas.UserResponse)
async def read_users_me(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    token = credentials.credentials
    user = await auth.get_current_user_simple(token, db)

    roll_no = None
    if user.role == 3:  # student
        student = db.query(models.StudentProfile).filter(
            models.StudentProfile.user_id == user.user_id
        ).first()
        if student:
            roll_no = student.roll_no

    return {
        "user_id": user.user_id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "created_at": user.created_at,
        "roll_no": roll_no
    }




# ============================
# GET ALL STUDENTS
# ============================

@app.get("/admin/stats")
def dashboard_stats(db: Session = Depends(get_db)):

    total_schools = db.query(models.School).count()
    total_students = db.query(models.StudentProfile).count()
    total_teachers = db.query(models.TeacherProfile).count()

    school_distribution = (
        db.query(models.School.school_name, db.func.count(models.StudentProfile.roll_no))
        .join(models.StudentProfile, models.School.school_id == models.StudentProfile.school_id)
        .group_by(models.School.school_name)
        .all()
    )

    recent = db.query(models.SchoolActivity).order_by(models.SchoolActivity.timestamp.desc()).limit(6).all()

    return {
        "stats": {
            "totalSchools": total_schools,
            "totalStudents": total_students,
            "totalTeachers": total_teachers,
            "activeCourses": 42
        },
        "recentActivities": [
            {
                "action": a.activity_name.value,
                "by": str(a.user_id),
                "timeAgo": "just now"
            }
            for a in recent
        ],
        "schoolDistribution": [
            {
                "school": s[0],
                "students": s[1]
            } for s in school_distribution
        ]
    }


@app.get("/students")
def get_students(db: Session = Depends(get_db)):
    students = db.query(models.StudentProfile).all()

    result = []
    for s in students:
        result.append({
            "roll_no": s.roll_no,
            "name": s.name,
            "email": s.email,
            "phone_number": s.phone_number,
            "semester": s.semester,
            "year": s.year,

            "school": {
                "school_id": s.school.school_id if s.school else None,
                "school_name": s.school.school_name if s.school else "Unknown"
            },

            "department": {
                "department_id": s.department.department_id if s.department else None,
                "department_name": s.department.department_name if s.department else "Unknown"
            }
        })
    return result



# ============================
# UPDATE STUDENT
# ============================
@app.put("/students/{roll_no}")
def update_student(roll_no: str, data: schemas.StudentCreate, db: Session = Depends(get_db)):
    student = db.query(models.StudentProfile).filter(models.StudentProfile.roll_no == roll_no).first()
    if not student:
        raise HTTPException(404, "Student not found")

    student.name = data.name
    student.email = data.email
    student.phone_number = data.phone_number
    student.semester = data.semester
    student.year = data.year
    student.school_id = data.school_id
    student.department_id = data.department_id

    db.commit()
    db.refresh(student)
    return {"message": "Student updated", "student": student}


from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
import smtplib
from email.message import EmailMessage
import os

class CredentialEmailRequest(BaseModel):
    email: EmailStr
    roll_no: str
    password: str

@app.post("/send-student-credentials")
def send_student_credentials(data: CredentialEmailRequest):
    """
    Sends login credentials to the student's email.
    """
    try:
        SENDER_EMAIL = os.getenv("SMTP_EMAIL")
        SENDER_PASSWORD = os.getenv("SMTP_PASSWORD")

        if not SENDER_EMAIL or not SENDER_PASSWORD:
            raise HTTPException(500, "Email environment variables missing")

        msg = EmailMessage()
        msg["Subject"] = "Your Student Login Credentials"
        msg["From"] = SENDER_EMAIL
        msg["To"] = data.email

        msg.set_content(
            f"""
Hello Student,

Your account has been created.

Login Credentials:
-----------------------
Roll Number (Username): {data.email}
Temporary Password:     {data.password}

Please login and change the password immediately.

Regards,
University Admin
"""
        )

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(SENDER_EMAIL, SENDER_PASSWORD)
            smtp.send_message(msg)

        return {"success": True, "message": "Credentials sent to student email"}

    except Exception as e:
        raise HTTPException(500, f"Failed to send email: {str(e)}")


# ============================
# DELETE STUDENT
# ============================
@app.delete("/students/{roll_no}")
def delete_student(roll_no: str, db: Session = Depends(get_db)):
    student = db.query(models.StudentProfile).filter(models.StudentProfile.roll_no == roll_no).first()
    if not student:
        raise HTTPException(404, "Student not found")

    # Get the user mapped to this student
    user = db.query(models.User).filter(models.User.user_id == student.user_id).first()

    # Delete student profile first
    db.delete(student)

    # Delete user if exists
    if user:
        db.delete(user)

    db.commit()
    return {"message": "Student + User account deleted"}


@app.post(
    "/add-student",
    response_model=schemas.StudentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a new student"
)
async def add_student(
    student_data: schemas.StudentCreate,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    Add a new student + create login account.
    This does ALL of the following:

    1. Validate school, department, semester
    2. Ensure roll_no and email are unique
    3. Create USER account (users table)
    4. Generate temporary password & hash it
    5. Attach user_id to StudentProfile
    6. Save StudentProfile
    7. Log activity
    """

    # ==============================
    # 1. AUTH CHECK
    # ==============================
    token = credentials.credentials
    current_user = await auth.get_current_user_simple(token, db)

    if current_user.role not in [1, 2, 3]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid user role – only Admin, School, or Teacher can add students"
        )

    # ==============================
    # 2. UNIQUE VALIDATION
    # ==============================
    # Roll number check
    if db.query(models.StudentProfile).filter(
        models.StudentProfile.roll_no == student_data.roll_no
    ).first():
        raise HTTPException(
            400,
            f"Student with roll number {student_data.roll_no} already exists"
        )

    # Email must allow login → check in users table too
    if db.query(models.User).filter(
        models.User.email == student_data.email
    ).first():
        raise HTTPException(
            400,
            f"Email {student_data.email} is already registered"
        )

    # ==============================
    # 3. FOREIGN KEYS VALIDATION
    # ==============================
    if not db.query(models.School).filter(
        models.School.school_id == student_data.school_id
    ).first():
        raise HTTPException(404, f"School ID {student_data.school_id} not found")

    if not db.query(models.Department).filter(
        models.Department.department_id == student_data.department_id
    ).first():
        raise HTTPException(404, f"Department ID {student_data.department_id} not found")

    if not (1 <= student_data.semester <= 8):
        raise HTTPException(400, "Semester must be between 1 and 8")

    try:
        # ============================================
        # 4. CREATE USER ACCOUNT FOR STUDENT
        # ============================================

        # Generate temporary password
        temp_password = utils.generate_random_password()   # You MUST create this helper!
        hashed_password = utils.get_password_hash(temp_password)

        new_user = models.User(
            email=student_data.email,
            password_hash=hashed_password,
            role=3,  # ROLE 4 = STUDENT
            name=student_data.name,
            phone_number=student_data.phone_number
        )

        db.add(new_user)
        db.flush()  # get new_user.user_id

        # ============================================
        # 5. CREATE STUDENT PROFILE
        # ============================================
        new_student = models.StudentProfile(
            roll_no=student_data.roll_no,
            name=student_data.name,
            phone_number=student_data.phone_number,
            email=student_data.email,
            semester=student_data.semester,
            year=student_data.year,
            school_id=student_data.school_id,
            department_id=student_data.department_id,
            user_id=new_user.user_id  # LINK STUDENT → USER
        )
        db.add(new_student)

        # ============================================
        # 6. LOG ACTIVITY
        # ============================================
        activity = models.SchoolActivity(
            activity_name=models.ActivityType.add_student,
            user_id=current_user.user_id,
            roll_no=new_student.roll_no
        )
        db.add(activity)

        # Commit everything
        db.commit()

        db.refresh(new_student)

        # ============================================
        # 7. RESPONSE WITH TEMP PASSWORD
        # ============================================
        return {
            "roll_no": new_student.roll_no,
            "name": new_student.name,
            "email": new_student.email,
            "phone_number": new_student.phone_number,
            "semester": new_student.semester,
            "year": new_student.year,
            "school_id": new_student.school_id,
            "department_id": new_student.department_id,
            "temporary_password": temp_password,   # ← IMPORTANT
            "message": "Student added successfully",
            "next_steps": {
                "face_recognition": "Use /face-recognition/enroll-student to upload photos"
            }
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            500,
            f"Error adding student: {str(e)}"
        )

@app.get("/health", summary="Health check")
def health_check():
    health_status = {
        "status": "healthy", 
        "service": "School Management System",
        "face_recognition": FACE_RECOGNITION_AVAILABLE,
        "cors_enabled": True  # ✅ NEW
    }
    
    if FACE_RECOGNITION_AVAILABLE:
        health_status["face_recognition_status"] = "available"
    else:
        health_status["face_recognition_status"] = "not_available"
    
    return health_status

# Fallback route if face recognition is not available
if not FACE_RECOGNITION_AVAILABLE:
    @app.get("/face-recognition", summary="Face Recognition Status")
    def face_recognition_status():
        return {
            "available": False,
            "message": "Face Recognition not available. Install dependencies: pip install -r requirements_face_recognition.txt",
            "required_env_vars": [
                "PINECONE_API_KEY",
                "PINECONE_ENVIRONMENT"
            ]
        }


