
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware  # ✅ NEW IMPORT
from sqlalchemy.orm import Session
from typing import Optional
import uuid
from datetime import timedelta
import os
from contextlib import asynccontextmanager

# Local imports
from . import models, schemas, utils, auth
from .database import Base, get_db
from .config import ACCESS_TOKEN_EXPIRE_MINUTES

# Import create_engine
from sqlalchemy import create_engine

# Get DATABASE_URL from environment variable
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set")

# Create engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_timeout=60,
    pool_recycle=3600,
    pool_pre_ping=True
)

# FIXED - Try multiple import paths:
try:
    import sys
    import os
    
    # Add the project root to Python path
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.append(project_root)
    
    from face_recognition_system.integration import get_face_recognition_router
    FACE_RECOGNITION_AVAILABLE = True
    print("✅ Face Recognition import successful!")
except ImportError as e:
    FACE_RECOGNITION_AVAILABLE = False
    print(f"❌ Face Recognition import failed: {str(e)}")

security = HTTPBearer()

# Lifespan context manager - replaces deprecated @app.on_event("startup")
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    Code before yield runs on startup, code after yield runs on shutdown.
    """
    # STARTUP: Create all database tables
    Base.metadata.create_all(bind=engine)
    print("✅ Database initialized successfully!")
    
    if FACE_RECOGNITION_AVAILABLE:
        print("✅ Face Recognition system available!")
    else:
        print("⚠️  Face Recognition system not available!")
    
    # Add face recognition routes if available
    if FACE_RECOGNITION_AVAILABLE:
        try:
            face_router = get_face_recognition_router()
            app.include_router(face_router)
            print("✅ Face Recognition routes added!")
        except Exception as e:
            print(f"❌ Failed to add face recognition routes: {str(e)}")
    
    yield  # Application runs here
    
    # SHUTDOWN: Add cleanup code here if needed
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
    "http://localhost:8080",              # Local development
    "http://localhost:3000",              # Alternate local port
    "http://localhost:5173",              # Vite default port
    "https://gbu-facelearn.vercel.app",   # Your Vercel deployment
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
    """
    Add a new teacher to the system.
    This endpoint:
    1. Creates a user account (email + password)
    2. Creates a teacher profile linked to the user
    3. Logs the activity
    
    Requires: Bearer token authentication (admin or school role)
    """
    # Verify current user
    token = credentials.credentials
    current_user = await auth.get_current_user_simple(token, db)
    
    # Check if user has permission (admin=1 or school=2)
    if current_user.role not in [1, 2]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin or school users can add teachers"
        )
    
    # Check if email already exists
    existing_user = auth.get_user_by_email(db, teacher_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Check if school exists
    school = db.query(models.School).filter(models.School.school_id == teacher_data.school_id).first()
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"School with ID {teacher_data.school_id} not found"
        )
    
    try:
        # 1. Create user account
        hashed_password = utils.get_password_hash(teacher_data.password)
        new_user = models.User(
            email=teacher_data.email,
            password_hash=hashed_password,
            role=3,  # Teacher role
            name=teacher_data.name,
            phone_number=teacher_data.phone_number
        )
        db.add(new_user)
        db.flush()  # Get user_id without committing
        
        # 2. Create teacher profile
        new_teacher = models.TeacherProfile(
            user_id=new_user.user_id,
            school_id=teacher_data.school_id,
            teacher_name=teacher_data.name,
            teacher_email=teacher_data.email
        )
        db.add(new_teacher)
        db.flush()  # Get teacher_id
        
        # 3. Log activity
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
            "message": "Teacher added successfully"
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error adding teacher: {str(e)}"
        )

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
        role=3,  # Default role: teacher
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
@app.post(
    "/login",
    response_model=schemas.Token,
    summary="Login with email and password (JSON)"
)
def login(user_credentials: schemas.UserCreate, db: Session = Depends(get_db)):
    """
    Simple login with JSON body containing email and password.
    """
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

    return {"access_token": access_token, "token_type": "bearer"}

@app.get(
    "/users/me",
    response_model=schemas.UserResponse,
    summary="Get current user (Bearer token required)"
)
async def read_users_me(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    """
    Get current user info using Bearer token.
    """
    token = credentials.credentials
    user = await auth.get_current_user_simple(token, db)
    return user

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
    Add a new student to the system.
    This endpoint:
    1. Creates a student profile
    2. Logs the activity
    
    Note: To enable face recognition for the student, use /face-recognition/enroll-student
    
    Requires: Bearer token authentication (admin, school, or teacher role)
    """
    # Verify current user
    token = credentials.credentials
    current_user = await auth.get_current_user_simple(token, db)
    
    # All authenticated users can add students
    if current_user.role not in [1, 2, 3]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid user role"
        )
    
    # Check if roll number already exists
    existing_student = db.query(models.StudentProfile).filter(
        models.StudentProfile.roll_no == student_data.roll_no
    ).first()
    if existing_student:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Student with roll number {student_data.roll_no} already exists"
        )
    
    # Check if email already exists (if provided)
    if student_data.email:
        existing_email = db.query(models.StudentProfile).filter(
            models.StudentProfile.email == student_data.email
        ).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Email {student_data.email} already registered"
            )
    
    # Verify school exists
    school = db.query(models.School).filter(models.School.school_id == student_data.school_id).first()
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"School with ID {student_data.school_id} not found"
        )
    
    # Verify department exists
    department = db.query(models.Department).filter(
        models.Department.department_id == student_data.department_id
    ).first()
    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with ID {student_data.department_id} not found"
        )
    
    # Validate semester
    if student_data.semester < 1 or student_data.semester > 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Semester must be between 1 and 8"
        )
    
    try:
        # 1. Create student profile
        new_student = models.StudentProfile(
            roll_no=student_data.roll_no,
            name=student_data.name,
            phone_number=student_data.phone_number,
            email=student_data.email,
            semester=student_data.semester,
            year=student_data.year,
            school_id=student_data.school_id,
            department_id=student_data.department_id
        )
        db.add(new_student)
        db.flush()
        
        # 2. Log activity
        activity = models.SchoolActivity(
            activity_name=models.ActivityType.add_student,
            user_id=current_user.user_id,
            roll_no=new_student.roll_no
        )
        db.add(activity)
        
        db.commit()
        db.refresh(new_student)
        
        response_data = {
            "roll_no": new_student.roll_no,
            "name": new_student.name,
            "email": new_student.email,
            "phone_number": new_student.phone_number,
            "semester": new_student.semester,
            "year": new_student.year,
            "school_id": new_student.school_id,
            "department_id": new_student.department_id,
            "message": "Student added successfully"
        }
        
        if FACE_RECOGNITION_AVAILABLE:
            response_data["next_steps"] = {
                "face_recognition": "Use /face-recognition/enroll-student to add face recognition data"
            }
        
        return response_data
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error adding student: {str(e)}"
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


