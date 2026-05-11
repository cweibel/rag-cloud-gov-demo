# RAG Demo on Cloud.gov

This demonstration application showcases Retrieval-Augmented Generation (RAG) using Cloud.gov's PostgreSQL service with pgvector extension and open-source language models.

## Features

- ✅ Vector similarity search using pgvector
- ✅ Open-source embeddings (Sentence Transformers)
- ✅ Open-source language model (Flan-T5)
- ✅ No external API dependencies by default
- ✅ Optional external LLM support (Anthropic, OpenAI)
- ✅ Runs entirely on Cloud.gov

## Prerequisites

- Cloud.gov account with access to `aws-rds` service
- Cloud Foundry CLI installed
- Python 3.11+ (for local development)

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│   Browser   │────▶│  Flask App   │────▶│  PostgreSQL     │
└─────────────┘     └──────────────┘     │  + pgvector     │
                            │            └─────────────────┘
                            ▼
                    ┌──────────────┐
                    │ LLM Provider │
                    │ - Embedded   │
                    │ - Anthropic  │
                    │ - OpenAI     │
                    └──────────────┘
```

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/rag-cloud-gov-demo
cd rag-cloud-gov-demo
```

### 2. Create the PostgreSQL Service

```bash
cf create-service aws-rds micro-psql my-rag-db
```

Wait for the service to provision (this may take 5-10 minutes):

```bash
cf services
```

### 3. Deploy the Application

```bash
cf push
```

The first deployment may take 10-15 minutes as it downloads the ML models.

### 4. Load Sample Data

```bash
# Using the provided sample data
curl -X POST https://rag-demo.app.cloud.gov/upload \
  -H "Content-Type: application/json" \
  -d @data/sample_documents.json
```

### 5. Test the Application

Visit `https://rag-demo.app.cloud.gov` in your browser or use curl:

```bash
# Query the system
curl -X POST https://rag-demo.app.cloud.gov/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is Cloud.gov?"}'

# Check status
curl https://rag-demo.app.cloud.gov/status
```

## Configuration Options

### Using Embedded Model (Default - Secure)
No configuration needed. The application will use the embedded Flan-T5 model by default. All data stays within Cloud.gov.

### Using External LLM Providers

⚠️ **Warning**: When using external providers, your data (questions and retrieved documents) will be sent outside Cloud.gov to the provider's API.

#### Anthropic Claude
```bash
cf set-env rag-demo LLM_PROVIDER anthropic
cf set-env rag-demo LLM_API_KEY your-anthropic-api-key
cf restage rag-demo
```

#### OpenAI
```bash
cf set-env rag-demo LLM_PROVIDER openai
cf set-env rag-demo LLM_API_KEY your-openai-api-key
cf restage rag-demo
```

### Switching Back to Embedded Model
```bash
cf unset-env rag-demo LLM_PROVIDER
cf unset-env rag-demo LLM_API_KEY
cf restage rag-demo
```

## API Endpoints

### GET /
Web interface for testing the RAG system

### GET /status
Returns application health and document count

### POST /upload
Upload documents to the vector store

Request body:
```json
{
  "documents": [
    {
      "content": "Document text here",
      "metadata": {
        "source": "optional source",
        "category": "optional category"
      }
    } 
 ]
}
```

### POST /query
Query the RAG system

Request body:
```json
{
  "question": "Your question here"
}
```

Response:
```json
{
  "answer": "Generated answer",
  "sources": [
    {
      "content": "Relevant document content",
      "metadata": {...},
      "similarity": 0.95
    }
  ],
  "model": "google/flan-t5-base",
  "provider": "embedded"
}
```

### POST /clear
Remove all documents from the vector store

### GET /config
Get current LLM configuration (for debugging)

## Security Considerations

### Data Privacy by Provider

| Provider | Data Location | Suitable for CUI | Notes |
|----------|--------------|------------------|-------|
| Embedded | Cloud.gov only | Yes* | All processing happens locally |
| Anthropic | External API | No | Data sent to Anthropic servers |
| OpenAI | External API | No | Data sent to OpenAI servers |

\* Follow your agency's policies for CUI handling

### Best Practices

1. **Default to Embedded**: Always start with the embedded model unless you specifically need external capabilities
2. **Audit External Usage**: When using external providers, log and audit all queries
3. **Separate Environments**: Use different Cloud.gov spaces for testing external providers
4. **API Key Management**: Never commit API keys to code; always use environment variables

## Local Development

1. Install PostgreSQL with pgvector locally
2. Set environment variables:
   ```bash
   export VCAP_SERVICES='{"aws-rds":[{"credentials":{"host":"localhost","port":5432,"username":"postgres","password":"password","db_name":"ragdemo"}}]}'
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the application:
   ```bash
   python app.py
   ```

## Memory and Performance

- The application requires 2GB of memory to run the language model
- First request after deployment will be slow as models are loaded
- Subsequent requests should respond in 2-5 seconds
- Vector search is optimized with IVFFlat indexing

### Performance Comparison

| Provider | Response Time | Quality | Cost |
|----------|--------------|---------|------|
| Embedded | 2-5 seconds | Good for basic Q&A | Free |
| Claude Haiku | <1 second | Excellent | ~$0.25/million tokens |
| GPT-3.5 | <1 second | Very Good | ~$0.50/million tokens |

## Customization

### Using Different Models

To use a different embedding model, modify `services/embeddings.py`:
```python
self.model = SentenceTransformer('your-model-name')
```

To use a different language model, modify `services/rag_chain.py`:
```python
self.generator = pipeline(
    "text2text-generation",
    model="your-model-name"
)
```

### Adjusting Vector Search

Modify the number of documents retrieved in `services/rag_chain.py`:
```python
relevant_docs = self.vector_store.search(question, k=5)  # Retrieve top 5
```

## Troubleshooting

### Out of Memory Errors
- Ensure your manifest.yml specifies at least 2GB memory
- Consider using smaller models (e.g., flan-t5-small instead of base)

### Slow First Request
- This is normal - models are being loaded into memory
- Subsequent requests will be much faster

### Database Connection Errors
- Ensure the RDS service is fully provisioned: `cf services`
- Check logs: `cf logs rag-demo --recent`

### External LLM Issues
- Verify API key is set correctly: `cf env rag-demo`
- Check provider status pages for outages
- Review logs for specific error messages

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This project is in the public domain within the United States.

## Acknowledgments

- Cloud.gov team for the excellent PaaS platform
- Hugging Face for open-source models
- pgvector team for the PostgreSQL extension
- Anthropic and OpenAI for their APIs (when used)
```
