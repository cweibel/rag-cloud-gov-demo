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
        
        # Create index for vector similarity search
        cur.execute('''
            CREATE INDEX IF NOT EXISTS documents_embedding_idx 
            ON documents 
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
        ''')
        
        conn.commit()
    conn.close()
    print("Database initialized successfully")