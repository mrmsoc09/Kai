"""
Language handler registry.
"""
from .base import BaseLanguageHandler, ExecutionResult, LanguageContext
from .python import PythonHandler
from .bash import BashHandler
from .go import GoHandler
from ..models import ScriptLanguage


HANDLERS = {
    ScriptLanguage.PYTHON: PythonHandler,
    ScriptLanguage.BASH: BashHandler,
    ScriptLanguage.GO: GoHandler
}


def get_handler(language: ScriptLanguage, config: dict = None) -> BaseLanguageHandler:
    """Get appropriate handler for language."""
    handler_class = HANDLERS.get(language)
    if not handler_class:
        raise ValueError(f"No handler available for language: {language}")
    return handler_class(config)
