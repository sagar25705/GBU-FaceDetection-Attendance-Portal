"""
Ultra-Simple Face Recognition System
Uses ONLY basic packages that come with standard Python/pip
No complex dependencies at all
"""

import hashlib
import json
import os
import base64
from typing import List, Dict, Optional
from pathlib import Path
from datetime import datetime
import logging

# Only use basic image processing
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# Try to import pinecone, but make it optional
try:
    import pinecone
    PINECONE_AVAILABLE = True
except ImportError:
    PINECONE_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class UltraSimpleFaceRecognition:
    """Ultra-simple face recognition using basic image statistics"""
    
    def __init__(self, pinecone_api_key: str = None, pinecone_environment: str = None, index_name: str = "student-faces"):
        """
        Initialize ultra-simple face recognition
        
        Args:
            pinecone_api_key: Optional Pinecone API key
            pinecone_environment: Optional Pinecone environment
            index_name: Index name
        """
        self.pinecone_api_key = pinecone_api_key
        self.pinecone_environment = pinecone_environment
        self.index_name = index_name
        self.index = None
        
        # Try to setup Pinecone if available
        if PINECONE_AVAILABLE and pinecone_api_key and pinecone_environment:
            try:
                self._setup_pinecone()
            except Exception as e:
                logger.warning(f"Pinecone setup failed, using local storage: {str(e)}")
                self.index = None
        
        # Local storage fallback
        self.local_storage_path = Path("local_face_storage.json")
        self.local_storage = self._load_local_storage()
        
        # Paths
        self.student_images_path = Path("student_images")
        self.temp_upload_path = Path("temp_uploads")
        
        # Create directories
        self.student_images_path.mkdir(exist_ok=True)
        self.temp_upload_path.mkdir(exist_ok=True)
        
        logger.info("✅ Ultra-Simple Face Recognition System initialized")
        logger.info(f"   PIL available: {PIL_AVAILABLE}")
        logger.info(f"   Pinecone available: {PINECONE_AVAILABLE and self.index is not None}")
    
    def _setup_pinecone(self):
        """Setup Pinecone with new API"""
        if not PINECONE_AVAILABLE:
            return
        
        try:
            # New Pinecone API syntax
            from pinecone import Pinecone
            
            pc = Pinecone(api_key=self.pinecone_api_key)
            
            # Check if index exists
            existing_indexes = pc.list_indexes().names()
            if self.index_name in existing_indexes:
                self.index = pc.Index(self.index_name)
                logger.info(f"✅ Connected to Pinecone index: {self.index_name}")
            else:
                logger.warning(f"Index {self.index_name} not found in: {existing_indexes}")
                
        except Exception as e:
            logger.error(f"Pinecone setup failed: {str(e)}")
            self.index = None
    
    def _load_local_storage(self) -> Dict:
        """Load local storage file"""
        if self.local_storage_path.exists():
            try:
                with open(self.local_storage_path, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {}
    
    def _save_local_storage(self):
        """Save local storage file"""
        try:
            with open(self.local_storage_path, 'w') as f:
                json.dump(self.local_storage, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save local storage: {str(e)}")
    
    def _extract_image_features(self, image_path: str) -> Optional[List[float]]:
        """
        Extract ultra-simple features from image
        
        Args:
            image_path: Path to image
            
        Returns:
            Simple feature vector or None
        """
        try:
            if not PIL_AVAILABLE:
                # Fallback: use file stats and content hash
                stat = os.stat(image_path)
                with open(image_path, 'rb') as f:
                    content = f.read()
                
                # Create simple features from file
                features = [
                    float(stat.st_size % 1000),  # File size feature
                    float(len(content) % 100),   # Content length feature
                    float(sum(content[:100]) % 256),  # First 100 bytes sum
                    float(sum(content[-100:]) % 256), # Last 100 bytes sum
                ]
                
                # Add hash-based features
                hash_obj = hashlib.md5(content)
                hash_bytes = hash_obj.digest()
                
                # Convert hash bytes to features
                for i in range(0, min(len(hash_bytes), 32), 4):
                    chunk = hash_bytes[i:i+4]
                    feature_val = sum(chunk) / 255.0
                    features.append(feature_val)
                
                # Pad to 128 dimensions
                while len(features) < 128:
                    features.append(0.0)
                
                return features[:128]
            
            # PIL-based feature extraction
            with Image.open(image_path) as img:
                # Convert to RGB and resize
                img = img.convert('RGB')
                img = img.resize((64, 64))  # Small size for simplicity
                
                # Extract simple statistical features
                features = []
                
                # Get pixel data
                pixels = list(img.getdata())
                
                # Color channel statistics
                r_values = [p[0] for p in pixels]
                g_values = [p[1] for p in pixels]
                b_values = [p[2] for p in pixels]
                
                # Add statistical features for each channel
                for channel_values in [r_values, g_values, b_values]:
                    features.extend([
                        sum(channel_values) / len(channel_values),  # Mean
                        max(channel_values),                        # Max
                        min(channel_values),                        # Min
                        len([v for v in channel_values if v > 128]) / len(channel_values)  # Bright pixel ratio
                    ])
                
                # Add histogram-like features (simple bins)
                for channel_values in [r_values, g_values, b_values]:
                    bins = [0] * 8  # 8 bins per channel
                    for val in channel_values:
                        bin_idx = min(val // 32, 7)  # 256/32 = 8 bins
                        bins[bin_idx] += 1
                    
                    # Normalize bins
                    total = sum(bins)
                    if total > 0:
                        bins = [b / total for b in bins]
                    
                    features.extend(bins)
                
                # Add texture-like features (simplified)
                # Compare adjacent pixels
                edge_count = 0
                for i in range(len(pixels) - 1):
                    diff = abs(sum(pixels[i]) - sum(pixels[i+1]))
                    if diff > 100:  # Threshold for edge
                        edge_count += 1
                
                features.append(edge_count / len(pixels))
                
                # Add more simple features to reach ~128 dimensions
                # Quadrant analysis
                width, height = 64, 64
                for quad_y in range(0, height, height//4):
                    for quad_x in range(0, width, width//4):
                        quad_pixels = []
                        for y in range(quad_y, min(quad_y + height//4, height)):
                            for x in range(quad_x, min(quad_x + width//4, width)):
                                idx = y * width + x
                                if idx < len(pixels):
                                    quad_pixels.append(sum(pixels[idx]))
                        
                        if quad_pixels:
                            avg_intensity = sum(quad_pixels) / len(quad_pixels)
                            features.append(avg_intensity / 765.0)  # Normalize by max RGB sum
                
                # Pad or truncate to 128 dimensions
                while len(features) < 128:
                    features.append(0.0)
                
                return features[:128]
                
        except Exception as e:
            logger.error(f"Error extracting features from {image_path}: {str(e)}")
            return None
    
    def enroll_student(self, roll_no: str, student_name: str, image_folder_path: str) -> bool:
        """
        Enroll student using ultra-simple method
        
        Args:
            roll_no: Student roll number
            student_name: Student name
            image_folder_path: Path to images folder
            
        Returns:
            True if successful
        """
        try:
            logger.info(f"Enrolling student: {student_name} ({roll_no})")
            
            # Get image files
            image_folder = Path(image_folder_path)
            if not image_folder.exists():
                logger.error(f"Folder does not exist: {image_folder_path}")
                return False
            
            # Find image files
            image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.gif'}
            image_files = [
                f for f in image_folder.iterdir()
                if f.suffix.lower() in image_extensions
            ]
            
            if len(image_files) < 1:
                logger.error("No image files found")
                return False
            
            # Extract features from all images
            all_features = []
            for image_file in image_files:
                features = self._extract_image_features(str(image_file))
                if features:
                    all_features.append(features)
            
            if not all_features:
                logger.error("No valid features extracted")
                return False
            
            # Average features if multiple images
            if len(all_features) > 1:
                averaged_features = []
                for i in range(len(all_features[0])):
                    avg_val = sum(feat[i] for feat in all_features) / len(all_features)
                    averaged_features.append(avg_val)
            else:
                averaged_features = all_features[0]
            
            # Store the features
            student_data = {
                "roll_no": roll_no,
                "name": student_name,
                "features": averaged_features,
                "enrolled_at": datetime.now().isoformat(),
                "images_processed": len(all_features)
            }
            
            # Try Pinecone first, fallback to local storage
            if self.index:
                try:
                    # Ensure all values are floats for Pinecone
                    float_features = [float(x) for x in averaged_features]
                    
                    self.index.upsert(
                        vectors=[(roll_no, float_features, {
                            "roll_no": roll_no,
                            "name": student_name,
                            "enrolled_at": student_data["enrolled_at"]
                        })]
                    )
                    logger.info("✅ Stored in Pinecone")
                except Exception as e:
                    logger.warning(f"Pinecone storage failed, using local: {str(e)}")
                    self.local_storage[roll_no] = student_data
                    self._save_local_storage()
            else:
                # Local storage
                self.local_storage[roll_no] = student_data
                self._save_local_storage()
                logger.info("✅ Stored locally")
            
            logger.info(f"✅ Student {student_name} ({roll_no}) enrolled!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error enrolling student: {str(e)}")
            return False
    
    def recognize_student(self, image_path: str, top_k: int = 3) -> List[Dict]:
        """
        Recognize student from image
        
        Args:
            image_path: Path to image to recognize
            top_k: Number of top matches
            
        Returns:
            List of matches
        """
        try:
            logger.info(f"Recognizing from: {image_path}")
            
            # Extract features from query image
            query_features = self._extract_image_features(image_path)
            if not query_features:
                return []
            
            matches = []
            
            # Try Pinecone first
            # Try Pinecone first
            if self.index:
                try:
                    # Ensure query features are floats
                    float_query_features = [float(x) for x in query_features]
                    
                    results = self.index.query(
                        vector=float_query_features,
                        top_k=top_k,
                        include_metadata=True
                    )
                    
                    for match in results['matches']:
                        confidence = float(match['score']) * 100
                        metadata = match['metadata']
                        
                        matches.append({
                            "roll_no": metadata['roll_no'],
                            "name": metadata['name'],
                            "confidence": confidence,
                            "is_match": confidence > 60,  # Simple threshold
                            "method": "pinecone"
                        })
                    
                    return matches
                    
                except Exception as e:
                    logger.warning(f"Pinecone query failed: {str(e)}")
            
            # Fallback to local storage
            for roll_no, student_data in self.local_storage.items():
                stored_features = student_data["features"]
                
                # Simple cosine similarity
                dot_product = sum(a * b for a, b in zip(query_features, stored_features))
                norm_a = sum(a * a for a in query_features) ** 0.5
                norm_b = sum(b * b for b in stored_features) ** 0.5
                
                if norm_a > 0 and norm_b > 0:
                    similarity = dot_product / (norm_a * norm_b)
                    confidence = similarity * 100
                    
                    matches.append({
                        "roll_no": student_data["roll_no"],
                        "name": student_data["name"],
                        "confidence": confidence,
                        "is_match": confidence > 60,
                        "method": "local"
                    })
            
            # Sort by confidence
            matches.sort(key=lambda x: x['confidence'], reverse=True)
            
            return matches[:top_k]
            
        except Exception as e:
            logger.error(f"❌ Error in recognition: {str(e)}")
            return []
    
    def get_system_stats(self) -> Dict:
        """Get system statistics"""
        try:
            if self.index:
                try:
                    stats = self.index.describe_index_stats()
                    return {
                        "total_enrolled_students": stats.total_vector_count,
                        "storage_method": "pinecone",
                        "status": "operational"
                    }
                except:
                    pass
            
            # Local storage stats
            return {
                "total_enrolled_students": len(self.local_storage),
                "storage_method": "local",
                "status": "operational"
            }
            
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def delete_student(self, roll_no: str) -> bool:
        """Delete student"""
        try:
            if self.index:
                try:
                    self.index.delete(ids=[roll_no])
                except:
                    pass
            
            if roll_no in self.local_storage:
                del self.local_storage[roll_no]
                self._save_local_storage()
            
            return True
            
        except Exception as e:
            logger.error(f"Error deleting student: {str(e)}")
            return False


# Easy setup function
def create_ultra_simple_face_system(pinecone_api_key=None, pinecone_environment=None):
    """Create ultra-simple face system"""
    return UltraSimpleFaceRecognition(pinecone_api_key, pinecone_environment)


if __name__ == "__main__":
    print("🎯 Ultra-Simple Face Recognition")
    print("Works with ANY Python environment!")
    
    # Test basic functionality
    system = create_ultra_simple_face_system()
    stats = system.get_system_stats()
    print(f"System stats: {stats}")