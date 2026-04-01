#!/usr/bin/env python3
"""Test what gets formatted and passed to the LLM."""

import sys
import os

# Add src to path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from vector import retriever
from main import format_retrieved_context

query = "Give me the telemetry for EVA1"
print(f"Query: {query}\n")

docs = retriever.invoke(query)
formatted = format_retrieved_context(docs)

print(f"Retrieved {len(docs)} documents")
print(f"\nFormatted context passed to LLM:\n")
print("="*80)
print(formatted)
print("="*80)
print(f"\nLength: {len(formatted)} characters")
