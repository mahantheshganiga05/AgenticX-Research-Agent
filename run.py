"""Entrypoint to run the AgenticX Research Agent application."""

import sys
import uvicorn
from app.config import config

# Ensure UTF-8 output on Windows consoles
if sys.platform.startswith("win"):
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 Starting AgenticX Tool-Using Research Agent")
    print(f"📍 Server running at: http://{config.HOST}:{config.PORT}")
    print(f"⚙️ Hard Step Limit: MAX_AGENT_STEPS = {config.MAX_AGENT_STEPS}")
    print(f"🤖 LLM Model: {config.GEMINI_MODEL}")
    is_gemini_configured = bool(
        config.GEMINI_API_KEY
        and config.GEMINI_API_KEY not in ("your_gemini_api_key_here", "your_actual_key_here")
    )
    is_tavily_configured = bool(
        config.TAVILY_API_KEY
        and config.TAVILY_API_KEY not in ("your_tavily_api_key_here", "your_actual_key_here")
    )
    print(f"🔑 Gemini API key configured: {is_gemini_configured}")
    print(f"🔑 Tavily API key configured: {is_tavily_configured}")
    print("=" * 60)
    uvicorn.run(
        "app.main:app",
        host=config.HOST,
        port=config.PORT,
        reload=True,
    )
