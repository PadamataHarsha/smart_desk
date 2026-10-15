"""Conversation state, prompt construction, and export helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class ChatMessage:
	"""One timestamped message in the active conversation."""

	role: str
	content: str
	timestamp: datetime

	@property
	def word_count(self) -> int:
		return len(self.content.split())

	@property
	def character_count(self) -> int:
		return len(self.content)


class ChatManager:
	"""Own conversation state and serialize it for saving or export."""

	def __init__(self) -> None:
		self.messages: list[ChatMessage] = []
		self.conversation_number = 1

	@property
	def word_count(self) -> int:
		return sum(message.word_count for message in self.messages)

	@property
	def character_count(self) -> int:
		return sum(message.character_count for message in self.messages)

	def add_message(self, role: str, content: str) -> ChatMessage:
		if role not in {"user", "assistant"}:
			raise ValueError("Message role must be 'user' or 'assistant'.")
		message = ChatMessage(role, content, datetime.now())
		self.messages.append(message)
		return message

	def clear(self, new_conversation: bool = False) -> None:
		self.messages.clear()
		if new_conversation:
			self.conversation_number += 1

	def build_prompt(self, document_text: str, question: str) -> str:
		history = self.messages[-9:-1]
		history_text = "\n".join(
			f"{message.role.upper()}: {message.content}" for message in history
		)
		return (
			"You are SmartDesk AI, a precise document assistant. Answer using only "
			"the provided document. If the answer is not present, say so clearly. "
			"Do not invent facts.\n\n"
			f"DOCUMENT:\n{document_text[:24000]}\n\n"
			f"CONVERSATION:\n{history_text or '(no earlier messages)'}\n\n"
			f"QUESTION:\n{question}\n\nANSWER:"
		)

	def build_summary_prompt(self, document_text: str) -> str:
		return (
			"Summarize this document in clear, useful bullet points. Include its "
			"central ideas and important details, and do not introduce information "
			"that is not in the document.\n\n"
			f"DOCUMENT:\n{document_text[:24000]}\n\nSUMMARY:"
		)

	def save(self, file_path: str | Path, format_name: str = "text") -> None:
		"""Write the active conversation as readable text or Markdown."""
		if format_name not in {"text", "markdown"}:
			raise ValueError("format_name must be 'text' or 'markdown'.")
		lines = [f"SmartDesk AI - Conversation {self.conversation_number}", ""]
		for message in self.messages:
			role = "You" if message.role == "user" else "AI Assistant"
			timestamp = message.timestamp.strftime("%Y-%m-%d %H:%M")
			lines.extend((f"{role}  |  {timestamp}", message.content, ""))
		if format_name == "markdown":
			lines[0] = f"# {lines[0]}"
			lines = [
				f"## {line}" if line.startswith(("You  |", "AI Assistant  |")) else line
				for line in lines
			]
		Path(file_path).write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


ChatService = ChatManager

__all__ = ["ChatManager", "ChatMessage", "ChatService"]
