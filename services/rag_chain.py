import logging
from transformers import pipeline
import torch
from config.llm_config import LLMConfig, LLMProvider

logger = logging.getLogger(__name__)

class RAGChain:
    def __init__(self, vector_store):
        self.vector_store = vector_store
        self.llm_config = LLMConfig()
        
        # Validate configuration
        self.llm_config.validate()
        
        # Initialize the appropriate LLM
        self._initialize_llm()
        
        logger.info(f"RAG Chain initialized with provider: {self.llm_config.provider}")
    
    def _initialize_llm(self):
        """Initialize the LLM based on the configured provider"""
        if self.llm_config.provider == LLMProvider.EMBEDDED.value:
            self._init_embedded_llm()
        elif self.llm_config.provider == LLMProvider.ANTHROPIC.value:
            self._init_anthropic()
        elif self.llm_config.provider == LLMProvider.OPENAI.value:
            self._init_openai()
    
    def _init_embedded_llm(self):
        """Initialize embedded Flan-T5 model"""
        logger.info("Loading embedded language model... This may take a few minutes on first run.")
        self.generator = pipeline(
            "text2text-generation",
            model=self.llm_config.get_model_name(),
            device=-1  # CPU only for Cloud.gov
        )
        logger.info("Embedded language model loaded successfully")
    
    def _init_anthropic(self):
        """Initialize Anthropic Claude client"""
        from anthropic import Anthropic
        self.client = Anthropic(api_key=self.llm_config.api_key)
        logger.info("Anthropic Claude client initialized")
    
    def _init_openai(self):
        """Initialize OpenAI client"""
        from openai import OpenAI
        self.client = OpenAI(api_key=self.llm_config.api_key)
        logger.info("OpenAI client initialized")
    
    def query(self, question, k=3):
        """Answer a question using RAG"""
        # Retrieve relevant documents
        relevant_docs = self.vector_store.search(question, k=k)
        
        if not relevant_docs:
            return {
                "answer": "I couldn't find any relevant information to answer your question.",
                "sources": [],
                "model": self.llm_config.get_model_name(),
                "provider": self.llm_config.provider
            }
        
        # Build context from retrieved documents
        context = self._build_context(relevant_docs)
        
        # Generate answer based on provider
        if self.llm_config.provider == LLMProvider.EMBEDDED.value:
            answer = self._generate_embedded(question, context)
        elif self.llm_config.provider == LLMProvider.ANTHROPIC.value:
            answer = self._generate_anthropic(question, context)
        elif self.llm_config.provider == LLMProvider.OPENAI.value:
            answer = self._generate_openai(question, context)
        
        return {
            "answer": answer,
            "sources": [
                {
                    "content": doc['content'],
                    "metadata": doc['metadata'],
                    "similarity": round(doc['similarity'], 3)
                }
                for doc in relevant_docs
            ],
            "model": self.llm_config.get_model_name(),
            "provider": self.llm_config.provider
        }
    
    def _build_context(self, docs):
        """Build context string from documents"""
        context_parts = []
        for i, doc in enumerate(docs):
            context_parts.append(f"Document {i+1}: {doc['content']}")
        return "\n\n".join(context_parts)
    
    def _generate_embedded(self, question, context):
        """Generate answer using embedded model"""
        prompt = f"""Answer the question based on the following context. If the answer cannot be found in the context, say "I don't have enough information to answer that."

Context:
{context}

Question: {question}

Answer:"""
        
        response = self.generator(
            prompt,
            max_length=150,
            min_length=10,
            temperature=0.7,
            do_sample=True
        )
        
        return response[0]['generated_text'].strip()
    
    def _generate_anthropic(self, question, context):
        """Generate answer using Anthropic Claude"""
        prompt = f"""Based on the following context, please answer the question. If the answer cannot be found in the context, say "I don't have enough information to answer that."

Context:
{context}

Question: {question}"""
        
        message = self.client.messages.create(
            model=self.llm_config.get_model_name(),
            max_tokens=300,
            temperature=0.7,
            system="You are a helpful assistant that answers questions based solely on the provided context.",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        return message.content[0].text
    
    def _generate_openai(self, question, context):
        """Generate answer using OpenAI"""
        prompt = f"""Based on the following context, answer the question. If the answer cannot be found in the context, say "I don't have enough information to answer that."

Context:
{context}

Question: {question}"""
        
        response = self.client.chat.completions.create(
            model=self.llm_config.get_model_name(),
            messages=[
                {
                    "role": "system", 
                    "content": "You are a helpful assistant that answers questions based solely on the provided context."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=300
        )
        
        return response.choices[0].message.content