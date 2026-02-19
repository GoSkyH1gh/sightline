from abc import ABC, abstractmethod
import numpy as np
from PIL import Image
from typing import List
from sentence_transformers import SentenceTransformer

class EmbeddingModel(ABC):
    """Abstract base class for embedding models - easy to swap implementations"""
    
    @abstractmethod
    def encode_images(self, images: List[Image.Image]) -> np.ndarray:
        """Encode images to embeddings"""
        pass
    
    @abstractmethod
    def encode_text(self, text: str) -> np.ndarray:
        """Encode text to embeddings"""
        pass
    
    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return model name"""
        pass


class CLIPModel(EmbeddingModel):
    """CLIP model using sentence-transformers ONNX backend with DirectML GPU acceleration.
    
    On first run the model is auto-exported to ONNX and cached locally.
    Subsequent runs load from cache instantly.
    """
    
    def __init__(self, model_name: str = "clip-ViT-B-32", device: str = "directml"):
        self._model_name = model_name
        self.device = device

        # Map device string to ONNX Runtime execution provider
        if device == "directml":
            provider = "DmlExecutionProvider"
        elif device == "cuda":
            provider = "CUDAExecutionProvider"
        else:
            provider = "CPUExecutionProvider"

        print(f"Loading {model_name} (ONNX backend, provider={provider})...")
        self.model = SentenceTransformer(
            model_name,
            backend="onnx",
            model_kwargs={"provider": provider},
        )
        print(f"[+] Model loaded on {provider}")
    
    def encode_images(self, images: List[Image.Image]) -> np.ndarray:
        """Encode images to embeddings"""
        embeddings = self.model.encode(
            images,
            batch_size=128,
            show_progress_bar=True,
            convert_to_numpy=True,
        )
        return embeddings
    
    def encode_text(self, text: str) -> np.ndarray:
        """Encode text to embeddings"""
        embedding = self.model.encode(
            [text],
            convert_to_numpy=True,
        )
        return embedding[0]
    
    @property
    def model_name(self) -> str:
        return self._model_name
