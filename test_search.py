import os
from openai import OpenAI

print("Starting vector search test...")

vector_store_id = os.environ.get("LOANOPS_VECTOR_STORE_ID")

print("Vector store ID:", vector_store_id)

if not vector_store_id:
    raise RuntimeError("LOANOPS_VECTOR_STORE_ID is not set.")

client = OpenAI()

print("Sending search request...")

results = client.vector_stores.search(
    vector_store_id=vector_store_id,
    query="What financial coverage requirement applies to Riverside?",
)

print("Search finished.")
print("Number of results:", len(results.data))

for result in results.data:
    print("\n------------------------")
    print("FILE:", result.filename)
    print("SCORE:", result.score)

    for content in result.content:
        print("TEXT:", content.text)