from flask import Flask, request, jsonify, render_template_string
import os
import logging
from config.database import init_database
from config.llm_config import LLMConfig
from services.vector_store import VectorStore
from services.rag_chain import RAGChain

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Initialize components
try:
    # Check LLM configuration
    llm_config = LLMConfig()
    llm_config.validate()
    
    init_database()
    vector_store = VectorStore()
    rag_chain = RAGChain(vector_store)
    
    logger.info(f"Application initialized successfully with LLM provider: {llm_config.provider}")
except Exception as e:
    logger.error(f"Failed to initialize application: {e}")
    raise

# Updated HTML template with provider info
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>RAG Demo on Cloud.gov</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        .container { max-width: 800px; margin: auto; }
        input, textarea { width: 100%; padding: 10px; margin: 10px 0; }
        button { background-color: #4CAF50; color: white; padding: 10px 20px; border: none; cursor: pointer; }
        button:hover { background-color: #45a049; }
        .response { background-color: #f0f0f0; padding: 20px; margin-top: 20px; border-radius: 5px; }
        .source { background-color: #e0e0e0; padding: 10px; margin: 5px 0; border-radius: 3px; }
        .info { background-color: #e3f2fd; padding: 15px; margin: 20px 0; border-radius: 5px; }
        .warning { background-color: #fff3cd; padding: 15px; margin: 20px 0; border-radius: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>RAG Demo on Cloud.gov</h1>
        <p>This demo uses pgvector for semantic search and can use either embedded or external language models.</p>
        
        <div id="providerInfo" class="info">
            <strong>Current Configuration:</strong><br>
            LLM Provider: <span id="llmProvider">Loading...</span><br>
            Model: <span id="modelName">Loading...</span>
        </div>
        
        <h2>Ask a Question</h2>
        <form id="queryForm">
            <input type="text" id="question" placeholder="Enter your question..." required>
            <button type="submit">Ask</button>
        </form>
        
        <div id="response" class="response" style="display:none;">
            <h3>Answer:</h3>
            <p id="answer"></p>
            <p><small>Provider: <span id="answerProvider"></span> | Model: <span id="answerModel"></span></small></p>
            <h3>Sources:</h3>
            <div id="sources"></div>
        </div>
        
        <h2>Document Count</h2>
        <p>Total documents in vector store: <span id="docCount">Loading...</span></p>
    </div>
    
    <script>
        // Load status
        fetch('/status')
            .then(res => res.json())
            .then(data => {
                document.getElementById('docCount').textContent = data.document_count;
                document.getElementById('llmProvider').textContent = data.llm_provider;
                document.getElementById('modelName').textContent = data.model_name;
                
                // Add warning for external providers
                if (data.llm_provider !== 'embedded') {
                    const warning = document.createElement('div');
                    warning.className = 'warning';
                    warning.innerHTML = '<strong>⚠️ Note:</strong> Using external LLM provider. Data will be sent outside Cloud.gov for processing.';
                    document.getElementById('providerInfo').after(warning);
                }
            });
        
        // Handle form submission
        document.getElementById('queryForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const question = document.getElementById('question').value;
            
            const response = await fetch('/query', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ question })
            });
            
            const data = await response.json();
            
            if (data.error) {
                document.getElementById('answer').textContent = 'Error: ' + data.error;
            } else {
                document.getElementById('answer').textContent = data.answer;
                document.getElementById('answerProvider').textContent = data.provider;
                document.getElementById('answerModel').textContent = data.model;
            }
            
            const sourcesDiv = document.getElementById('sources');
            sourcesDiv.innerHTML = '';
            
            if (data.sources) {
                data.sources.forEach((source, i) => {
                    const sourceDiv = document.createElement('div');
                    sourceDiv.className = 'source';
                    sourceDiv.innerHTML = `<strong>Source ${i+1} (similarity: ${source.similarity}):</strong><br>${source.content}`;
                    sourcesDiv.appendChild(sourceDiv);
                });
            }
            
            document.getElementById('response').style.display = 'block';
        });
    </script>
</body>
</html>
'''

@app.route('/')
def home():
    """Serve the demo interface"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/status', methods=['GET'])
def status():
    """Get application status"""
    try:
        doc_count = vector_store.get_document_count()
        llm_config = LLMConfig()
        
        return jsonify({
            "status": "healthy",
            "document_count": doc_count,
            "llm_provider": llm_config.provider,
            "model_name": llm_config.get_model_name(),
            "message": "RAG Demo on Cloud.gov is running"
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/upload', methods=['POST'])
def upload_documents():
    """Upload documents to the vector store"""
    try:
        data = request.get_json()
        documents = data.get('documents', [])
        
        if not documents:
            return jsonify({"error": "No documents provided"}), 400
        
        vector_store.add_documents(documents)
        
        return jsonify({
            "message": f"Successfully uploaded {len(documents)} documents",
            "total_documents": vector_store.get_document_count()
        })
    except Exception as e:
        logger.error(f"Error uploading documents: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/query', methods=['POST'])
def query():
    """Query the RAG system"""
    try:
        data = request.get_json()
        question = data.get('question', '').strip()
        
        if not question:
            return jsonify({"error": "No question provided"}), 400
        
        # Log if using external provider
        llm_config = LLMConfig()
        if not llm_config.is_embedded():
            logger.info(f"Processing query with external provider: {llm_config.provider}")
        
        result = rag_chain.query(question)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/clear', methods=['POST'])
def clear_documents():
    """Clear all documents from the vector store"""
    try:
        vector_store.clear_all()
        return jsonify({"message": "All documents cleared"})
    except Exception as e:
        logger.error(f"Error clearing documents: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/config', methods=['GET'])
def get_config():
    """Get current configuration (for debugging)"""
    try:
        llm_config = LLMConfig()
        return jsonify({
            "llm_provider": llm_config.provider,
            "model": llm_config.get_model_name(),
            "is_embedded": llm_config.is_embedded(),
            "available_providers": list(llm_config.model_configs.keys())
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)