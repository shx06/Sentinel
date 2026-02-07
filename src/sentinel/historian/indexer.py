"""
Git indexer for extracting repository history.

This module provides functionality to read and parse Git repository commit history,
extracting relevant metadata and code changes for analysis.
"""

from typing import Dict, List, Optional
from datetime import datetime
import git


class GitIndexer:
    """
    Indexes Git repository commit history.

    Uses GitPython to iterate through commits and extract:
    - Commit hash
    - Author
    - Date
    - Commit message
    - Code changes (diffs)
    """

    def __init__(self, repo_path: str):
        """
        Initialize the GitIndexer.

        Args:
            repo_path: Path to the Git repository
        """
        self.repo_path = repo_path
        self.repo = git.Repo(repo_path)

    def get_commits(self, max_count: Optional[int] = None) -> List[Dict]:
        """
        Iterate through repository commit history and extract metadata.

        Args:
            max_count: Maximum number of commits to retrieve (None for all)

        Returns:
            List of dictionaries containing commit information
        """
        commits = []

        # Iterate through commits
        for commit in self.repo.iter_commits(max_count=max_count):
            commit_data = self._extract_commit_data(commit)
            commits.append(commit_data)

        return commits

    def _extract_commit_data(self, commit: git.Commit) -> Dict:
        """
        Extract relevant data from a single commit.

        Args:
            commit: GitPython Commit object

        Returns:
            Dictionary containing commit metadata and changes
        """
        # Extract basic metadata
        commit_data = {
            "hash": commit.hexsha,
            "author": str(commit.author),
            "author_email": commit.author.email,
            "date": datetime.fromtimestamp(commit.committed_date).isoformat(),
            "message": commit.message.strip(),
            "diffs": [],
        }

        # Extract diffs
        try:
            if commit.parents:
                # Compare with parent commit
                parent = commit.parents[0]
                diffs = commit.diff(parent, create_patch=True)

                for diff in diffs:
                    diff_data = {
                        "file_path": diff.b_path if diff.b_path else diff.a_path,
                        "change_type": diff.change_type,
                        "diff": diff.diff.decode("utf-8", errors="replace")
                        if diff.diff
                        else "",
                    }
                    commit_data["diffs"].append(diff_data)
            else:
                # Initial commit - show all files as added
                for item in commit.tree.traverse():
                    if item.type == "blob":
                        diff_data = {
                            "file_path": item.path,
                            "change_type": "A",
                            "diff": f"Added file: {item.path}",
                        }
                        commit_data["diffs"].append(diff_data)
        except Exception as e:
            # If diff extraction fails, just continue without diffs
            commit_data["diffs"] = []
            commit_data["diff_error"] = str(e)

        return commit_data
