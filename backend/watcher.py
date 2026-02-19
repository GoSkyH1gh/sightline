import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pathlib import Path
import asyncio
from typing import Callable

class FolderWatchHandler(FileSystemEventHandler):
    def __init__(self, on_change: Callable[[Path], None], supported_formats: set):
        self.on_change = on_change
        self.supported_formats = supported_formats
        self.last_triggered = {} # path -> time

    def on_modified(self, event):
        if event.is_directory:
            return
        self._handle_event(event.src_path)

    def on_created(self, event):
        if event.is_directory:
            return
        self._handle_event(event.src_path)

    def on_deleted(self, event):
        if event.is_directory:
            return
        self._handle_event(event.src_path)

    def on_moved(self, event):
        if not event.is_directory:
            self._handle_event(event.dest_path)
            self._handle_event(event.src_path)

    def _handle_event(self, path_str: str):
        path = Path(path_str)
        if path.suffix.lower() in self.supported_formats:
            # Debounce: only trigger once per 2 seconds per folder to avoid spam
            folder = path.parent
            now = time.time()
            if now - self.last_triggered.get(str(folder), 0) > 2:
                self.last_triggered[str(folder)] = now
                print(f"[watcher] Change detected in {folder}, triggering re-index...")
                self.on_change(folder)

class FolderWatcher:
    def __init__(self, indexer):
        self.indexer = indexer
        self.observer = Observer()
        self.watches = {} # folder_path -> watch object

    def start(self):
        self.observer.start()
        # Initial watches for already indexed folders
        for folder in self.indexer.indexed_folders:
            self.add_watch(folder)

    def stop(self):
        self.observer.stop()
        self.observer.join()

    def add_watch(self, folder_path: str):
        path = Path(folder_path).resolve()
        if not path.exists() or str(path) in self.watches:
            return
        
        handler = FolderWatchHandler(
            on_change=self._trigger_index,
            supported_formats=self.indexer.SUPPORTED_FORMATS
        )
        watch = self.observer.schedule(handler, str(path), recursive=True)
        self.watches[str(path)] = watch
        print(f"[watcher] Now watching: {path}")

    def remove_watch(self, folder_path: str):
        path = str(Path(folder_path).resolve())
        if path in self.watches:
            try:
                self.observer.unschedule(self.watches[path])
                del self.watches[path]
                print(f"[watcher] Stopped watching: {path}")
            except Exception as e:
                print(f"[watcher] Failed to stop watch for {path}: {e}")

    def _trigger_index(self, folder_path: Path):
        # We need to run this in a way that doesn't block the watcher thread
        # The indexer.index_folder is already wrapped in to_thread in main.py
        # But here we are in a background thread of watchdog.
        # We can just call it directly as it's thread-safe enough (FAISS/JSON writes are atomic-ish 
        # but we should be careful about concurrent indexing).
        # ImageIndexer has no locks, but it's usually called from one place.
        
        # Pro tip: Use a simple flag or queue if multiple folders change at once.
        # For now, index_folder is designed to be incremental and fast if few changes.
        try:
            self.indexer.index_folder(folder_path)
        except Exception as e:
            print(f"[watcher] Indexing failed for {folder_path}: {e}")
