#!/usr/bin/env python3
"""Debug what's in the database after rebuild."""

from src.vector import vector_store

# Check what's actually in the database
try:
    all_docs = vector_store.get(include=["documents", "metadatas"])
    print(f"Total documents in database: {len(all_docs['ids'])}\n")
    
    for i, (doc_id, metadata, document) in enumerate(zip(all_docs['ids'], all_docs['metadatas'], all_docs['documents']), 1):
        print(f"[{i}] ID: {doc_id}")
        print(f"    Type: {metadata.get('type', 'unknown')}")
        print(f"    Eva: {metadata.get('eva', 'N/A')}")
        print(f"    Content preview: {document[:100]}...")
        print()
        
except Exception as e:
    print(f"Error checking database: {e}")
    import traceback
    traceback.print_exc()
