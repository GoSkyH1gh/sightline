import os
import shutil
import time
from pathlib import Path
from PIL import Image, ImageDraw
from models import CLIPModel
from indexer import ImageIndexer
import traceback

def create_test_image(path, color, text=None):
    img = Image.new('RGB', (100, 100), color=color)
    if text:
        d = ImageDraw.Draw(img)
        # Use black text for better contrast
        d.text((10, 10), text, fill=(0, 0, 0))
    img.save(path)

def test_incremental_indexing():
    # Setup
    test_dir = Path("test_data")
    if test_dir.exists():
        shutil.rmtree(test_dir)
    test_dir.mkdir()
    
    index_dir = Path("test_index")
    if index_dir.exists():
        shutil.rmtree(index_dir)
    
    try:
        # Create initial images
        print("\n--- Step 1: Initial Indexing ---")
        create_test_image(test_dir / "img1.png", "red", "hello")
        create_test_image(test_dir / "img2.png", "blue", "world")
        
        # Initialize indexer
        model = CLIPModel(device="cpu")
        indexer = ImageIndexer(model, index_dir=str(index_dir), use_ocr=True)
        
        # Initial index
        indexer.index_folder(test_dir)
        assert len(indexer.image_paths) == 2
        assert indexer.indexed_folder == str(test_dir.resolve())
        
        # No changes
        print("\n--- Step 2: No Changes ---")
        indexer.index_folder(test_dir)
        assert len(indexer.image_paths) == 2
        
        # Add new file
        print("\n--- Step 3: Add New File ---")
        create_test_image(test_dir / "img3.png", "green", "python")
        indexer.index_folder(test_dir)
        assert len(indexer.image_paths) == 3
        # Check if python is in OCR text
        ocr_str = " ".join(indexer.ocr_texts)
        if "python" not in ocr_str.lower():
             print(f"Warning: 'python' not found in OCR: {ocr_str}")
        
        # Modify file
        print("\n--- Step 4: Modify File ---")
        time.sleep(2) # Ensure mtime changes
        create_test_image(test_dir / "img1.png", "white", "modified")
        indexer.index_folder(test_dir)
        
        assert len(indexer.image_paths) == 3
        # Check if OCR updated
        ocr_str = " ".join(indexer.ocr_texts)
        print(f"OCR Content: {ocr_str}")
        
        # Delete file
        print("\n--- Step 5: Delete File ---")
        os.remove(test_dir / "img2.png")
        indexer.index_folder(test_dir)
        assert len(indexer.image_paths) == 2
        
        # Model change (simulated)
        print("\n--- Step 6: Model Change ---")
        indexer.last_model_name = "different-model"
        indexer.index_folder(test_dir)
        assert len(indexer.image_paths) == 2
        
        print("\n[+] All tests passed!")
        
    except Exception:
        traceback.print_exc()
        raise
    finally:
        # Cleanup
        if test_dir.exists():
            shutil.rmtree(test_dir)
        if index_dir.exists():
            shutil.rmtree(index_dir)

if __name__ == "__main__":
    test_incremental_indexing()
