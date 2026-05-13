from sentence_transformers import SentenceTransformer
import numpy as np

class EmbeddingService:
    def __init__(self, model_name='all-MiniLM-L6-v2'):
        """Initialize the embedding model"""
        print(f"Loading embedding model: {model_name}")
        self.model = SentenceTransformer(model_name)
        self.dimension = 384  # all-MiniLM-L6-v2 produces 384-dimensional embeddings

    def encode(self, texts):
        """Encode texts into embeddings"""
        if isinstance(texts, str):
            texts = [texts]
        
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return embeddings
    
    def encode_single(self, text):
        """Encode a single text into an embedding"""
        return self.encode([text])[0]