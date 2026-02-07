"""
Memory storage for commit history using ChromaDB.

This module provides vector storage and semantic search capabilities
for Git commit history.
"""

from typing import Dict, List, Optional
import hashlib
import chromadb
from chromadb.config import Settings
from chromadb.api.types import EmbeddingFunction


class SimpleHashEmbedding(EmbeddingFunction):
    """
    Simple hash-based embedding function for offline use.
    
    Note: This is a basic implementation for demonstration and offline testing.
    For production use, consider using proper embedding models like SentenceTransformers.
    """
    
    def __init__(self):
        """Initialize the embedding function."""
        self.dimension = 384
    
    def __call__(self, input: List[str]) -> List[List[float]]:
        """
        Generate embeddings from input texts.
        
        Args:
            input: List of text strings to embed
            
        Returns:
            List of embedding vectors
        """
        embeddings = []
        for text in input:
            # Create a simple deterministic embedding from hash
            hash_obj = hashlib.sha256(text.encode())
            hash_bytes = hash_obj.digest()
            # Convert to normalized vector of floats
            embedding = [float(b) / 255.0 for b in hash_bytes[:self.dimension]]
            # Pad to required dimensions if needed
            while len(embedding) < self.dimension:
                embedding.append(0.0)
            embeddings.append(embedding)
        return embeddings


class HistorianMemory:
    """
    Vector storage and search for commit history.
    
    Uses ChromaDB to store commit metadata and enable semantic search
    over repository history.
    """
    
    def __init__(self, persist_directory: Optional[str] = None, 
                 embedding_function=None):
        """
        Initialize the HistorianMemory.
        
        Args:
            persist_directory: Directory to persist ChromaDB data (None for in-memory)
            embedding_function: Custom embedding function (None for default simple hash)
        """
        if persist_directory:
            self.client = chromadb.PersistentClient(path=persist_directory)
        else:
            self.client = chromadb.Client()
        
        # Use simple hash embedding if none provided (works offline)
        if embedding_function is None:
            embedding_function = SimpleHashEmbedding()
        
        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name="sentinel-history",
            metadata={"description": "Git commit history for contextual understanding"},
            embedding_function=embedding_function
        )
    
    def ingest_commits(self, commits: List[Dict]) -> None:
        """
        Ingest commits into the vector database.
        
        Args:
            commits: List of commit dictionaries from GitIndexer
        """
        if not commits:
            return
        
        documents = []
        metadatas = []
        ids = []
        
        for commit in commits:
            # Create a searchable document from commit data
            doc_parts = [
                f"Commit: {commit['hash'][:8]}",
                f"Author: {commit['author']}",
                f"Date: {commit['date']}",
                f"Message: {commit['message']}",
            ]
            
            # Add diff information
            if commit.get('diffs'):
                doc_parts.append("Changes:")
                for diff in commit['diffs']:
                    doc_parts.append(f"  - {diff['file_path']} ({diff['change_type']})")
                    if diff.get('diff'):
                        # Include a snippet of the diff
                        diff_lines = diff['diff'].split('\n')[:10]
                        doc_parts.append('\n'.join(diff_lines))
            
            document = '\n'.join(doc_parts)
            documents.append(document)
            
            # Store metadata
            metadata = {
                'hash': commit['hash'],
                'author': commit['author'],
                'author_email': commit.get('author_email', ''),
                'date': commit['date'],
                'message': commit['message'][:500]  # Truncate long messages
            }
            metadatas.append(metadata)
            
            # Use commit hash as ID
            ids.append(commit['hash'])
        
        # Add to collection
        self.collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
    
    def search(self, query: str, n_results: int = 5) -> Dict:
        """
        Perform semantic search over commit history.
        
        Args:
            query: Search query string
            n_results: Number of results to return
            
        Returns:
            Dictionary containing search results with documents, metadatas, and distances
        """
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results
        )
        
        return results
    
    def get_collection_stats(self) -> Dict:
        """
        Get statistics about the collection.
        
        Returns:
            Dictionary with collection statistics
        """
        count = self.collection.count()
        return {
            'total_commits': count,
            'collection_name': self.collection.name
        }
