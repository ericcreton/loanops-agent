from mcp.server import MCPServer


mcp = MCPServer("LoanOps Tools")


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


@mcp.tool()
def get_loan(loan_id: str) -> dict:
    """Retrieve authoritative structured information for a loan."""

    if loan_id not in LOANS:
        return {
            "status": "not_found",
            "loan_id": loan_id,
            "data": None,
        }

    return {
        "status": "success",
        "loan_id": loan_id,
        "data": LOANS[loan_id],
    }


@mcp.tool()
def calculate_dscr(
    noi: float,
    annual_debt_service: float,
) -> dict:
    """Calculate Debt Service Coverage Ratio."""

    if annual_debt_service == 0:
        return {
            "status": "error",
            "message": "Annual debt service cannot be zero.",
        }

    return {
        "status": "success",
        "dscr": round(noi / annual_debt_service, 3),
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")