import asyncio
import os
import sys
from pathlib import Path

from agents import (
    Agent,
    Runner,
    SQLiteSession,
    FileSearchTool,
)

from agents.mcp import MCPServerStdio


# --------------------------------------------------
# Configuration
# --------------------------------------------------

PROJECT_DIR = Path(__file__).parent

VECTOR_STORE_ID = os.environ["LOANOPS_VECTOR_STORE_ID"]


# --------------------------------------------------
# Main
# --------------------------------------------------

async def main():

    # Start and connect to our local MCP server
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

        # ------------------------------------------
        # Agent
        # ------------------------------------------

        loan_agent = Agent(
            name="LoanOps MCP Agent",

            instructions="""
            You are an AI assistant for commercial loan servicing.

            You have access to MCP tools containing authoritative
            structured loan information and financial calculations.

            You also have access to file search for unstructured
            loan documents.

            Rules:

            - Never invent loan information.
            - Use the get_loan MCP tool for structured operational
              loan information.
            - Use the calculate_dscr MCP tool when calculating DSCR.
            - Use file search for contractual information such as
              covenants, restrictions, insurance requirements,
              maturity clauses, and other loan document language.
            - Prefer authoritative structured data for current
              operational values.
            - Clearly distinguish calculated values from contractual
              requirements.
            - If sufficient evidence cannot be found, say so.
            """,

            # Regular/hosted tools
            tools=[
                FileSearchTool(
                    vector_store_ids=[VECTOR_STORE_ID],
                    max_num_results=5,
                ),
            ],

            # Tools discovered from MCP
            mcp_servers=[
                loanops_mcp
            ],
        )


        # ------------------------------------------
        # Conversation memory
        # ------------------------------------------

        session = SQLiteSession(
            "loanops_mcp_demo",
            "mcp_conversations.db",
        )


        # ------------------------------------------
        # Chat loop
        # ------------------------------------------

        print("LoanOps MCP Agent")
        print("Type 'quit' to exit.\n")

        while True:

            question = input("You: ")

            if question.lower() == "quit":
                break

            result = await Runner.run(
                loan_agent,
                question,
                session=session,
            )

            print("\nAgent:")
            print(result.final_output)
            print()


if __name__ == "__main__":
    asyncio.run(main())