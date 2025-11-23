"""
Face Recognition System Configuration
Configuration management for MediaPipe face recognition
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class FaceRecognitionConfig:
    """Configuration class for face recognition system"""
    
    # ============================================
    # Pinecone Vector Database Configuration
    # ============================================
    PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
    PINECONE_ENVIRONMENT = os.getenv("PINECONE_ENVIRONMENT")  
    PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "student-faces")
    
    # ============================================
    # Face Recognition Parameters
    # ============================================
    FACE_DETECTION_CONFIDENCE = float(os.getenv("FACE_DETECTION_CONFIDENCE", "0.5"))
    FACE_RECOGNITION_TOLERANCE = float(os.getenv("FACE_RECOGNITION_TOLERANCE", "0.6"))
    
    # ============================================
    # Image Processing Parameters
    # ============================================
    MAX_IMAGE_SIZE = int(os.getenv("MAX_IMAGE_SIZE", "1000"))
    BRIGHTNESS_FACTOR = float(os.getenv("BRIGHTNESS_FACTOR", "1.1"))
    CONTRAST_FACTOR = float(os.getenv("CONTRAST_FACTOR", "1.2"))
    SHARPNESS_FACTOR = float(os.getenv("SHARPNESS_FACTOR", "1.1"))
    
    # ============================================
    # File Paths
    # ============================================
    STUDENT_IMAGES_PATH = os.getenv("STUDENT_IMAGES_PATH", "./student_images")
    TEMP_UPLOAD_PATH = os.getenv("TEMP_UPLOAD_PATH", "./temp_uploads")
    
    # ============================================
    # System Settings
    # ============================================
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    MIN_IMAGES_PER_STUDENT = int(os.getenv("MIN_IMAGES_PER_STUDENT", "3"))
    MAX_IMAGES_PER_STUDENT = int(os.getenv("MAX_IMAGES_PER_STUDENT", "10"))
    EMBEDDING_DIMENSION = 128  # Fixed for face recognition
    
    @classmethod
    def validate_config(cls):
        """Validate required configuration parameters"""
        missing_configs = []
        
        if not cls.PINECONE_API_KEY:
            missing_configs.append("PINECONE_API_KEY")
        
        if not cls.PINECONE_ENVIRONMENT:
            missing_configs.append("PINECONE_ENVIRONMENT")
        
        if missing_configs:
            raise ValueError(f"Missing required configuration: {', '.join(missing_configs)}")
        
        return True
    
    @classmethod
    def get_pinecone_config(cls):
        """Get Pinecone configuration dictionary"""
        return {
            "api_key": cls.PINECONE_API_KEY,
            "environment": cls.PINECONE_ENVIRONMENT,
            "index_name": cls.PINECONE_INDEX_NAME,
            "dimension": cls.EMBEDDING_DIMENSION
        }
    
    @classmethod
    def get_image_processing_config(cls):
        """Get image processing configuration"""
        return {
            "max_image_size": cls.MAX_IMAGE_SIZE,
            "brightness_factor": cls.BRIGHTNESS_FACTOR,
            "contrast_factor": cls.CONTRAST_FACTOR,
            "sharpness_factor": cls.SHARPNESS_FACTOR
        }
    
    @classmethod
    def get_recognition_config(cls):
        """Get face recognition configuration"""
        return {
            "detection_confidence": cls.FACE_DETECTION_CONFIDENCE,
            "recognition_tolerance": cls.FACE_RECOGNITION_TOLERANCE,
            "min_images": cls.MIN_IMAGES_PER_STUDENT,
            "max_images": cls.MAX_IMAGES_PER_STUDENT,
            "embedding_dimension": cls.EMBEDDING_DIMENSION
        }

# Global config instance
config = FaceRecognitionConfig()