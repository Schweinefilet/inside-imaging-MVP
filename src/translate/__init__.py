"""Patient-friendly translation package.

Re-exports the public surface used by callers (Glossary, build_structured).
LAY_GLOSS is a module-level cache that app.py populates at startup; integration
code may read it as `from src.translate import LAY_GLOSS`.
"""

from src.translate.glossary import Glossary
from src.translate.pipeline import build_structured

# Mutable module-level glossary populated by app.py on startup; None until then.
LAY_GLOSS = None

__all__ = ["Glossary", "build_structured", "LAY_GLOSS"]
