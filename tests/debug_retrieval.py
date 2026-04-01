#!/usr/bin/env python3
"""Debug script to test what the retriever returns."""

from src.vector import retriever

# Test queries that should return oxygen data
test_queries = [
    "What is the primary oxygen storage?",
    "How much oxygen is left?",
    "oxygen consumption rate",
    "time until oxygen runs out"
]

for query in test_queries:
    print(f"\n{'='*60}")
    print(f"Query: {query}")
    print('='*60)
    
    docs = retriever.invoke(query)
    print(f"Retrieved {len(docs)} documents:\n")
    
    for i, doc in enumerate(docs, 1):
        print(f"[{i}] Type: {doc.metadata.get('type', 'unknown')}")
        print(f"    ID: {doc.id}")
        print(f"    Content:\n{doc.page_content}\n")
