"""Configuration settings for the AI clinic application."""

import os
from typing import Optional


class Settings:
    """Application settings."""
    
    # Database
    DATABASE_URL: str = os.environ.get("DATABASE_URL", "sqlite:///./ai_clinic.db")
    
    # OpenAI
    OPENAI_API_KEY: Optional[str] = os.environ.get("OPENAI_API_KEY")
    
    # Server
    HOST: str = os.environ.get("HOST", "0.0.0.0")
    PORT: int = int(os.environ.get("PORT", 8000))
    
    # LangGraph
    LANGGRAPH_API_URL: str = os.environ.get("LANGGRAPH_API_URL", "http://localhost:8123")


settings = Settings() 