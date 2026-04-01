#!/usr/bin/env python3
"""Test what the retriever finds for 'Give me telemetry for EVA1'."""

from src.vector import retriever

query = "Give me the telemetry for EVA1"
print(f"Query: {query}\n")

docs = retriever.invoke(query)
print(f"Retrieved {len(docs)} documents:\n")

for i, doc in enumerate(docs, 1):
    print(f"[{i}] ID: {doc.id}")
    print(f"    Type: {doc.metadata.get('type', 'unknown')}")
    print(f"    Content: {doc.page_content[:150]}...\n")
