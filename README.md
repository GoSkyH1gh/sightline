# �️ Sightline | Local Image Intelligence

> **"Behold your images."**

* note: this is 100% vibecoded and just for fun

Sightline is a privacy-first, local-only semantic search engine for your photo library. It allows you to search through thousands of images using natural language (e.g., *"a sunset over the sea"*), visual similarity, or even OCR text contained within the images.

[![Vibecoded](https://img.shields.io/badge/Vibe-coded-blueviolet?style=flat-square)](#)
[![AMD Optimized](https://img.shields.io/badge/AMD-Optimized-red?style=flat-square)](#)
---

## ✨ Features

- 🧠 **Semantic Search**: Powered by OpenAI's **CLIP** model. Search by description, not just filename.
- 🖼️ **Visual Similarity**: Find "more like this" by dropping an image or clicking a result.
- 📝 **Hybrid OCR**: Search for text *inside* images (documents, screenshots, labels) using **RapidOCR**.
- 🚀 **AMD GPU Acceleration**: Optimized for Windows users with AMD GPUs via **ONNX Runtime** and **DirectML**.
- ⚡ **Incremental Indexing**: Blazing fast updates. Only processes new or modified files using BLAKE2 hashing.
- 📂 **Folder Watching**: Automatically updates your index when you add or remove files from watched folders.
- 🔒 **100% Local**: No API keys, no tracking, no cloud. Your data never leaves your machine.

---

## 🛠️ Tech Stack

- **Backend**: FastAPI, FAISS (Vector Store), CLIP (Sentence-Transformers), RapidOCR.
- **Frontend**: React, Vite, Lucide Icons, Sonner.
- **Acceleration**: ONNX Runtime with `DirectML` (GPU) and `CPU` fallbacks.
- **Project Style**: Fully **Vibecoded** (built with AI assistance as a "vibing" personal project).

---

## 🚀 Getting Started (Windows)

This project is designed to run easily on Windows with an AMD GPU (though it works on any hardware).

### 1. Prerequisites
- [Python 3.10+](https://www.python.org/)
- [pnpm](https://pnpm.io/) (for frontend)
- [uv](https://github.com/astral-sh/uv) (recommended for blistering fast python dependency management)

### 2. Quick Start
Just run the included batch script:
```batch
start.bat
```
This will automatically:
1. Initialize the backend environment.
2. Start the FastAPI server (Port 8000).
3. Start the Vite dev server (Port 5173).

---

## 💡 Usage

1. **Pick a Folder**: Type or paste a folder path (e.g., `C:\Users\You\Pictures`).
2. **Index**: Let Sightline process your images. You'll see real-time progress for OCR and Embedding.
3. **Search**: 
   - Type queries like *"workspace with multiple monitors"*
   - Toggle **"Text Search"** to prioritize OCR matches.
   - Drag and drop an image onto the UI to find visually similar ones.

---

## 📝 Why Sightline?

This started as a quest for a local, fast, and modern way to navigate a massive personal image library. It was built for fun, optimized for my own AMD hardware, and refined using AI "Vibe Coding" techniques. It's proof that you don't need the cloud to have high-intelligence search.

---

## ⚠️ Privacy & Security

Sightline is a personal project. It runs a local web server (FastAPI). While it's designed for local use, avoid exposing the backend port (8000) to the open internet.

---

## Project Structure

- `backend/`: Python logic, indexing, and model serving.
- `frontend/`: React-based UI.
- `index_data/`: (Local only) Where your FAISS index and metadata are stored.
