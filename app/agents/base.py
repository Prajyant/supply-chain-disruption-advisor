"""Base agent class wrapping the Amazon Bedrock SDK."""
import json
import logging
import re
from typing import Any, Type, TypeVar, Optional

from pydantic import BaseModel

from app.core.config import get_settings

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    boto3 = None
    ClientError = None

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class BedrockAgent:
    """Base class for all AI agents using Amazon Bedrock."""

    def __init__(self, system_prompt: str, model_id: Optional[str] = None):
        """Initialize the Bedrock agent.
        
        Args:
            system_prompt: The role and instructions for this specific agent.
            model_id: Optional override for the Bedrock model to use.
        """
        self.system_prompt = system_prompt
        self.settings = get_settings()
        self.model_id = model_id or self.settings.bedrock_model_id
        
        if not boto3 or not self.settings.aws_access_key_id:
            logger.warning("Bedrock SDK not available or AWS credentials missing.")
            self.client = None
        else:
            try:
                session = boto3.Session(
                    aws_access_key_id=self.settings.aws_access_key_id,
                    aws_secret_access_key=self.settings.aws_secret_access_key,
                    aws_session_token=self.settings.aws_session_token,
                    region_name=self.settings.aws_region,
                )
                self.client = session.client("bedrock-runtime")
            except Exception as e:
                logger.warning(f"Bedrock client init failed: {e}")
                self.client = None

    async def generate(self, prompt: str, response_schema: Type[T]) -> Optional[T]:
        """Generate a structured response using Bedrock.
        
        Args:
            prompt: The specific query or task.
            response_schema: A Pydantic model class for structured output.
            
        Returns:
            An instance of the response_schema, or None if generation fails.
        """
        if not self.client:
            logger.error("Cannot generate: Bedrock client not initialized.")
            return None

        # Build the JSON schema description for the model
        schema_fields = {}
        for name, field in response_schema.model_fields.items():
            field_type = "string"
            if "float" in str(field.annotation):
                field_type = "number"
            elif "int" in str(field.annotation):
                field_type = "integer"
            elif "bool" in str(field.annotation):
                field_type = "boolean"
            schema_fields[name] = field_type

        schema_instruction = (
            "Return ONLY a valid JSON object with these fields: "
            + ", ".join(f'"{k}" ({v})' for k, v in schema_fields.items())
            + ". No markdown, no code fences, no extra text."
        )

        messages = [
            {
                "role": "user",
                "content": [{"text": prompt + "\n\n" + schema_instruction}],
            }
        ]

        try:
            import asyncio
            loop = asyncio.get_event_loop()

            def _call_bedrock():
                return self.client.converse(
                    modelId=self.model_id,
                    messages=messages,
                    system=[{"text": self.system_prompt}],
                    inferenceConfig={"temperature": 0.2, "maxTokens": 4096},
                )

            response = await loop.run_in_executor(None, _call_bedrock)

            output = response.get("output", {})
            message = output.get("message", {})
            content_blocks = message.get("content", [])
            text = ""
            for block in content_blocks:
                if "text" in block:
                    text = block["text"]
                    break

            if not text:
                return None

            # Parse the JSON response
            cleaned = text.strip()
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

