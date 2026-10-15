"""Application service interfaces."""

from smart_desk.services.chat_service import ChatManager, ChatMessage, ChatService
from smart_desk.services.document_service import DocumentError, DocumentInfo, DocumentService
from smart_desk.services.ollama_service import OllamaError, OllamaService, OllamaStatus

__all__ = [
    "ChatManager",
    "ChatMessage",
    "ChatService",
    "DocumentError",
    "DocumentInfo",
    "DocumentService",
    "OllamaError",
    "OllamaService",
    "OllamaStatus",
]
