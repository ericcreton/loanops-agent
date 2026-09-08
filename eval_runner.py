import asyncio
import json
import os
import sys
from pathlib import Path

from pydantic import BaseModel

from agents import (
    Agent,
    Runner,
    FileSearchTool,
    RunConfig,
)

from agents.items import ToolCallItem
from agents.mcp import MCPServerStdio


# --------------------------------------------------
# Configuration
# --------------------------------------------------

PROJECT_DIR = Path(__file__).parent

VECTOR_STORE_ID = os.environ["LOANOPS_VECTOR_STORE_ID"]


# --------------------------------------------------
# Judge output structure
# --------------------------------------------------

class JudgeResult(BaseModel):
    pass_eval: bool
    score: int
    reason: str


# --------------------------------------------------
# LLM Judge Agent
# --------------------------------------------------

judge_agent = Agent(
    name="LoanOps Eval Judge",

    instructions="""
    You are evaluating the quality of an AI assistant for
    commercial loan servicing.

    Evaluate the assistant response ONLY against the supplied
    question and rubric.

    Score the answer from 1 to 5:

    5 = fully correct and satisfies the rubric
    4 = correct with a minor omission
    3 = partially correct but materially incomplete
    2 = substantial errors
    1 = incorrect or unsupported

    Set pass_eval to true only for scores of 4 or 5.

    Do not give credit merely because an answer sounds plausible.

    Pay close attention to:
    - numerical values
    - unsupported claims
    - whether the answer actually satisfies the rubric
    """,

    output_type=JudgeResult,
)


# --------------------------------------------------
# Normalize text
# --------------------------------------------------

def normalize_text(text):

    return (
        str(text)
        .lower()
        .replace("’", "'")
        .replace("‘", "'")
        .strip()
    )


# --------------------------------------------------
# Deterministic answer grader
# --------------------------------------------------

def answer_matches(
    answer,
    expected_values,
):

    answer = normalize_text(answer)

    return any(
        normalize_text(expected) in answer
        for expected in expected_values
    )


# --------------------------------------------------
# Extract tool name
# --------------------------------------------------

def get_tool_name(item):

    raw = item.raw_item

    # Raw item may sometimes behave like a dictionary
    if isinstance(raw, dict):

        return (
            raw.get("name")
            or raw.get("type")
        )

    # Function / MCP calls may expose a name
    name = getattr(
        raw,
        "name",
        None,
    )

    if name:
        return name

    # Hosted tools such as file search may expose a type
    return getattr(
        raw,
        "type",
        None,
    )


# --------------------------------------------------
# Extract tool arguments
# --------------------------------------------------

def get_tool_arguments(item):

    raw = item.raw_item

    if isinstance(raw, dict):

        arguments = raw.get(
            "arguments"
        )

    else:

        arguments = getattr(
            raw,
            "arguments",
            None,
        )

    if arguments is None:
        return None

    # Function arguments are commonly stored
    # as a JSON string.
    if isinstance(
        arguments,
        str,
    ):

        try:

            return json.loads(
                arguments
            )

        except json.JSONDecodeError:

            return arguments

    return arguments
def tool_arguments_match(
    tool_calls,
    expected_tool_arguments,
):

    for tool_name, expected_args in expected_tool_arguments.items():

        matching_calls = [
            call
            for call in tool_calls
            if call["name"] == tool_name
        ]

        if not matching_calls:
            return False

        found_match = False

        for call in matching_calls:

            actual_args = call["arguments"]

            if not isinstance(actual_args, dict):
                continue

            arguments_match = all(
                actual_args.get(key) == value
                for key, value in expected_args.items()
            )

            if arguments_match:
                found_match = True
                break

        if not found_match:
            return False

    return True

# --------------------------------------------------
# Run LLM judge
# --------------------------------------------------

async def run_llm_judge(
    question,
    answer,
    rubric,
):

    judge_input = f"""
QUESTION:
{question}

RUBRIC:
{rubric}

ASSISTANT ANSWER:
{answer}

Evaluate the assistant answer.
"""

    result = await Runner.run(
        judge_agent,
        judge_input,
    )

    return result.final_output


# --------------------------------------------------
# Main eval harness
# --------------------------------------------------

async def main():

    # --------------------------------------------------
    # Load golden eval dataset
    # --------------------------------------------------

    with open(
        PROJECT_DIR / "eval_cases.json"
    ) as file:

        eval_cases = json.load(
            file
        )


    # --------------------------------------------------
    # Start LoanOps MCP server
    # --------------------------------------------------

    async with MCPServerStdio(
        name="LoanOps MCP Server",

        params={
            "command": sys.executable,

            "args": [
                str(
                    PROJECT_DIR
                    / "mcp_server.py"
                )
            ],

            "cwd": str(
                PROJECT_DIR
            ),
        },

    ) as loanops_mcp:


        # --------------------------------------------------
        # Agent being evaluated
        # --------------------------------------------------

        agent = Agent(
            name="LoanOps Eval Agent",

            instructions="""
            You are an AI assistant for commercial loan servicing.

            Rules:

            - Never invent loan information.

            - Use get_loan for authoritative structured
              operational loan data.

            - Use calculate_dscr for DSCR calculations.

            - Use file search for contractual information
              contained in loan documents.

            - Clearly distinguish current calculated values
              from contractual requirements.

            - If sufficient evidence cannot be found,
              clearly say so.
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


        passed = 0


        # --------------------------------------------------
        # Run each eval case
        # --------------------------------------------------

        for case in eval_cases:

            print(
                "\n================================"
            )

            print(
                "TEST:",
                case["id"]
            )

            print(
                "QUESTION:",
                case["question"]
            )


            # --------------------------------------------------
            # Run the LoanOps agent
            # --------------------------------------------------

            result = await Runner.run(
                agent,
                case["question"],

                run_config=RunConfig(
                    workflow_name=(
                        "LoanOps Eval Harness"
                    ),

                    trace_metadata={
                        "eval_case":
                        case["id"]
                    },
                ),
            )


            # --------------------------------------------------
            # Get final answer
            # --------------------------------------------------

            answer = str(
                result.final_output
            )


            # --------------------------------------------------
            # Extract agent trajectory
            # --------------------------------------------------

            tool_calls = []

            for item in result.new_items:

                if isinstance(
                    item,
                    ToolCallItem,
                ):

                    tool_name = get_tool_name(
                        item
                    )

                    if tool_name:

                        tool_calls.append(
                            {
                                "name":
                                tool_name,

                                "arguments":
                                get_tool_arguments(
                                    item
                                ),
                            }
                        )


            # --------------------------------------------------
            # Create simple list of tool names
            # --------------------------------------------------

            tool_names = [
                call["name"]
                for call in tool_calls
            ]


            # --------------------------------------------------
            # Deterministic answer grading
            # --------------------------------------------------

            answer_pass = answer_matches(
                answer,
                case["expected_any"],
            )


            # --------------------------------------------------
            # Required tool grading
            # --------------------------------------------------

            required_tools_pass = all(
                tool in tool_names

                for tool
                in case["required_tools"]
            )


            # --------------------------------------------------
            # Forbidden tool grading
            # --------------------------------------------------

            forbidden_tools_pass = all(
                tool not in tool_names

                for tool
                in case["forbidden_tools"]
            )


            # --------------------------------------------------
            # Maximum tool-call grading
            # --------------------------------------------------

            tool_count_pass = (
                len(tool_calls)
                <= case["max_tool_calls"]
            )


            # --------------------------------------------------
            # Combined trajectory grade
            # --------------------------------------------------
            tool_arguments_pass = tool_arguments_match(
                tool_calls,
                case["expected_tool_arguments"],
            )
            trajectory_pass = (
                required_tools_pass
                and forbidden_tools_pass
                and tool_count_pass
                and tool_arguments_pass
            )


            # --------------------------------------------------
            # Run LLM-as-a-judge
            # --------------------------------------------------

            judgment = await run_llm_judge(
                question=case["question"],
                answer=answer,
                rubric=case["rubric"],
            )


            # --------------------------------------------------
            # Overall test result
            # --------------------------------------------------

            test_pass = (
                answer_pass
                and trajectory_pass
                and judgment.pass_eval
            )


            # --------------------------------------------------
            # Print answer
            # --------------------------------------------------

            print(
                "\nANSWER:"
            )

            print(
                answer
            )


            # --------------------------------------------------
            # Print tool calls + arguments
            # --------------------------------------------------

            print(
                "\nTOOL CALLS:"
            )

            if tool_calls:

                for call in tool_calls:

                    print(
                        f"- {call['name']}"
                    )

                    print(
                        "  Arguments:",
                        call["arguments"]
                    )

            else:

                print(
                    "No tools called."
                )


            # --------------------------------------------------
            # Print deterministic grader
            # --------------------------------------------------

            print(
                "\nDETERMINISTIC ANSWER:"
            )

            print(
                "PASS"
                if answer_pass
                else "FAIL"
            )


            # --------------------------------------------------
            # Print trajectory grader
            # --------------------------------------------------

            print(
                "\nTRAJECTORY:"
            )

            print(
                "Required tools:",
                (
                    "PASS"
                    if required_tools_pass
                    else "FAIL"
                )
            )

            print(
                "Forbidden tools:",
                (
                    "PASS"
                    if forbidden_tools_pass
                    else "FAIL"
                )
            )

            print(
                "Tool count:",
                (
                    "PASS"
                    if tool_count_pass
                    else "FAIL"
                )
            )
            print(
                "Tool arguments:",
                (
                     "PASS"
                    if tool_arguments_pass
                    else "FAIL"
                )
            )

            # --------------------------------------------------
            # Print LLM judge
            # --------------------------------------------------

            print(
                "\nLLM JUDGE:"
            )

            print(
                "Score:",
                judgment.score
            )

            print(
                "Pass:",
                judgment.pass_eval
            )

            print(
                "Reason:",
                judgment.reason
            )


            # --------------------------------------------------
            # Print overall result
            # --------------------------------------------------

            print(
                "\nRESULT:"
            )

            if test_pass:

                print(
                    "PASS"
                )

                passed += 1

            else:

                print(
                    "FAIL"
                )


        # --------------------------------------------------
        # Final report
        # --------------------------------------------------

        total = len(
            eval_cases
        )

        print(
            "\n================================"
        )

        print(
            "FINAL RESULTS"
        )

        print(
            "================================"
        )

        print(
            f"Passed: "
            f"{passed}/{total}"
        )

        print(
            f"Score: "
            f"{(passed / total) * 100:.1f}%"
        )


# --------------------------------------------------
# Start program
# --------------------------------------------------

if __name__ == "__main__":

    asyncio.run(
        main()
    )