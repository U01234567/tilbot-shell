"""Phase 3, questions: the participant asks, the knowledge base answers.

The knowledge base is project/knowledge.xlsx (config/project.py reads it). matching.py finds the entry
whose question or phrasing means most nearly the same, through vector-similarity-intent; the bridge's
/bridge/ask gives Tilbot the answer, word for word from the file.
"""
