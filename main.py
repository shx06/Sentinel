"""
Sentinel entry point.

Run the Sentinel CLI::

    python main.py analyze /path/to/repo
    python main.py analyze /path/to/repo --sandbox
"""

from sentinel.cli import main

if __name__ == "__main__":
    main()
