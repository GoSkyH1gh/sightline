import numpy as np
import faiss
import re
import threading
from pathlib import Path
from PIL import Image
from typing import List, Tuple, Optional, Union
import json
import os
from dataclasses import dataclass
from models import EmbeddingModel
from rapidocr_onnxruntime import RapidOCR
from difflib import SequenceMatcher
from metadata_service import MetadataService


@dataclass
class IndexProgress:
    """Shared progress state updated by the indexer and read by /progress endpoint."""
    is_running: bool = False
    phase: str = "idle"          # idle | scanning | loading | ocr | embedding | saving | done
    total: int = 0               # total images found
    processed: int = 0          # images processed so far in current phase
    from_cache: int = 0         # images reused from existing index (incremental)
    new_or_modified: int = 0    # images actually re-embedded
    abort_requested: bool = False # set to True to stop indexing

    def reset(self):
        self.is_running = True
        self.phase = "scanning"
        self.total = 0
        self.processed = 0
        self.from_cache = 0
        self.abort_requested = False
        self.new_or_modified = 0

    def done(self):
        self.is_running = False
        self.phase = "done"

class ImageIndexer:
    """Handles indexing and searching images using FAISS"""
    
    SUPPORTED_FORMATS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif'}
    BATCH_SIZE = 200  
    
    def __init__(self, model: EmbeddingModel, index_dir: str = "./index_data", use_ocr: bool = True, ocr_languages: List[str] = ['en'], progress: Optional['IndexProgress'] = None):
        self.model = model
        self.lock = threading.Lock()
        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(exist_ok=True)
        
        self.index_path = self.index_dir / "faiss.index"
        self.metadata_path = self.index_dir / "metadata.json"
        
        self.index = None
        self.image_paths = []
        self.ocr_texts = []
        self.metadata = []  # Image properties (size, date, camera, etc.)
        self.file_hashes = []  # Content hashes for robust deduplication/moving
        self.file_mtimes = {}  # Store file modification times
        self.indexed_folders = []  # Track all indexed folders
        self.last_model_name = None 
        
        # Shared progress state
        self.progress = progress if progress is not None else IndexProgress()
        
        self.use_ocr = use_ocr
        self.ocr_reader = None
        self._ocr_lang = ocr_languages[0] if ocr_languages else 'en'
        
        # Try to load existing index
        self._load_index()
    
    def _calculate_hash(self, file_path: Path) -> str:
        """Calculate a fast BLAKE2 hash of the file content"""
        import hashlib
        h = hashlib.blake2b(digest_size=20)
        try:
            with open(file_path, "rb") as f:
                # Read in 64kb chunks
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
            return h.hexdigest()
        except Exception as e:
            print(f"Hash failed for {file_path}: {e}")
            return f"err-{os.path.getmtime(file_path)}"

    def index_folder(self, folder_path: Path) -> int:
        """Index or update a folder incrementally without losing other indexed folders"""
        with self.lock:
            folder_path = Path(folder_path).resolve()
            folder_str = str(folder_path)
        
        # Check for model changes first - this forces a global refresh if the AI changed
        if self.is_indexed() and self._model_changed():
            print("[!] Model changed, performing full re-index of all folders")
            # We would ideally re-index all folders, but for now we'll just 
            # clear and start fresh with this folder to avoid mixed-model embeddings
            self.image_paths = []
            self.ocr_texts = []
            self.file_hashes = []
            self.file_mtimes = {}
            self.indexed_folders = []
            self.index = None

        if folder_str not in self.indexed_folders:
            self.indexed_folders.append(folder_str)
            print(f"Adding new folder to index: {folder_str}")
        
        return self._incremental_index(folder_path)

    def remove_folder(self, folder_path: Union[Path, str]) -> int:
        """Remove all images in a folder from the index and rebuild it."""
        folder_path = Path(folder_path).resolve()
        folder_str = str(folder_path)
        
        with self.lock:
            if folder_str not in self.indexed_folders:
                print(f"[!] Folder not in index: {folder_str}")
                return 0
            
            print(f"[-] Removing folder from index: {folder_str}")
            
            # Identify indices to keep
            keep_indices = []
            for i, path in enumerate(self.image_paths):
                if not path.startswith(folder_str):
                    keep_indices.append(i)
            
            num_removed = len(self.image_paths) - len(keep_indices)
            
            # Update metadata lists
            new_paths = []
            new_ocr = []
            new_metadata = []
            new_hashes = []
            new_mtimes = {}
            kept_embeddings = []
            
            for i in keep_indices:
                path = self.image_paths[i]
                new_paths.append(path)
                new_ocr.append(self.ocr_texts[i])
                new_metadata.append(self.metadata[i] if i < len(self.metadata) else {})
                new_hashes.append(self.file_hashes[i])
                new_mtimes[path] = self.file_mtimes.get(path, 0)
                if self.index:
                    kept_embeddings.append(self.index.reconstruct(i))
            
            self.image_paths = new_paths
            self.ocr_texts = new_ocr
            self.metadata = new_metadata
            self.file_hashes = new_hashes
            self.file_mtimes = new_mtimes
            self.indexed_folders.remove(folder_str)
            
            # Rebuild index
            if kept_embeddings:
                stacked = np.vstack(kept_embeddings)
                self.index = faiss.IndexFlatIP(stacked.shape[1])
                self.index.add(stacked)
            else:
                self.index = None
                
            self._save_index()
            print(f"[+] Removed {num_removed} images. Total index size: {len(self.image_paths)}")
            return num_removed

    def _incremental_index(self, folder_path: Path) -> int:
        """Update index incrementally, only touching files within folder_path"""
        prog = self.progress
        prog.reset()
        prog.phase = "scanning"
        print(f"[progress] Scanning {folder_path} for changes...")
        
        # 1. Scan current files on disk in the target folder
        current_disk_paths = {}
        for ext in self.SUPPORTED_FORMATS:
            for p in folder_path.rglob(f"*{ext}"):
                abs_p = p.resolve()
                current_disk_paths[str(abs_p)] = os.path.getmtime(abs_p)
        
        # 2. Identify "owned" images (existing records that belong to this folder)
        # We use startswith to check if the indexed path is within our folder_path
        owned_indices = []
        for i, path in enumerate(self.image_paths):
            if path.startswith(str(folder_path)):
                owned_indices.append(i)
        
        owned_paths_set = {self.image_paths[i] for i in owned_indices}
        disk_paths_set = set(current_disk_paths.keys())
        
        # Deleted: In Index (owned) but NOT on Disk
        deleted_paths = owned_paths_set - disk_paths_set
        
        # New/Modified candidates: On Disk
        # We'll check mtime and hash to decide if they really need re-processing
        potential_files = list(disk_paths_set)
        
        prog.total = len(disk_paths_set)
        print(f"[progress] Found {len(disk_paths_set)} files on disk. {len(deleted_paths)} removed files detected.")

        # 3. Plan the update: Keep, Re-use, or Process
        kept_embeddings = []
        kept_paths = []
        kept_ocr = []
        kept_metadata = []
        kept_hashes = []
        kept_mtimes = {}
        
        # First, preserve everything NOT in this folder
        for i, path in enumerate(self.image_paths):
            if not path.startswith(str(folder_path)):
                try:
                    kept_embeddings.append(self.index.reconstruct(i))
                    kept_paths.append(path)
                    kept_ocr.append(self.ocr_texts[i])
                    kept_metadata.append(self.metadata[i] if i < len(self.metadata) else {})
                    kept_hashes.append(self.file_hashes[i])
                    kept_mtimes[path] = self.file_mtimes.get(path, 0)
                except: pass

        # Map hashes to data for fast reuse
        # Structure: hash -> (ocr, metadata, embedding_vec)
        hash_to_data = {}
        for i in range(len(self.image_paths)):
            h = self.file_hashes[i]
            if h not in hash_to_data:
                try:
                    # Capture the embedding from the current index if possible
                    hash_to_data[h] = (
                        self.ocr_texts[i], 
                        self.metadata[i] if i < len(self.metadata) else {},
                        self.index.reconstruct(i)
                    )
                except: pass

        # 4. Process files on disk
        prog.phase = "hashing"
        files_to_actually_process = []
        
        for path_str in potential_files:
            prog.processed += 1
            mtime = current_disk_paths[path_str]
            old_mtime = self.file_mtimes.get(path_str, 0)
            
            # Optimization: If path and mtime match, it's definitely the same file
            if path_str in self.file_mtimes and abs(mtime - old_mtime) < 0.1:
                idx = self.image_paths.index(path_str)
                kept_embeddings.append(self.index.reconstruct(idx))
                kept_paths.append(path_str)
                kept_ocr.append(self.ocr_texts[idx])
                kept_metadata.append(self.metadata[idx] if idx < len(self.metadata) else {})
                kept_hashes.append(self.file_hashes[idx])
                kept_mtimes[path_str] = mtime
                continue
            
            # Mtime changed or path is new - check hash
            img_hash = self._calculate_hash(Path(path_str))
            
            if img_hash in hash_to_data:
                # REUSE existing AI results (moved file or duplicate)
                ocr, meta, vec = hash_to_data[img_hash]
                kept_embeddings.append(vec)
                kept_paths.append(path_str)
                kept_ocr.append(ocr)
                kept_metadata.append(meta)
                kept_hashes.append(img_hash)
                kept_mtimes[path_str] = mtime
                prog.from_cache += 1
            else:
                # TRULY NEW or MODIFIED content
                files_to_actually_process.append((path_str, img_hash, mtime))

            if prog.abort_requested:
                print("[progress] Indexing aborted during hashing phase.")
                prog.is_running = False
                prog.phase = "idle"
                return len(self.image_paths)

        prog.new_or_modified = len(files_to_actually_process)
        prog.total = len(files_to_actually_process)
        prog.processed = 0 # Reset processed count for the next phase
        prog.from_cache += (len(disk_paths_set) - len(files_to_actually_process) - (len(disk_paths_set - owned_paths_set))) # rough count
        
        # 5. Rebuild progress index with kept items
        if kept_embeddings:
            stacked = np.vstack(kept_embeddings)
            self.index = faiss.IndexFlatIP(stacked.shape[1])
            self.index.add(stacked)
        else:
            self.index = None
            
        self.image_paths = kept_paths
        self.ocr_texts = kept_ocr
        self.metadata = kept_metadata
        self.file_hashes = kept_hashes
        self.file_mtimes = kept_mtimes
        
        if not files_to_actually_process:
            print("[progress] All images resolved from cache or mtime.")
            self._save_index()
            prog.done()
            return len(self.image_paths)

        # 6. Process new images in batches
        print(f"[progress] Processing {len(files_to_actually_process)} new/modified images...")
        for i in range(0, len(files_to_actually_process), self.BATCH_SIZE):
            if prog.abort_requested:
                print("[progress] Indexing aborted between batches.")
                break
            batch = files_to_actually_process[i : i + self.BATCH_SIZE]
            batch_images = []
            batch_paths = []
            batch_ocr = []
            batch_metadata = []
            batch_hashes = []
            batch_mtimes = {}
            
            prog.phase = "ocr"
            for path_str, img_hash, mtime in batch:
                if prog.abort_requested: break
                try:
                    img_path = Path(path_str)
                    img = Image.open(img_path).convert('RGB')
                    text = self._extract_text(img_path) if self.use_ocr else ""
                    meta = MetadataService.extract_metadata(img_path)
                    
                    batch_images.append(img)
                    batch_paths.append(path_str)
                    batch_ocr.append(text)
                    batch_metadata.append(meta)
                    batch_hashes.append(img_hash)
                    batch_mtimes[path_str] = mtime
                    
                    prog.processed += 1
                except Exception as e:
                    print(f"[!] Error processing {path_str}: {e}")
            
            if not batch_images: continue
            
            prog.phase = "embedding"
            if prog.abort_requested: break
            embeddings = self.model.encode_images(batch_images)
            faiss.normalize_L2(embeddings)
            
            prog.phase = "saving"
            if self.index is None:
                self.index = faiss.IndexFlatIP(embeddings.shape[1])
            
            self.index.add(embeddings)
            self.image_paths.extend(batch_paths)
            self.ocr_texts.extend(batch_ocr)
            self.metadata.extend(batch_metadata)
            self.file_hashes.extend(batch_hashes)
            self.file_mtimes.update(batch_mtimes)
            
            self._save_index()
            print(f"[progress] Checkpoint: {len(self.image_paths)} total images")

        print(f"[progress] Incremental update complete. Total: {len(self.image_paths)} images")
        prog.done()
        return len(self.image_paths)

    def _model_changed(self) -> bool:
        """Check if model has changed"""
        if not self.last_model_name:
            return True # Assume changed if no previous record
        return self.last_model_name != self.model.model_name
    
    def search(self, query: str, top_k: int = 20, use_hybrid: bool = True, folder_filters: Optional[List[str]] = None) -> List[dict]:
        """
        Search for images matching the query, optionally filtered by multiple folders.
        """
        if not self.is_indexed():
            raise ValueError("No index loaded")
        
        # If hybrid search is disabled or OCR not available, use semantic search only
        if not use_hybrid or not self.use_ocr or len(self.ocr_texts) == 0:
            results = self._semantic_search(query, top_k, folder_filters)
        else:
            # Hybrid search: combine semantic and text matching
            results = self._hybrid_search(query, top_k, folder_filters)
            
        return self._format_results(results)

    def search_by_image(self, image: Image.Image, top_k: int = 20, folder_filters: Optional[List[str]] = None) -> List[dict]:
        """
        Visual search: find images similar to the provided PIL Image, optionally filtered by folders.
        """
        if not self.is_indexed():
            raise ValueError("No index loaded")
            
        # Generate embedding for the input image
        embedding = self.model.encode_images([image])
        embedding = embedding.reshape(1, -1)
        
        # Normalize for cosine similarity
        faiss.normalize_L2(embedding)
        
        # Search the index for a larger candidate pool if filtering is active
        search_k = min(top_k * 10 if folder_filters else top_k, len(self.image_paths))
        scores, indices = self.index.search(embedding, search_k)
        
        results = []
        # Pre-resolve and resolve all filters for faster matching
        resolved_filters = [str(Path(f).resolve()) for f in folder_filters] if folder_filters else []
        
        for i, idx in enumerate(indices[0]):
            if idx != -1 and idx < len(self.image_paths):
                path = self.image_paths[idx]
                
                # Apply folder filters
                if resolved_filters:
                    if not any(path.startswith(f) for f in resolved_filters):
                        continue
                    
                score = scores[0][i]
                ocr_text = self.ocr_texts[idx] if idx < len(self.ocr_texts) else ""
                results.append((path, score, ocr_text, score, 0.0))
                
                if len(results) >= top_k:
                    break
                    
        return self._format_results(results)

    def search_similar(self, image_path: str, top_k: int = 20, folder_filters: Optional[List[str]] = None) -> List[dict]:
        """
        Visual search: find images similar to the one at the given path, optionally filtered by folders.
        """
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
            
        with Image.open(path) as img:
            rgb_img = img.convert("RGB")
            return self.search_by_image(rgb_img, top_k, folder_filters)

    def _format_results(self, results: List[tuple]) -> List[dict]:
        """Convert result tuples to a list of dicts matching the SearchResult schema"""
        formatted = []
        for item in results:
            if len(item) == 5:
                img_path, score, ocr_text, semantic_score, text_score = item
            else:
                img_path, score, ocr_text = item
                semantic_score = score
                text_score = 0.0
                
            formatted.append({
                "image_path": str(img_path),
                "score": float(score),
                "semantic_score": float(semantic_score),
                "text_score": float(text_score),
                "ocr_text": ocr_text
            })
        return formatted

    def _semantic_search(self, query: str, top_k: int, folder_filters: Optional[List[str]] = None) -> List[Tuple[str, float, str]]:
        """Perform semantic search, optionally filtered by multiple folders"""
        query_embedding = self.model.encode_text(query)
        query_embedding = query_embedding.reshape(1, -1)
        faiss.normalize_L2(query_embedding)
        
        # Search a larger pool if filtering to ensure we find top_k matches in the target folder
        search_k = min(top_k * 10 if folder_filters else top_k, len(self.image_paths))
        scores, indices = self.index.search(query_embedding, search_k)
        
        results = []
        resolved_filters = [str(Path(f).resolve()) for f in folder_filters] if folder_filters else []

        for i, idx in enumerate(indices[0]):
            if idx != -1 and idx < len(self.image_paths):
                path = self.image_paths[idx]
                
                # Apply folder filters
                if resolved_filters:
                    if not any(path.startswith(f) for f in resolved_filters):
                        continue
                    
                score = scores[0][i]
                ocr_text = self.ocr_texts[idx] if idx < len(self.ocr_texts) else ""
                results.append((path, score, ocr_text, score, 0.0))
                
                if len(results) >= top_k:
                    break
        
        return results
    
    def _hybrid_search(self, query: str, top_k: int, folder_filters: Optional[List[str]] = None) -> List[tuple]:
        """Hybrid search, optionally filtered by folder"""
        # Expand candidate pool
        candidate_count = min(max(top_k * 20, 1000), len(self.image_paths))
        semantic_results = self._semantic_search(query, candidate_count, folder_filters)
        
        query_lower = query.lower()
        
        # Prepare regex for whole word match
        try:
            # Escape to handle special characters, \b for word boundaries
            word_pattern = re.compile(r'\b' + re.escape(query_lower) + r'\b', re.IGNORECASE)
        except:
            word_pattern = None

        hybrid_results = []
        
        for img_path, semantic_score, ocr_text, _, _ in semantic_results:
            ocr_text_lower = ocr_text.lower()
            text_score = 0.0
            
            if ocr_text_lower:
                # Tier 1: Whole word match (Highest Priority)
                if word_pattern and word_pattern.search(ocr_text_lower):
                    text_score = 1.0
                # Tier 2: Query is a prefix of a word in the text (Medium-High)
                elif any(word.startswith(query_lower) for word in ocr_text_lower.split()):
                    text_score = 0.7
                # Tier 1.5: Substring match in a "conglomerate" (joined words)
                elif query_lower in ocr_text_lower:
                    # If it's a substring match and the text has very few spaces, 
                    # it's likely a concatenated word match.
                    if ocr_text_lower.count(' ') < 3:
                        text_score = 0.9 # High priority for conglomerate matches
                    else:
                        # Tier 3: Substring match (Medium)
                        # ratio allows us to distinguish between exact match and 'needle in haystack'
                        length_ratio = len(query_lower) / len(ocr_text_lower)
                        text_score = 0.4 + (0.1 * min(length_ratio, 1.0))
                # Tier 4: Fuzzy match (Low)
                else:
                    matcher = SequenceMatcher(None, query_lower, ocr_text_lower)
                    text_score = matcher.ratio() * 0.3 # Keep fuzzy matches low priority
            
            # FUSION LOGIC
            # If we have a high-quality text match, it should significantly boost the result
            if text_score > 0.6:
                # Strong text match: 70% text weight, 30% semantic
                combined_score = (0.7 * text_score) + (0.3 * semantic_score)
            elif text_score > 0.3:
                # Moderate/Substring match: 40% text, 60% semantic
                combined_score = (0.4 * text_score) + (0.6 * semantic_score)
            else:
                # Fallback to semantic
                combined_score = semantic_score
            
            hybrid_results.append((img_path, float(combined_score), ocr_text, float(semantic_score), float(text_score)))
        
        # Sort and return top_k
        hybrid_results.sort(key=lambda x: x[1], reverse=True)
        return hybrid_results[:top_k]
    
    def _get_ocr_reader(self):
        """Lazily initialize RapidOCR on first call (must run in the worker thread).

        RapidOCR uses prefixed kwargs (det_use_dml, cls_use_dml, rec_use_dml)
        to route settings to each sub-model's InferSession via UpdateParameters.
        """
        if self.ocr_reader is None:
            print("Loading RapidOCR (provider=DmlExecutionProvider)...")
            self.ocr_reader = RapidOCR(
                det_use_dml=True,
                cls_use_dml=True,
                rec_use_dml=True,
            )
            print("[+] RapidOCR loaded (DmlExecutionProvider)")
        return self.ocr_reader

    def _extract_text(self, image_path: Path) -> str:
        """Extract text from image using RapidOCR"""
        try:
            reader = self._get_ocr_reader()
            result, _ = reader(str(image_path))
            if not result:
                return ""
            texts = [line[1] for line in result if line and len(line) > 1 and line[1]]
            return '\n'.join(texts)
        except Exception as e:
            print(f"OCR failed for {image_path}: {e}")
            return ""
    
    def is_indexed(self) -> bool:
        """Check if index is loaded"""
        return self.index is not None and len(self.image_paths) > 0
    
    def num_images(self) -> int:
        """Return number of indexed images"""
        return len(self.image_paths)
    
    def _save_index(self):
        """Save FAISS index and metadata"""
        faiss.write_index(self.index, str(self.index_path))
        
        with open(self.metadata_path, 'w') as f:
            json.dump({
                'image_paths': self.image_paths,
                'model_name': self.model.model_name,
                'ocr_texts': self.ocr_texts,
                'metadata': self.metadata,
                'file_hashes': self.file_hashes,
                'use_ocr': self.use_ocr,
                'file_mtimes': self.file_mtimes,
                'indexed_folders': self.indexed_folders
            }, f)
        
        self.last_model_name = self.model.model_name
        print(f"[+] Index saved to {self.index_path}")
    
    def _load_index(self):
        """Load existing FAISS index and metadata"""
        if self.index_path.exists() and self.metadata_path.exists():
            try:
                self.index = faiss.read_index(str(self.index_path))
                
                with open(self.metadata_path, 'r') as f:
                    metadata = json.load(f)
                    self.image_paths = metadata['image_paths']
                    self.ocr_texts = metadata.get('ocr_texts', [])
                    self.metadata = metadata.get('metadata', [])
                    self.file_hashes = metadata.get('file_hashes', [])
                    self.file_mtimes = metadata.get('file_mtimes', {})
                    
                    # Migrate from single indexed_folder to list
                    if 'indexed_folders' in metadata:
                        self.indexed_folders = metadata['indexed_folders']
                    elif 'indexed_folder' in metadata:
                        self.indexed_folders = [metadata['indexed_folder']] if metadata['indexed_folder'] else []
                    
                    self.use_ocr = metadata.get('use_ocr', self.use_ocr)
                    self.last_model_name = metadata.get('model_name')
                    
                    # Data migration for older versions
                    if not self.ocr_texts:
                        self.ocr_texts = [''] * len(self.image_paths)
                    
                    if not self.metadata:
                        self.metadata = [{} for _ in range(len(self.image_paths))]
                    
                    # CRITICAL: If hashes are missing (migration), we need to generate them once
                    if not self.file_hashes or len(self.file_hashes) != len(self.image_paths):
                        print("[!] Missing hashes in index. Generating them now (one-time migration)...")
                        self.file_hashes = []
                        valid_indices = []
                        new_paths = []
                        new_ocr = []
                        new_mtimes = {}
                        
                        for i, path_str in enumerate(self.image_paths):
                            p = Path(path_str)
                            if p.exists():
                                self.file_hashes.append(self._calculate_hash(p))
                                valid_indices.append(i)
                                new_paths.append(path_str)
                                new_ocr.append(self.ocr_texts[i])
                                new_mtimes[path_str] = self.file_mtimes.get(path_str, 0)
                        
                        # If we lost some files, we must filter the FAISS index too
                        if len(valid_indices) < len(self.image_paths) and self.index:
                            embeddings = []
                            for idx in valid_indices:
                                embeddings.append(self.index.reconstruct(idx))
                            stacked = np.vstack(embeddings)
                            self.index = faiss.IndexFlatIP(stacked.shape[1])
                            self.index.add(stacked)
                            self.image_paths = new_paths
                            self.ocr_texts = new_ocr
                            self.file_mtimes = new_mtimes
                        
                        self._save_index()
                
                print(f"[+] Loaded existing index with {len(self.image_paths)} images from {len(self.indexed_folders)} folders")
            except Exception as e:
                print(f"Failed to load index: {e}")
                import traceback
                traceback.print_exc()
                self.index = None
                self.image_paths = []
                self.ocr_texts = []
                self.file_hashes = []
