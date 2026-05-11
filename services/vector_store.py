import json
import numpy as np
from config.database import get_db_connection
from services.embeddings import EmbeddingService
from psycopg2.extras import RealDictCursor

class VectorStore:
    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.index_created = self._check_index_exists()
    
    def _check_index_exists(self):
        """Check if vector index exists"""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) 
                    FROM pg_indexes 
                    WHERE tablename = 'documents' 
                    AND indexname = 'documents_embedding_idx'
                """)
                return cur.fetchone()[0] > 0
        finally:
            conn.close()
    
    def _create_index_if_needed(self):
        """Create vector index if it doesn't exist and we have enough data"""
        if self.index_created:
            return  # Index already exists
        
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # Check document count
                cur.execute("SELECT COUNT(*) FROM documents WHERE embedding IS NOT NULL")
                count = cur.fetchone()[0]
                
                # Only create index after we have at least 10 documents
                if count >= 10:
                    # Calculate optimal lists parameter
                    # For small datasets: 10-30, for large: sqrt(n)
                    lists = min(30, max(10, int(count ** 0.5)))
                    
                    print(f"Creating vector index with {count} documents, lists={lists}")
                    
                    try:
                        cur.execute(f'''
                            CREATE INDEX documents_embedding_idx 
                            ON documents 
                            USING ivfflat (embedding vector_cosine_ops)
                            WITH (lists = {lists})
                        ''')
                        conn.commit()
                        self.index_created = True
                        print(f"Vector index created successfully with lists={lists}")
                    except Exception as e:
                        # Index might already exist or other error
                        print(f"Could not create index: {e}")
                        conn.rollback()
        finally:
            conn.close()
    
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
            
            # Check if we should create the index now
            self._create_index_if_needed()
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
                # Drop the index if it exists
                cur.execute('DROP INDEX IF EXISTS documents_embedding_idx')
                # Clear all documents
                cur.execute('TRUNCATE TABLE documents RESTART IDENTITY')
            conn.commit()
            self.index_created = False  # Reset index status
            print("Cleared all documents from vector store")
        finally:
            conn.close()
    
    def optimize_index(self):
        """Manually optimize the vector index based on current data"""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # Get current document count
                cur.execute("SELECT COUNT(*) FROM documents WHERE embedding IS NOT NULL")
                count = cur.fetchone()[0]
                
                if count < 10:
                    print(f"Not enough documents ({count}) to optimize index")
                    return
                
                # Drop existing index
                cur.execute('DROP INDEX IF EXISTS documents_embedding_idx')
                
                # Calculate optimal parameters
                lists = min(100, max(10, int(count ** 0.5)))
                
                # Recreate with optimal parameters
                cur.execute(f'''
                    CREATE INDEX documents_embedding_idx 
                    ON documents 
                    USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = {lists})
                ''')
                
                conn.commit()
                self.index_created = True
                print(f"Index optimized for {count} documents with lists={lists}")
        finally:
            conn.close()