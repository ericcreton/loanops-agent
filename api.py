import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

from agents import (
    Agent,
    Runner,
    FileSearchTool,
    SQLiteSession,
)

from agents.mcp import MCPServerStdio


# --------------------------------------------------
# Configuration
# --------------------------------------------------

PROJECT_DIR = Path(__file__).parent

VECTOR_STORE_ID = os.environ["LOANOPS_VECTOR_STORE_ID"]


# --------------------------------------------------
# Request / response models
# --------------------------------------------------

class ChatRequest(BaseModel):
    message: str
    session_id: str = "web_demo"

    @field_validator("message")
    @classmethod
    def validate_message(cls, message: str) -> str:
        if not message.strip():
            raise ValueError("Message must not be empty or whitespace-only.")
        return message


class ChatResponse(BaseModel):
    answer: str


# --------------------------------------------------
# FastAPI lifespan
# --------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):

    # Start our MCP server when FastAPI starts.
    async with MCPServerStdio(
        name="LoanOps MCP Server",

        params={
            "command": sys.executable,
            "args": [
                str(PROJECT_DIR / "mcp_server.py")
            ],
            "cwd": str(PROJECT_DIR),
        },

    ) as loanops_mcp:

        # Build the agent once.
        agent = Agent(
            name="LoanOps Web Agent",

            instructions="""
            You are an AI assistant for commercial loan servicing.

            Rules:

            - Never invent loan information.
            - Use get_loan for authoritative structured loan data.
            - Use calculate_dscr for DSCR calculations.
            - Use file search for contractual loan information.
            - Clearly distinguish current values from contractual
              requirements.
            - If sufficient evidence cannot be found, say so.
            """,

            tools=[
                FileSearchTool(
                    vector_store_ids=[
                        VECTOR_STORE_ID
                    ],
                    max_num_results=5,
                )
            ],

            mcp_servers=[
                loanops_mcp
            ],
        )

        # Store our agent on the FastAPI application.
        app.state.loan_agent = agent

        yield


# --------------------------------------------------
# Create FastAPI app
# --------------------------------------------------

app = FastAPI(
    title="LoanOps API",
    lifespan=lifespan,
)


# --------------------------------------------------
# CORS
# --------------------------------------------------

app.add_middleware(
    CORSMiddleware,

    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],

    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------
# Health endpoint
# --------------------------------------------------

@app.get("/health")
async def health():

    return {
        "status": "ok"
    }


# --------------------------------------------------
# Chat endpoint
# --------------------------------------------------

@app.post(
    "/chat",
    response_model=ChatResponse,
)
async def chat(
    request: ChatRequest,
):

    session = SQLiteSession(
        request.session_id,
        "web_conversations.db",
    )

    result = await Runner.run(
        app.state.loan_agent,
        request.message,
        session=session,
    )

    return ChatResponse(
        answer=str(
            result.final_output
        )
    )
