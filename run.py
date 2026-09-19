"""Entrypoint to run the AgenticX Research Agent application."""

import uvicorn
from app.config import config

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 Starting AgenticX Tool-Using Research Agent")
    print(f"📍 Server running at: http://{config.HOST}:{config.PORT}")
    print(f"⚙️ Hard Step Limit: MAX_AGENT_STEPS = {config.MAX_AGENT_STEPS}")
    print(f"🤖 LLM Model: {config.OPENAI_MODEL}")
    print("=" * 60)
    uvicorn.run(
        "app.main:app",
        host=config.HOST,
        port=config.PORT,
        reload=True,
    )
