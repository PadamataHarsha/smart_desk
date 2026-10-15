"""Load supported local documents and calculate useful metadata."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader


class DocumentError(RuntimeError):
	"""Raised when a supported document cannot be read."""


@dataclass(frozen=True)
class DocumentInfo:
	"""Text, extracted pages, and metadata for a PDF or TXT document."""

	path: Path
	text: str
	page_count: int | None
	size_bytes: int
	pages: tuple[str, ...] = ()
	metadata: tuple[tuple[str, str], ...] = ()

	@property
	def name(self) -> str:
		return self.path.name

	@property
	def file_type(self) -> str:
		return self.path.suffix.lstrip(".").upper()

	@property
	def character_count(self) -> int:
		return len(self.text)

	@property
	def word_count(self) -> int:
		return len(self.text.split())

	@property
	def size_label(self) -> str:
		size = float(self.size_bytes)
		for unit in ("B", "KB", "MB", "GB"):
			if size < 1024 or unit == "GB":
				return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
			size /= 1024
		return f"{size:.1f} GB"


class DocumentService:
	"""Read TXT and PDF documents into a consistent text representation."""

	SUPPORTED_EXTENSIONS = {".txt", ".pdf"}

	def load(self, file_path: str | Path) -> DocumentInfo:
		"""Load a supported file, preserving its page count and PDF metadata."""
		path = Path(file_path).expanduser()
		suffix = path.suffix.lower()
		if suffix not in self.SUPPORTED_EXTENSIONS:
			raise DocumentError("Choose a PDF or TXT document.")
		if not path.is_file():
			raise DocumentError(f"The selected file does not exist:\n{path}")

		try:
			if suffix == ".txt":
				try:
					text = path.read_text(encoding="utf-8-sig")
				except UnicodeDecodeError:
					text = path.read_text(encoding="cp1252")
				page_count = None
				pages = (text,)
				metadata: tuple[tuple[str, str], ...] = ()
			else:
				reader = PdfReader(str(path))
				if reader.is_encrypted:
					raise DocumentError("This PDF is password-protected and cannot be read.")
				pages = tuple(page.extract_text() or "" for page in reader.pages)
				text = "\n\n".join(pages)
				page_count = len(pages)
				pdf_info = reader.metadata
				metadata_values = (
					("Title", getattr(pdf_info, "title", None)),
					("Author", getattr(pdf_info, "author", None)),
					("Subject", getattr(pdf_info, "subject", None)),
					("Creator", getattr(pdf_info, "creator", None)),
				)
				metadata = tuple(
					(label, str(value).strip())
					for label, value in metadata_values
					if value and str(value).strip()
				)
			return DocumentInfo(
				path=path,
				text=text,
				page_count=page_count,
				size_bytes=path.stat().st_size,
				pages=pages,
				metadata=metadata,
			)
		except DocumentError:
			raise
		except Exception as exc:
			raise DocumentError(f"Could not read '{path.name}': {exc}") from exc


__all__ = ["DocumentError", "DocumentInfo", "DocumentService"]
