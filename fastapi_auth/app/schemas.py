from pydantic import BaseModel, EmailStr, ConfigDict, validator
from datetime import datetime
from typing import Optional
import uuid

# Existing User schemas
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    
    @validator('password')
    def validate_password(cls, v):
        if len(v.encode('utf-8')) > 72:
            raise ValueError('Password cannot be longer than 72 bytes')
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters long')
        return v

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    user_id: uuid.UUID
    email: str
    name: str
    role: int
    created_at: datetime
    roll_no: Optional[str] = None

class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: str
    email: str
    name: str
    role: int

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenData(BaseModel):
    email: Optional[str] = None

# NEW: Teacher schemas (MISSING FROM YOUR SCHEMAS)
class TeacherCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    phone_number: Optional[str]
    school_id: int
    department: Optional[str] = None
    subject_specialisation: Optional[str] = None
    
    @validator('password')
    def validate_password(cls, v):
        if len(v.encode('utf-8')) > 72:
            raise ValueError('Password cannot be longer than 72 bytes')
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters long')
        return v

class TeacherResponse(BaseModel):
    teacher_id: int
    user_id: uuid.UUID
    name: str
    email: str
    school_id: int
    phone_number: Optional[str]
    department: Optional[str]
    subject_specialisation: Optional[str]
    message: str

class TeacherUpdate(BaseModel):
    name: Optional[str]
    email: Optional[EmailStr]
    phone_number: Optional[str]
    department: Optional[str]
    subject_specialisation: Optional[str]
    school_id: Optional[int]


# NEW: Student schemas (MISSING FROM YOUR SCHEMAS)
class StudentCreate(BaseModel):
    roll_no: str
    name: str
    phone_number: Optional[str] = None
    email: Optional[EmailStr] = None
    semester: int
    year: int
    school_id: int
    department_id: int
    
    @validator('semester')
    def validate_semester(cls, v):
        if v < 1 or v > 8:
            raise ValueError('Semester must be between 1 and 8')
        return v

class StudentResponse(BaseModel):
    roll_no: str
    name: str
    email: Optional[str]
    phone_number: Optional[str]
    semester: int
    year: int
    school_id: int
    department_id: int
    temporary_password: Optional[str]  # <- ADD THIS
    message: str
    next_steps: Optional[dict] = None

    model_config = ConfigDict(from_attributes=True)



class AttendanceGenerate(BaseModel):
    course_code: str
    class_id: int


class MarkAttendance(BaseModel):
    unique_code: str
    roll_no: str
    is_manual: bool = False
