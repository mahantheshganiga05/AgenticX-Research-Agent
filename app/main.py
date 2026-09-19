"""FastAPI Application for AgenticX Tool-Using Research Agent.

Exposes REST endpoints and serves the research web interface.
"""

import logging
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.config import config
from app.agent.research_agent import ResearchAgent
from app.models.schemas import ResearchRequest, ResearchResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("agenticx.api")

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

app = FastAPI(
    title="AgenticX Tool-Using Research Agent",
    description="Autonomous research agent with hard step limits, claim traceability, and two distinct tools.",
    version="1.0.0",
)

# CORS middleware for development flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
def read_root():
    """Serve the research agent web interface."""
    index_file = TEMPLATES_DIR / "index.html"
    if not index_file.exists():
        return HTMLResponse("<h1>AgenticX Research Agent</h1><p>UI loading error: templates/index.html not found.</p>", status_code=500)
    with open(index_file, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/health")
def health_check():
    """Application health status endpoint."""
    return {
        "status": "healthy",
        "service": "AgenticX Research Agent",
        "max_agent_steps": config.MAX_AGENT_STEPS,
        "model": config.OPENAI_MODEL,
        "openai_configured": bool(config.OPENAI_API_KEY and config.OPENAI_API_KEY != "your_openai_api_key_here"),
        "tavily_configured": bool(config.TAVILY_API_KEY and config.TAVILY_API_KEY != "your_tavily_api_key_here"),
    }


@app.get("/api/example")
def get_example_questions():
    """Return suggested research queries for demonstration."""
    return {
        "examples": [
            "What are the main applications of generative AI in healthcare?",
            "What are the environmental effects of electric vehicles over their lifecycle?",
            "What is the difference between supervised and unsupervised machine learning?",
            "How does quantum key distribution enhance cybersecurity?",
        ]
    }


@app.post("/api/research", response_model=ResearchResponse)
def run_research(request: ResearchRequest):
    """Execute the autonomous research agent on a given research question."""
    logger.info(f"Received research request: '{request.question}'")
    try:
        agent = ResearchAgent()
        state = agent.run(question=request.question, max_steps=request.max_steps)

        return ResearchResponse(
            question=state.question,
            answer=state.final_answer or "No answer could be generated.",
            sources=state.get_source_list(),
            steps_used=state.steps_used,
            max_steps=state.max_steps,
            tool_history=state.tool_history,
            errors=state.errors,
            status=state.status,
        )
    except Exception as e:
        logger.error(f"Error handling research request: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal research agent error: {str(e)}")
