"""Finding source material for a question.

The strongest questions start from a real repository: the model has never seen
that code, so the question resists being answered from the brief alone.
"""

from .repos import Repo, find

__all__ = ["Repo", "find"]
