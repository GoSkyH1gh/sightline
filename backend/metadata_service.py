import os
from pathlib import Path
from PIL import Image
from PIL.ExifTags import TAGS
from datetime import datetime

class MetadataService:
    @staticmethod
    def extract_metadata(image_path: Path) -> dict:
        """Extract basic metadata and EXIF data from an image."""
        metadata = {
            "size_bytes": os.path.getsize(image_path),
            "dimensions": None,
            "date_taken": None,
            "camera_model": None
        }
        
        try:
            with Image.open(image_path) as img:
                metadata["dimensions"] = f"{img.width}x{img.height}"
                
                # Extract EXIF
                exif_data = img._getexif()
                if exif_data:
                    for tag_id, value in exif_data.items():
                        tag = TAGS.get(tag_id, tag_id)
                        if tag == "DateTimeOriginal":
                            try:
                                # Standard format: YYYY:MM:DD HH:MM:SS
                                dt = datetime.strptime(str(value), "%Y:%m:%d %H:%M:%S")
                                metadata["date_taken"] = dt.isoformat()
                            except:
                                metadata["date_taken"] = str(value)
                        elif tag == "Model":
                            metadata["camera_model"] = str(value)
                
                # Fallback to mtime if date_taken is missing
                if not metadata["date_taken"]:
                    mtime = os.path.getmtime(image_path)
                    metadata["date_taken"] = datetime.fromtimestamp(mtime).isoformat()
                    
        except Exception as e:
            print(f"Metadata extraction failed for {image_path}: {e}")
            
        return metadata
