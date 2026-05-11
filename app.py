from flask import Flask, request, jsonify, render_template_string
import os
import logging
from config.database import init_database
from config.llm_config import LLMConfig
from services.vector_store import VectorStore
from services.rag_chain import RAGChain
from werkzeug.utils import secure_filename
import re
import yaml

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

# Updated HTML template with provider info and file upload form
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
        
        /* New styles for file upload */
        .upload-section { background-color: #f8f9fa; padding: 20px; margin: 20px 0; border-radius: 5px; }
        input[type="file"] { width: auto; padding: 5px; }
        .upload-result { margin-top: 15px; padding: 15px; background-color: #fff; border-radius: 5px; }
        .upload-result ul { list-style-type: none; padding-left: 0; }
        .upload-result li { padding: 5px 0; }
        .success { color: #28a745; }
        .skipped { color: #ffc107; }
        .error { color: #dc3545; }
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
        
        <!-- New file upload section -->
        <div class="upload-section">
            <h2>Upload Markdown Files</h2>
            <p>Select one or more markdown files (.md or .markdown) to add to the knowledge base.</p>
            <form id="uploadForm" enctype="multipart/form-data">
                <input type="file" id="fileInput" multiple accept=".md,.markdown" />
                <button type="submit">Upload Files</button>
            </form>
            <div id="uploadResult" class="upload-result" style="display:none;"></div>
        </div>
        
        <h2>Document Count</h2>
        <p>Total documents in vector store: <span id="docCount">Loading...</span></p>
    </div>
    
    <script>
        // Load status
        function loadStatus() {
            fetch('/status')
                .then(res => res.json())
                .then(data => {
                    document.getElementById('docCount').textContent = data.document_count;
                    document.getElementById('llmProvider').textContent = data.llm_provider;
                    document.getElementById('modelName').textContent = data.model_name;
                    
                    // Add warning for external providers
                    if (data.llm_provider !== 'embedded') {
                        const existingWarning = document.querySelector('.warning');
                        if (!existingWarning) {
                            const warning = document.createElement('div');
                            warning.className = 'warning';
                            warning.innerHTML = '<strong>⚠️ Note:</strong> Using external LLM provider. Data will be sent outside Cloud.gov for processing.';
                            document.getElementById('providerInfo').after(warning);
                        }
                    }
                });
        }
        
        // Initial load
        loadStatus();
        
        // Handle query form submission
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
        
        // Handle file upload form submission
        document.getElementById('uploadForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const files = document.getElementById('fileInput').files;
            if (files.length === 0) {
                alert('Please select files to upload');
                return;
            }
            
            // Disable the submit button and show loading
            const submitButton = e.target.querySelector('button[type="submit"]');
            submitButton.disabled = true;
            submitButton.textContent = 'Uploading...';
            
            const formData = new FormData();
            for (let i = 0; i < files.length; i++) {
                formData.append('files', files[i]);
            }
            
            try {
                const response = await fetch('/upload-multiple', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                // Display results
                const resultDiv = document.getElementById('uploadResult');
                resultDiv.style.display = 'block';
                
                if (response.ok) {
                    resultDiv.innerHTML = `
                        <h3>Upload Results:</h3>
                        <p class="success">${result.message}</p>
                        <p>Total chunks created: ${result.total_chunks_created}</p>
                        <ul>
                            ${result.results.map(r => {
                                const statusClass = r.status === 'success' ? 'success' : 'skipped';
                                const chunks = r.chunks ? ` (${r.chunks} chunks)` : '';
                                const reason = r.reason ? ` - ${r.reason}` : '';
                                return `<li class="${statusClass}">${r.filename}: ${r.status}${chunks}${reason}</li>`;
                            }).join('')}
                        </ul>
                    `;
                    
                    // Reload status to update document count
                    loadStatus();
                    
                    // Clear the file input
                    document.getElementById('fileInput').value = '';
                } else {
                    resultDiv.innerHTML = `
                        <h3>Upload Failed:</h3>
                        <p class="error">${result.error || 'Unknown error occurred'}</p>
                    `;
                }
            } catch (error) {
                const resultDiv = document.getElementById('uploadResult');
                resultDiv.style.display = 'block';
                resultDiv.innerHTML = `
                    <h3>Upload Failed:</h3>
                    <p class="error">Network error: ${error.message}</p>
                `;
            } finally {
                // Re-enable the submit button
                submitButton.disabled = false;
                submitButton.textContent = 'Upload Files';
            }
        });
    </script>
</body>
</html>
'''


# Add these functions before your routes
def parse_frontmatter(content):
    """Extract frontmatter and content from markdown"""
    pattern = r'^---\s*\n(.*?)\n---\s*\n(.*)$'
    match = re.match(pattern, content, re.DOTALL)
    
    if match:
        try:
            frontmatter = yaml.safe_load(match.group(1))
            markdown_content = match.group(2)
            return frontmatter, markdown_content
        except yaml.YAMLError:
            pass
    
    return {}, content

def split_markdown_by_headers(content, metadata, max_chunk_size=2000):
    """Split markdown content by headers into smaller chunks"""
    documents = []
    lines = content.split('\n')
    current_chunk = []
    current_size = 0
    chunk_num = 1
    
    for line in lines:
        line_size = len(line)
        
        # Check if adding this line would exceed max size
        if current_size + line_size > max_chunk_size and current_chunk:
            # Save current chunk
            chunk_content = '\n'.join(current_chunk)
            chunk_metadata = metadata.copy()
            chunk_metadata['chunk'] = chunk_num
            documents.append({
                'content': chunk_content,
                'metadata': chunk_metadata
            })
            chunk_num += 1
            current_chunk = [line]
            current_size = line_size
        else:
            current_chunk.append(line)
            current_size += line_size
    # Don't forget the last chunk
    if current_chunk:
        chunk_content = '\n'.join(current_chunk)
        chunk_metadata = metadata.copy()
        chunk_metadata['chunk'] = chunk_num
        documents.append({
            'content': chunk_content,
            'metadata': chunk_metadata
        })
    
    return documents


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

# Add these new routes to app.py
@app.route('/upload-file', methods=['POST'])
def upload_file():
    """Upload a single markdown file"""
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        
        if not file.filename.endswith(('.md', '.markdown')):
            return jsonify({"error": "Only markdown files are supported"}), 400
        
        # Read file content
        content = file.read().decode('utf-8')
        filename = secure_filename(file.filename)
        
        # Parse frontmatter if present
        frontmatter, markdown_content = parse_frontmatter(content)
        
        # Build metadata
        metadata = {
            "filename": filename,
            "source": "file_upload",
            **frontmatter
        }
        
        # Split large documents
        documents = split_markdown_by_headers(markdown_content, metadata)
        
        # Add to vector store
        vector_store.add_documents(documents)
        
        return jsonify({
            "message": f"Successfully uploaded {filename}",
            "chunks_created": len(documents),
            "total_documents": vector_store.get_document_count()
        })
        
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/upload-multiple', methods=['POST'])
def upload_multiple_files():
    """Upload multiple markdown files at once"""
    try:
        if 'files' not in request.files:
            return jsonify({"error": "No files provided"}), 400
        
        files = request.files.getlist('files')
        if not files:
            return jsonify({"error": "No files selected"}), 400
        
        results = []
        total_chunks = 0
        
        for file in files:
            if file.filename and file.filename.endswith(('.md', '.markdown')):
                # Process each file
                content = file.read().decode('utf-8')
                filename = secure_filename(file.filename)
                
                # Parse frontmatter
                frontmatter, markdown_content = parse_frontmatter(content)
                
                # Build metadata
                metadata = {
                    "filename": filename,
                    "source": "bulk_upload",
                    **frontmatter
                }
                
                # Split and add documents
                documents = split_markdown_by_headers(markdown_content, metadata)
                vector_store.add_documents(documents)
                
                results.append({
                    "filename": filename,
                    "chunks": len(documents),
                    "status": "success"
                })
                total_chunks += len(documents)
            else:
                results.append({
                    "filename": file.filename,
                    "status": "skipped",
                    "reason": "not a markdown file"
                })
        
        return jsonify({
            "message": f"Processed {len(files)} files",
            "total_chunks_created": total_chunks,
            "results": results,
            "total_documents": vector_store.get_document_count()
        })
        
    except Exception as e:
        logger.error(f"Error uploading multiple files: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/upload-url', methods=['POST'])
def upload_from_url():
    """Upload markdown content from a URL (e.g., GitHub raw content)"""
    try:
        data = request.get_json()
        url = data.get('url')
        
        if not url:
            return jsonify({"error": "No URL provided"}), 400
        
        # Fetch content from URL
        import requests
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        content = response.text
        
        # Extract filename from URL
        filename = url.split('/')[-1] or 'untitled.md'
        
        # Parse frontmatter
        frontmatter, markdown_content = parse_frontmatter(content)
        
        # Build metadata
        metadata = {
            "filename": filename,
            "source_url": url,
            "source": "url_upload",
            **frontmatter
        }
        
        # Split and add documents
        documents = split_markdown_by_headers(markdown_content, metadata)
        vector_store.add_documents(documents)
        
        return jsonify({
            "message": f"Successfully uploaded from {url}",
            "chunks_created": len(documents),
            "total_documents": vector_store.get_document_count()
        })
        
    except requests.RequestException as e:
        return jsonify({"error": f"Failed to fetch URL: {str(e)}"}), 400
    except Exception as e:
        logger.error(f"Error uploading from URL: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)