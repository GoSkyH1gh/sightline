import sys
import os

# Fix Unicode output on Windows cp1252 terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding and sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path
import json
import asyncio
import io
import subprocess
from PIL import Image
from typing import List, Optional
from models import EmbeddingModel, CLIPModel
from indexer import ImageIndexer, IndexProgress
from watcher import FolderWatcher

app = FastAPI(title="Sightline API")

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration: Models
# available_models = ["fast": "clip-ViT-B-32", "accurate": "clip-ViT-L-14"]
ACTIVE_MODEL = "clip-ViT-L-14" 

# Global state
indexer: Optional[ImageIndexer] = None
model: Optional[EmbeddingModel] = None
watcher: Optional[FolderWatcher] = None
progress = IndexProgress()  # Shared progress state — written by indexer thread, read by /progress

# Models
class IndexRequest(BaseModel):
    folder_path: str

class SearchRequest(BaseModel):
    query: str
    top_k: int = 20
    use_hybrid: bool = True  # Enable hybrid search by default
    folder_paths: Optional[List[str]] = None

class ShowInFolderRequest(BaseModel):
    path: str

class SimilarSearchRequest(BaseModel):
    image_path: str
    top_k: int = 100
    folder_paths: Optional[List[str]] = None

class SearchResult(BaseModel):
    image_path: str
    score: float
    semantic_score: Optional[float] = None
    text_score: Optional[float] = None
    ocr_text: Optional[str] = None
    metadata: Optional[dict] = None

@app.on_event("startup")
async def startup_event():
    """Initialize the embedding model and watcher on startup"""
    global model, indexer, watcher
    model = CLIPModel(model_name=ACTIVE_MODEL, device="directml")
    indexer = ImageIndexer(model, progress=progress)
    
    # Start the folder watcher
    watcher = FolderWatcher(indexer)
    watcher.start()
    
    print(f"[+] Model '{ACTIVE_MODEL}' loaded successfully")
    print(f"[+] Folder watcher started for {len(indexer.indexed_folders)} folders")

@app.get("/")
async def root():
    return {"message": "Sightline API", "status": "running"}

@app.post("/index")
async def index_folder(request: IndexRequest):
    """Index all images in a folder"""
    folder = Path(request.folder_path).resolve()
    
    if not folder.exists() or not folder.is_dir():
        raise HTTPException(status_code=400, detail="Invalid folder path")
    
    try:
        num_indexed = await asyncio.to_thread(indexer.index_folder, folder)
        # Add a watch for this new folder if it's not already being watched
        if watcher:
            watcher.add_watch(str(folder))
            
        return {
            "status": "success",
            "images_indexed": num_indexed,
            "index_path": str(indexer.index_path)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/stop-indexing")
async def stop_indexing():
    """Abort in-progress indexing"""
    if progress:
        progress.abort_requested = True
        return {"status": "success", "message": "Abort requested..."}
    return {"status": "error", "message": "No indexer running"}

@app.post("/api/remove-folder")
async def remove_folder_api(request: IndexRequest):
    """Remove a folder from the index"""
    folder_path = request.folder_path
    
    try:
        # 1. Remove from index
        num_removed = await asyncio.to_thread(indexer.remove_folder, folder_path)
        
        # 2. Stop watching
        if watcher:
            watcher.remove_watch(folder_path)
            
        return {
            "status": "success",
            "images_removed": num_removed,
            "message": f"Successfully removed {folder_path} from search."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/search", response_model=List[SearchResult])
async def search_images(request: SearchRequest):
    """Search for images using text query"""
    if not indexer.is_indexed():
        raise HTTPException(status_code=400, detail="No images indexed yet")
    
    try:
        results = await asyncio.to_thread(
            indexer.search, request.query, request.top_k, request.use_hybrid, request.folder_paths
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/image")
async def get_image(path: str):
    """Serve an indexed image"""
    image_path = Path(path)
    
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    
    return FileResponse(image_path)

@app.get("/status")
async def get_status():
    """Get indexing status"""
    return {
        "model_loaded": model is not None,
        "indexed": indexer.is_indexed() if indexer else False,
        "num_images": indexer.num_images() if indexer and indexer.is_indexed() else 0,
        "model_name": model.model_name if model else None,
        "indexed_folders": indexer.indexed_folders if indexer else []
    }

@app.get("/progress")
async def get_progress():
    """Get live indexing progress — non-blocking, reads shared state updated by the indexer thread"""
    return {
        "is_running": progress.is_running,
        "phase": progress.phase,
        "total": progress.total,
        "processed": progress.processed,
        "from_cache": progress.from_cache,
        "new_or_modified": progress.new_or_modified,
    }

@app.post("/api/show-in-folder")
async def show_in_folder(request: ShowInFolderRequest):
    """Open Windows Explorer and select the file"""
    path = Path(request.path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        # /select tells explorer to open the parent folder and highlight the file
        # We use a list to avoid shell injection
        subprocess.run(['explorer.exe', '/select,', str(path.absolute())], check=True)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to open explorer: {e}")

@app.post("/api/search-image", response_model=List[SearchResult])
async def search_by_image(file: UploadFile = File(...), top_k: int = 100, folder_paths: Optional[List[str]] = None):
    """Search for images using an uploaded image (visual similarity)"""
    if not indexer.is_indexed():
        raise HTTPException(status_code=400, detail="No images indexed yet")
    
    try:
        # Read uploaded file
        content = await file.read()
        image = Image.open(io.BytesIO(content)).convert("RGB")
        
        # Perform visual search
        results = await asyncio.to_thread(indexer.search_by_image, image, top_k, folder_paths)
        return results
    except Exception as e:
        print(f"Image search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/search-similar", response_model=List[SearchResult])
async def search_similar(request: SimilarSearchRequest):
    """Search for images similar to one already in the index"""
    if not indexer.is_indexed():
        raise HTTPException(status_code=400, detail="No images indexed yet")
    
    try:
        results = await asyncio.to_thread(
            indexer.search_similar, request.image_path, request.top_k, request.folder_paths
        )
        return results
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        print(f"Similar search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
