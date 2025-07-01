"""
🏥 AI Medical Assistant - Simplified FastAPI Application

A streamlined medical consultation API powered by LangGraph AI agent.
"""

import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .config.database import engine, Base
from .routers.medical import router as medical_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    # Startup
    print("🚀 Starting AI Medical Assistant...")
    
    # Create database tables
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables created/verified")
    except Exception as e:
        print(f"❌ Database error: {e}")
    
    # Verify OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  Warning: OPENAI_API_KEY not set")
    else:
        print("✅ OpenAI API key configured")
    
    print("🏥 AI Medical Assistant ready!")
    
    yield
    
    # Shutdown
    print("👋 Shutting down AI Medical Assistant...")


# Create FastAPI application
app = FastAPI(
    title="🏥 AI Medical Assistant",
    description="""
    **Intelligent Medical Consultation API**
    
    Powered by advanced LangGraph AI agent for comprehensive symptom collection,
    emergency detection, and medical data analysis.
    
    ### Key Features:
    - 🤖 **Dynamic AI Conversations**: Proactive symptom questioning
    - 🚨 **Emergency Detection**: Real-time critical symptom identification  
    - 📋 **OLDCARTS Data Collection**: Systematic medical documentation
    - 🔄 **Session Management**: Persistent conversation states
    - 📊 **Progress Tracking**: Data completeness monitoring
    
    ### Getting Started:
    1. **Start**: `POST /api/chat` with `user_id` only
    2. **Continue**: `POST /api/chat` with `session_id` and `message`
    3. **Monitor**: Use session endpoints to track progress
    """,
    version="2.0.0",
    contact={
        "name": "AI Medical Team",
        "email": "support@aimedical.com"
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT"
    },
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(medical_router, prefix="/api")


@app.get("/health")
async def health_check():
    """System health check."""
    return {
        "status": "healthy",
        "service": "AI Medical Assistant",
        "version": "2.0.0",
        "langgraph": "enabled"
    }


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    return {
        "error": "Internal server error",
        "detail": str(exc),
        "status_code": 500
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True) 