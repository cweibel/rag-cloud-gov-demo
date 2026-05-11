import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor

def get_db_connection():
    """Get database connection from Cloud Foundry VCAP_SERVICES"""
    vcap = json.loads(os.getenv('VCAP_SERVICES', '{}'))
    
    if 'aws-rds' not in vcap:
        raise ValueError("No RDS service bound. Please bind an aws-rds service.")
    
    creds = vcap['aws-rds'][0]['credentials']
    
    conn = psycopg2.connect(
        host=creds['host'],
        port=creds['port'],
        database=creds['db_name'],
        user=creds['username'],
        password=creds['password']
    )
    
    # Enable pgvector extension
    with conn.cursor() as cur:
        cur.execute('CREATE EXTENSION IF NOT EXISTS vector')
        conn.commit()
    
    return conn

def init_database():
    """Initialize database with vector table"""
    conn = get_db_connection()
    with conn.cursor() as cur:
        # Create the documents table with vector column
        cur.execute('''
            CREATE TABLE IF NOT EXISTS documents (
                id SERIAL PRIMARY KEY,
                content TEXT NOT NULL,
                embedding vector(384),
                metadata JSONB DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Don't create index immediately - wait for data
        # Index will be created after first batch of documents
        
        conn.commit()
    conn.close()
    print("Database initialized successfully")

def create_index_if_needed():
    """Create vector index if it doesn't exist and we have enough data"""
    conn = get_db_connection()
    with conn.cursor() as cur:
        # Check if index exists
        cur.execute("""
            SELECT COUNT(*) 
            FROM pg_indexes 
            WHERE tablename = 'documents' 
            AND indexname = 'documents_embedding_idx'
        """)
        
        if cur.fetchone()[0] == 0:
            # Check document count
            cur.execute("SELECT COUNT(*) FROM documents")
            count = cur.fetchone()[0]
            
            if count >= 10:  # Only create index after we have some data
                lists = min(30, max(10, int(count ** 0.5)))
                cur.execute(f'''
                    CREATE INDEX documents_embedding_idx 
                    ON documents 
                    USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = {lists})
                ''')
                conn.commit()
                print(f"Created vector index with lists={lists}")
    
    conn.close()