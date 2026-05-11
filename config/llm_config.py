import os
from enum import Enum

class LLMProvider(Enum):
    EMBEDDED = "embedded"
    ANTHROPIC = "anthropic"
    OPENAI = "openai"

class LLMConfig:
    def __init__(self):
        self.provider = os.getenv('LLM_PROVIDER', 'embedded').lower()
        self.api_key = os.getenv('LLM_API_KEY')
        
        # Model configurations for different providers
        self.model_configs = {
            LLMProvider.EMBEDDED.value: {
                "model": "google/flan-t5-base",
                "requires_api_key": False
            },
            LLMProvider.ANTHROPIC.value: {
                "model": "claude-3-haiku-20240307",  # Fast and cost-effective
                "requires_api_key": True
            },
            LLMProvider.OPENAI.value: {
                "model": "gpt-3.5-turbo",
                "requires_api_key": True
            }
        }
    
    def validate(self):
        """Validate configuration"""
        if self.provider not in self.model_configs:
            raise ValueError(f"Unknown LLM provider: {self.provider}")
        
        config = self.model_configs[self.provider]
        if config.get('requires_api_key') and not self.api_key:
            raise ValueError(
                f"LLM provider '{self.provider}' requires LLM_API_KEY environment variable. "
                f"Set it using: cf set-env rag-demo LLM_API_KEY <your-key>"
            )
        
        return True
    
    def get_model_name(self):
        """Get the model name for the current provider"""
        return self.model_configs[self.provider]["model"]
    
    def is_embedded(self):
        """Check if using embedded model"""
        return self.provider == LLMProvider.EMBEDDED.value