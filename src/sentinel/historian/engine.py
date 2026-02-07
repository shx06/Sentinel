"""
Contextual Historian orchestrator.

This module provides a high-level API for learning from repository history
and explaining code context.
"""

from typing import Dict, List, Optional
from .indexer import GitIndexer
from .memory import HistorianMemory


class ContextualHistorian:
    """
    High-level facade for the Contextual Historian pillar.
    
    Combines GitIndexer and HistorianMemory to provide a simple API
    for learning from repository history and answering contextual queries.
    """
    
    def __init__(self, repo_path: str, persist_directory: Optional[str] = None):
        """
        Initialize the ContextualHistorian.
        
        Args:
            repo_path: Path to the Git repository
            persist_directory: Directory to persist ChromaDB data (None for in-memory)
        """
        self.repo_path = repo_path
        self.indexer = GitIndexer(repo_path)
        self.memory = HistorianMemory(persist_directory)
    
    def learn_repository(self, max_commits: Optional[int] = None) -> Dict:
        """
        Learn from the repository's commit history.
        
        Extracts commit history and ingests it into vector storage
        for semantic search.
        
        Args:
            max_commits: Maximum number of commits to learn from (None for all)
            
        Returns:
            Dictionary with statistics about the learning process
        """
        # Extract commits
        commits = self.indexer.get_commits(max_count=max_commits)
        
        # Ingest into memory
        self.memory.ingest_commits(commits)
        
        # Return statistics
        stats = self.memory.get_collection_stats()
        stats['commits_processed'] = len(commits)
        
        return stats
    
    def explain_context(self, query: str, n_results: int = 5) -> List[Dict]:
        """
        Explain code context by searching commit history.
        
        Performs semantic search over the commit history to find
        relevant context for the given query.
        
        Args:
            query: Query about code context (e.g., "why was authentication added?")
            n_results: Number of relevant commits to return
            
        Returns:
            List of dictionaries containing relevant commit information
        """
        # Search memory
        results = self.memory.search(query, n_results)
        
        # Format results
        formatted_results = []
        
        if results.get('documents') and len(results['documents']) > 0:
            documents = results['documents'][0]
            metadatas = results.get('metadatas', [[]])[0]
            distances = results.get('distances', [[]])[0]
            
            for i, doc in enumerate(documents):
                result = {
                    'document': doc,
                    'relevance_score': 1 - distances[i] if i < len(distances) else 0,
                }
                
                # Add metadata if available
                if i < len(metadatas):
                    result.update(metadatas[i])
                
                formatted_results.append(result)
        
        return formatted_results
