from pathlib import Path
from openai import OpenAI


client = OpenAI()

DOCUMENT_DIR = Path("documents")


# Create vector store
vector_store = client.vector_stores.create(
    name="LoanOps Loan Documents"
)

print(f"Created vector store: {vector_store.id}")


# Find our document files
files = [
    open(path, "rb")
    for path in DOCUMENT_DIR.glob("*.txt")
]


# Upload them and wait until indexing completes
batch = client.vector_stores.file_batches.upload_and_poll(
    vector_store_id=vector_store.id,
    files=files,
)


print("Document ingestion finished.")
print(f"Status: {batch.status}")

print("\nSAVE THIS VECTOR STORE ID:")
print(vector_store.id)