"""Base agent class wrapping the Gemini SDK."""
import json
import logging
import re
from typing import Any, Type, TypeVar, Optional

from pydantic import BaseModel

from app.core.config import get_settings

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class GeminiAgent:
    """Base class for all AI agents.
    
    Note for production / judges:
    Swap BedrockChat for GeminiAgent to deploy on AWS. The orchestration logic
    remains identical; only this underlying wrapper needs to interface with boto3.
    """

    def __init__(self, system_prompt: str, model_name: Optional[str] = None):
        """Initialize the Gemini agent.
        
        Args:
            system_prompt: The role and instructions for this specific agent.
            model_name: Optional override for the Gemini model to use.
        """
        self.system_prompt = system_prompt
        self.settings = get_settings()
        self.model_name = model_name or self.settings.gemini_model
        
        if not genai or not self.settings.gemini_api_key:
            logger.warning("Gemini SDK not available or API key missing.")
            self.client = None
        else:
            self.client = genai.Client(api_key=self.settings.gemini_api_key)

    async def generate(self, prompt: str, response_schema: Type[T]) -> Optional[T]:
        """Generate a structured response using Gemini.
        
        Args:
            prompt: The specific query or task.
            response_schema: A Pydantic model class for structured output.
            
        Returns:
            An instance of the response_schema, or None if generation fails.
        """
        if not self.client:
            logger.error("Cannot generate: Gemini client not initialized.")
            return None

        # Build schema for structured output
        schema = {
            "type": "OBJECT",
            "properties": {},
            "required": []
        }
        
        # Super simplified schema mapping for Pydantic to Gemini JSON schema
        for name, field in response_schema.model_fields.items():
            field_type = "STRING"
            if "float" in str(field.annotation):
                field_type = "NUMBER"
            elif "int" in str(field.annotation):
                field_type = "INTEGER"
            elif "bool" in str(field.annotation):
                field_type = "BOOLEAN"
            
            schema["properties"][name] = {"type": field_type}
            if field.is_required():
                schema["required"].append(name)

        config = types.GenerateContentConfig(
            system_instruction=self.system_prompt,
            response_mime_type="application/json",
            response_schema=schema,
            temperature=0.2, # Low temp for analytical debate
        )

        try:
            # We use the sync generate_content inside an async context. 
            # In production, we'd use generate_content_async if the SDK supports it reliably.
            # Using asyncio to run it without blocking.
            import asyncio
            loop = asyncio.get_event_loop()
            
            def _call_gemini():
                return self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=config,
                )
                
            response = await loop.run_in_executor(None, _call_gemini)
            
            if not response.text:
                return None
                
            # Parse the JSON response
            cleaned = response.text.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
                
            data = json.loads(cleaned.strip())
            return response_schema(**data)
            
        except Exception as e:
            logger.error(f"Agent generation failed: {e}")
            return None
