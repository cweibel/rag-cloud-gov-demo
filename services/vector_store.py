import json
import numpy as np
from config.database import get_db_connection
from services.embeddings import EmbeddingService
from psycopg2.extras import RealDictCursor

class VectorStore:
    def __init__(self):
        self.embedding_service = EmbeddingService()
    
    def add_documents(self, documents):
        """Add documents to the vector store"""
        if not documents:
            return
        
        # Extract content and generate embeddings
        contents = [doc['content'] for doc in documents]
        embeddings = self.embedding_service.encode(contents)
        
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                for doc, embedding in zip(documents, embeddings):
                    cur.execute(
                        '''INSERT INTO documents (content, embedding, metadata) 
                           VALUES (%s, %s, %s)''',
                        (
                            doc['content'], 
                            embedding.tolist(), 
                            json.dumps(doc.get('metadata', {}))
                        )
                    )
            conn.commit()
            print(f"Added {len(documents)} documents to vector store")
        finally:
            conn.close()
    
    def search(self, query, k=5):
        """Search for similar documents using vector similarity"""
        # Generate query embedding
        query_embedding = self.embedding_service.encode_single(query)
        
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Perform vector similarity search
                cur.execute(
                    '''SELECT id, content, metadata,
                       1 - (embedding <=> %s::vector) as similarity
                       FROM documents
                       ORDER BY embedding <=> %s::vector
                       LIMIT %s''',
                    (query_embedding.tolist(), query_embedding.tolist(), k)
                )
                results = cur.fetchall()
                
            return results
        finally:
            conn.close()
    
    def get_document_count(self):
        """Get the total number of documents in the store"""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute('SELECT COUNT(*) FROM documents')
                count = cur.fetchone()[0]
            return count
        finally:
            conn.close()
    
    def clear_all(self):
        """Clear all documents from the store"""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute('TRUNCATE TABLE documents RESTART IDENTITY')
            conn.commit()
            print("Cleared all documents from vector store")
        finally:
            conn.close()