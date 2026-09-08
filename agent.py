import os

from agents import (
    Agent,
    Runner,
    SQLiteSession,
    FileSearchTool,
)

from agents.decorators import tool

VECTOR_STORE_ID = os.environ["LOANOPS_VECTOR_STORE_ID"]


# --------------------------------------------------
# Fake loan database
# --------------------------------------------------

LOANS = {
    "1001": {
        "property": "Riverside Plaza",
        "borrower": "Riverside Holdings LLC",
        "loan_balance": 32_500_000,
        "noi": 1_250_000,
        "annual_debt_service": 1_000_000,
        "maturity_date": "2031-06-01",
    },
    "1002": {
        "property": "Oak Street Apartments",
        "borrower": "Oak Street Properties LLC",
        "loan_balance": 18_750_000,
        "noi": 920_000,
        "annual_debt_service": 800_000,
        "maturity_date": "2029-11-15",
    },
    "1003": {
        "property": "Harbor Center",
        "borrower": "Harbor Commercial LLC",
        "loan_balance": 44_200_000,
        "noi": 2_400_000,
        "annual_debt_service": 1_750_000,
        "maturity_date": "2032-03-30",
    },
}


# --------------------------------------------------
# Tools
# --------------------------------------------------

@tool
def get_loan(loan_id: str) -> dict:
    """Retrieve authoritative structured information about a loan.

    Args:
        loan_id: The unique loan identifier.
    """

    if loan_id not in LOANS:
        return {
            "error": f"Loan {loan_id} was not found."
        }

    return LOANS[loan_id]


@tool
def calculate_dscr(
    noi: float,
    annual_debt_service: float
) -> float:
    """Calculate debt service coverage ratio (DSCR).

    DSCR = net operating income / annual debt service.

    Args:
        noi: Annual net operating income.
        annual_debt_service: Total annual debt service.
    """

    if annual_debt_service == 0:
        raise ValueError("Annual debt service cannot be zero.")

    return round(noi / annual_debt_service, 3)





# --------------------------------------------------
# Agent
# --------------------------------------------------

loan_agent = Agent(
    name="LoanOps Agent",

    instructions="""
    You are an AI assistant for commercial loan servicing.

    Your job is to answer questions using the tools available to you.

    Important rules:

    - Never invent loan information.
    - Use get_loan when authoritative structured loan data is needed.
    - Use calculate_dscr for DSCR calculations instead of calculating it yourself.
    - Use search_documents when information from loan agreements is needed.
    - Clearly distinguish calculated values from contractual requirements.
    - If information cannot be found, say so.
    """,

    tools=[
        get_loan,
        calculate_dscr,

        FileSearchTool(
            vector_store_ids=[VECTOR_STORE_ID],
            max_num_results=5,
        ),
    ],
)


# --------------------------------------------------
# Run agent
# --------------------------------------------------
session = SQLiteSession(
    "loanops_interview_demo",
    "conversations.db"
)
def main():

    print("LoanOps Agent")
    print("Type 'quit' to exit.\n")

    while True:

        question = input("You: ")

        if question.lower() == "quit":
            break

        result = Runner.run_sync(
            loan_agent,
            question,
            session=session
        )

        print("\nAgent:")
        print(result.final_output)
        print()


if __name__ == "__main__":
    main()
