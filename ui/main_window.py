"""Tkinter user interface for SmartDesk AI."""

from __future__ import annotations

import logging
import queue
import tkinter as tk
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from tkinter import filedialog
from typing import Any, Callable

import ttkbootstrap as tb

from smart_desk.services.chat_service import ChatManager, ChatMessage
from smart_desk.services.document_service import DocumentInfo, DocumentService
from smart_desk.services.ollama_service import DEFAULT_MODEL, OllamaService, OllamaStatus
from smart_desk.ui.components import Toast, Tooltip, create_button
from smart_desk.ui.dialogs import confirm, show_error, show_info, show_warning
from smart_desk.ui.styles import (
	APP_NAME,
	COLOR_ACCENT,
	COLOR_AMBER,
	COLOR_ASSISTANT,
	COLOR_BG,
	COLOR_BORDER,
	COLOR_GREEN,
	COLOR_MUTED,
	COLOR_PANEL,
	COLOR_PANEL_LIGHT,
	COLOR_RED,
	COLOR_SIDEBAR,
	COLOR_TEXT,
	COLOR_USER,
	DOCUMENT_FONT_FAMILY,
	EVENT_POLL_INTERVAL_MS,
	FONT_FAMILY,
	MIN_WINDOW_SIZE,
	PREVIEW_CHARACTER_LIMIT,
	STATUS_CHECK_INTERVAL_MS,
	WINDOW_SIZE,
	WINDOW_TITLE,
	configure_styles,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPORT_DIRECTORY = PROJECT_ROOT / "exports"


def _configure_logging() -> logging.Logger:
	log_directory = PROJECT_ROOT / "logs"
	try:
		log_directory.mkdir(parents=True, exist_ok=True)
		handler: logging.Handler = RotatingFileHandler(
			log_directory / "smartdesk_ai.log",
			maxBytes=1_000_000,
			backupCount=3,
			encoding="utf-8",
		)
	except OSError:
		handler = logging.StreamHandler()
	logging.basicConfig(
		level=logging.INFO,
		format="%(asctime)s %(levelname)s %(name)s: %(message)s",
		handlers=[handler],
		force=True,
	)
	return logging.getLogger("smartdesk")


class SmartDeskApp:
	"""Coordinate the desktop UI and its document, chat, and Ollama services."""

	def __init__(self) -> None:
		self.logger = _configure_logging()
		self.root = tb.Window(themename="darkly")
		self.root.title(WINDOW_TITLE)
		self.root.geometry(WINDOW_SIZE)
		self.root.minsize(*MIN_WINDOW_SIZE)
		self.root.configure(bg=COLOR_BG)
		configure_styles(tb.Style())
		try:
			EXPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)
		except OSError as exc:
			self.logger.warning("Could not create default export directory: %s", exc)

		self.document_service = DocumentService()
		self.ollama_service = OllamaService(model=DEFAULT_MODEL)
		self.chat_manager = ChatManager()
		self.document: DocumentInfo | None = None
		self.ollama_status: OllamaStatus | None = None
		self.executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="smartdesk")
		self.ui_events: queue.Queue[tuple[str, bool, Any]] = queue.Queue()
		self.status_check_pending = False
		self.is_busy = False
		self.activity_items: list[tuple[str, str]] = []
		self.message_labels: list[tk.Label] = []
		self.preview_page_index = 0
		self.preview_font_size = 11

		self._build_layout()
		self._update_conversation_stats()
		self._set_status("Checking Ollama…", COLOR_AMBER)
		self.root.protocol("WM_DELETE_WINDOW", self._close)
		self.root.after(EVENT_POLL_INTERVAL_MS, self._poll_events)
		self._request_status_check()
		self.root.after(STATUS_CHECK_INTERVAL_MS, self._schedule_status_check)

	def run(self) -> None:
		"""Start Tkinter's main event loop."""
		self.root.mainloop()

	def _build_layout(self) -> None:
		self.root.grid_rowconfigure(0, weight=1)
		self.root.grid_columnconfigure(1, weight=1)

		self.sidebar = tk.Frame(self.root, bg=COLOR_SIDEBAR, width=292)
		self.sidebar.grid(row=0, column=0, sticky="nsw")
		self.sidebar.grid_propagate(False)
		self.main = tk.Frame(self.root, bg=COLOR_BG)
		self.main.grid(row=0, column=1, sticky="nsew")
		self.main.grid_rowconfigure(1, weight=1)
		self.main.grid_columnconfigure(0, weight=1)

		self._build_sidebar()
		self._build_main_area()

	def _build_sidebar(self) -> None:
		header = tk.Frame(self.sidebar, bg=COLOR_SIDEBAR)
		header.pack(fill="x", padx=20, pady=(22, 20))
		mark = tk.Label(
			header,
			text="S",
			bg=COLOR_ACCENT,
			fg="#10221F",
			font=(FONT_FAMILY, 16, "bold"),
			width=2,
			height=1,
			padx=5,
			pady=4,
		)
		mark.pack(side="left")
		title_frame = tk.Frame(header, bg=COLOR_SIDEBAR)
		title_frame.pack(side="left", padx=10)
		tk.Label(
			title_frame,
			text="SmartDesk AI",
			bg=COLOR_SIDEBAR,
			fg=COLOR_TEXT,
			font=(FONT_FAMILY, 15, "bold"),
		).pack(anchor="w")
		tk.Label(
			title_frame,
			text="LOCAL FILE ASSISTANT",
			bg=COLOR_SIDEBAR,
			fg=COLOR_MUTED,
			font=(FONT_FAMILY, 8, "bold"),
		).pack(anchor="w", pady=(2, 0))

		self._button(
			self.sidebar,
			"＋   New chat",
			self.new_chat,
			"success",
			"Start a fresh conversation; the selected document stays loaded.",
		).pack(fill="x", padx=18, pady=(0, 16), ipady=4)

		self._section_label(self.sidebar, "CURRENT DOCUMENT")
		self.document_card = tk.Frame(
			self.sidebar,
			bg=COLOR_PANEL,
			highlightthickness=1,
			highlightbackground=COLOR_BORDER,
		)
		self.document_card.pack(fill="x", padx=14, pady=(7, 14))
		self.document_name_label = tk.Label(
			self.document_card,
			text="No document selected",
			bg=COLOR_PANEL,
			fg=COLOR_TEXT,
			font=(FONT_FAMILY, 10, "bold"),
			justify="left",
			anchor="w",
			wraplength=230,
		)
		self.document_name_label.pack(fill="x", padx=13, pady=(12, 3))
		self.document_path_label = tk.Label(
			self.document_card,
			text="Open a PDF or TXT file to begin",
			bg=COLOR_PANEL,
			fg=COLOR_MUTED,
			font=(FONT_FAMILY, 9),
			justify="left",
			anchor="w",
			wraplength=230,
		)
		self.document_path_label.pack(fill="x", padx=13, pady=(0, 10))
		self.document_stats_label = tk.Label(
			self.document_card,
			text="Type  —     Size  —\nWords  —     Characters  —\nPages  —",
			bg=COLOR_PANEL,
			fg="#C4CDD1",
			font=(FONT_FAMILY, 9),
			justify="left",
			anchor="w",
			pady=3,
		)
		self.document_stats_label.pack(fill="x", padx=13, pady=(0, 12))

		self._section_label(self.sidebar, "OLLAMA")
		status_frame = tk.Frame(self.sidebar, bg=COLOR_SIDEBAR)
		status_frame.pack(fill="x", padx=19, pady=(8, 2))
		self.status_dot = tk.Label(
			status_frame,
			text="●",
			bg=COLOR_SIDEBAR,
			fg=COLOR_AMBER,
			font=(FONT_FAMILY, 11),
		)
		self.status_dot.pack(side="left")
		self.status_badge = tk.Label(
			status_frame,
			text="Checking…",
			bg=COLOR_SIDEBAR,
			fg=COLOR_AMBER,
			font=(FONT_FAMILY, 9, "bold"),
		)
		self.status_badge.pack(side="left", padx=(7, 0))
		self.status_tooltip = Tooltip(self.status_badge, "Checking Ollama connection")
		self.model_label = tk.Label(
			self.sidebar,
			text=f"Model  ·  {DEFAULT_MODEL}",
			bg=COLOR_SIDEBAR,
			fg=COLOR_MUTED,
			font=(FONT_FAMILY, 9),
			anchor="w",
		)
		self.model_label.pack(fill="x", padx=20, pady=(2, 15))

		self._section_label(self.sidebar, "ACTIONS")
		actions = (
			("Open document", self.open_document, "primary", "Choose a PDF or TXT file."),
			("Summarize", self.summarize_document, "warning", "Generate a concise document summary."),
			("Save chat", self.save_conversation, "info", "Save this conversation as a text file."),
			("Export chat", self.export_chat, "secondary", "Export this conversation as Markdown."),
			("Clear chat", self.clear_chat, "danger-outline", "Remove messages from the current chat."),
		)
		for text, command, style, tip in actions:
			button = self._button(self.sidebar, text, command, style, tip)
			button.pack(fill="x", padx=17, pady=3, ipady=2)

		activity_header = tk.Frame(self.sidebar, bg=COLOR_SIDEBAR)
		activity_header.pack(fill="x", padx=19, pady=(20, 7))
		self._section_label(activity_header, "RECENT ACTIVITY")
		self.activity_frame = tk.Frame(self.sidebar, bg=COLOR_SIDEBAR)
		self.activity_frame.pack(fill="x", padx=20)
		self._render_activity()

	def _build_main_area(self) -> None:
		self.main.grid_rowconfigure(1, weight=1)
		self.main.grid_columnconfigure(0, weight=1)
		topbar = tk.Frame(self.main, bg=COLOR_BG, height=72)
		topbar.grid(row=0, column=0, sticky="ew", padx=22)
		topbar.grid_propagate(False)
		brand = tk.Frame(topbar, bg=COLOR_BG)
		brand.pack(side="left", pady=13)
		tk.Label(
			brand,
			text="SmartDesk AI",
			bg=COLOR_BG,
			fg=COLOR_TEXT,
			font=(FONT_FAMILY, 16, "bold"),
		).pack(anchor="w")
		tk.Label(
			brand,
			text="LOCAL DOCUMENT WORKSPACE",
			bg=COLOR_BG,
			fg=COLOR_MUTED,
			font=(FONT_FAMILY, 8, "bold"),
		).pack(anchor="w", pady=(1, 0))
		header_meta = tk.Frame(topbar, bg=COLOR_BG)
		header_meta.pack(side="right", pady=17)
		self.top_document_label = tk.Label(
			header_meta,
			text="No document loaded",
			bg=COLOR_PANEL,
			fg=COLOR_MUTED,
			font=(FONT_FAMILY, 9),
			padx=11,
			pady=6,
		)
		self.top_document_label.pack(side="right", padx=(12, 0))
		self.header_model_label = tk.Label(
			header_meta,
			text=DEFAULT_MODEL,
			bg=COLOR_BG,
			fg=COLOR_MUTED,
			font=(FONT_FAMILY, 9),
		)
		self.header_model_label.pack(side="right", padx=(12, 5))
		self.header_status_badge = tk.Label(
			header_meta,
			text="● Checking",
			bg=COLOR_BG,
			fg=COLOR_AMBER,
			font=(FONT_FAMILY, 9, "bold"),
		)
		self.header_status_badge.pack(side="right")

		workspace = tk.Frame(self.main, bg=COLOR_BG)
		workspace.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 12))
		workspace.grid_rowconfigure(0, weight=1)
		workspace.grid_columnconfigure(0, weight=5, minsize=320)
		workspace.grid_columnconfigure(1, weight=6, minsize=340)

		self.document_panel = tk.Frame(
			workspace,
			bg=COLOR_PANEL,
			highlightthickness=1,
			highlightbackground=COLOR_BORDER,
		)
		self.document_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
		self.document_panel.grid_rowconfigure(2, weight=1)
		self.document_panel.grid_columnconfigure(0, weight=1)
		doc_heading = tk.Frame(self.document_panel, bg=COLOR_PANEL)
		doc_heading.grid(row=0, column=0, sticky="ew", padx=17, pady=(15, 5))
		tk.Label(
			doc_heading,
			text="Document preview",
			bg=COLOR_PANEL,
			fg=COLOR_TEXT,
			font=(FONT_FAMILY, 12, "bold"),
		).pack(anchor="w")
		self.preview_name_label = tk.Label(
			doc_heading,
			text="Open a PDF or TXT file to read it here",
			bg=COLOR_PANEL,
			fg=COLOR_MUTED,
			font=(FONT_FAMILY, 9),
			anchor="w",
			justify="left",
			wraplength=470,
		)
		self.preview_name_label.pack(fill="x", pady=(3, 0))
		self.preview_metadata_label = tk.Label(
			doc_heading,
			text="",
			bg=COLOR_PANEL,
			fg=COLOR_MUTED,
			font=(FONT_FAMILY, 8),
			anchor="w",
			justify="left",
			wraplength=470,
		)
		self.preview_metadata_label.pack(fill="x", pady=(4, 0))
		preview_toolbar = tk.Frame(self.document_panel, bg=COLOR_PANEL)
		preview_toolbar.grid(row=1, column=0, sticky="ew", padx=13, pady=(9, 8))
		self.page_label = tk.Label(
			preview_toolbar,
			text="No document",
			bg=COLOR_PANEL,
			fg=COLOR_MUTED,
			font=(FONT_FAMILY, 9),
		)
		self.page_label.pack(side="left", padx=(4, 0))
		zoom_out = self._button(preview_toolbar, "−", self._zoom_out, "secondary", "Reduce document text size.")
		zoom_out.pack(side="right", padx=(3, 0))
		zoom_in = self._button(preview_toolbar, "+", self._zoom_in, "secondary", "Increase document text size.")
		zoom_in.pack(side="right", padx=3)
		self.previous_page_button = self._button(
			preview_toolbar, "‹", self._previous_page, "secondary", "Show the previous PDF page."
		)
		self.previous_page_button.pack(side="right", padx=(12, 3))
		self.next_page_button = self._button(
			preview_toolbar,
			"›",
			self._next_page,
			"secondary",
			tooltip="Show the next PDF page.",
		)
		self.next_page_button.pack(side="right", padx=3)
		preview_body = tk.Frame(self.document_panel, bg=COLOR_PANEL_LIGHT)
		preview_body.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))
		preview_body.grid_rowconfigure(0, weight=1)
		preview_body.grid_columnconfigure(0, weight=1)
		self.preview_text = tk.Text(
			preview_body,
			wrap="word",
			state="disabled",
			bg=COLOR_PANEL_LIGHT,
			fg="#E2E9EC",
			insertbackground=COLOR_ACCENT,
			selectbackground="#28685E",
			relief="flat",
			borderwidth=0,
			padx=25,
			pady=24,
			font=("Georgia", self.preview_font_size),
			spacing1=3,
			spacing3=5,
		)
		self.preview_text.grid(row=0, column=0, sticky="nsew")
		preview_scrollbar = tb.Scrollbar(
			preview_body,
			orient="vertical",
			command=self.preview_text.yview,
			bootstyle="secondary-round",
		)
		preview_scrollbar.grid(row=0, column=1, sticky="ns")
		self.preview_text.configure(yscrollcommand=preview_scrollbar.set)

		self.chat_panel = tk.Frame(
			workspace,
			bg=COLOR_BG,
			highlightthickness=1,
			highlightbackground=COLOR_BORDER,
		)
		self.chat_panel.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
		self.chat_panel.grid_rowconfigure(1, weight=1)
		self.chat_panel.grid_columnconfigure(0, weight=1)
		chat_heading = tk.Frame(self.chat_panel, bg=COLOR_SIDEBAR, height=58)
		chat_heading.grid(row=0, column=0, sticky="ew")
		chat_heading.grid_propagate(False)
		tk.Label(
			chat_heading,
			text="Conversation",
			bg=COLOR_SIDEBAR,
			fg=COLOR_TEXT,
			font=(FONT_FAMILY, 12, "bold"),
		).pack(side="left", padx=16, pady=17)
		self.chat_document_label = tk.Label(
			chat_heading,
			text="Ask about your document",
			bg=COLOR_SIDEBAR,
			fg=COLOR_MUTED,
			font=(FONT_FAMILY, 9),
			anchor="e",
		)
		self.chat_document_label.pack(side="right", padx=14, pady=17)

		chat_shell = tk.Frame(self.chat_panel, bg=COLOR_BG)
		chat_shell.grid(row=1, column=0, sticky="nsew")
		chat_shell.grid_rowconfigure(0, weight=1)
		chat_shell.grid_columnconfigure(0, weight=1)
		self.chat_canvas = tk.Canvas(chat_shell, bg=COLOR_BG, highlightthickness=0, bd=0)
		self.chat_canvas.grid(row=0, column=0, sticky="nsew")
		self.chat_scrollbar = tb.Scrollbar(
			chat_shell,
			orient="vertical",
			command=self.chat_canvas.yview,
			bootstyle="secondary-round",
		)
		self.chat_scrollbar.grid(row=0, column=1, sticky="ns")
		self.chat_canvas.configure(yscrollcommand=self.chat_scrollbar.set)
		self.message_container = tk.Frame(self.chat_canvas, bg=COLOR_BG)
		self.canvas_window = self.chat_canvas.create_window(
			(0, 0), window=self.message_container, anchor="nw"
		)
		self.message_container.bind("<Configure>", self._update_scroll_region)
		self.chat_canvas.bind("<Configure>", self._resize_message_container)
		self.chat_canvas.bind("<MouseWheel>", self._scroll_chat)
		self._render_messages()

		bottom = tk.Frame(self.chat_panel, bg=COLOR_BG)
		bottom.grid(row=2, column=0, sticky="ew", padx=12, pady=(5, 12))
		bottom.grid_columnconfigure(0, weight=1)
		self.progress_row = tk.Frame(bottom, bg=COLOR_BG, height=24)
		self.progress_row.grid(row=0, column=0, sticky="ew", pady=(0, 5))
		self.progress_row.grid_columnconfigure(1, weight=1)
		self.progress_label = tk.Label(
			self.progress_row,
			text="",
			bg=COLOR_BG,
			fg=COLOR_ACCENT,
			font=(FONT_FAMILY, 9),
		)
		self.progress_label.grid(row=0, column=0, sticky="w")
		self.progress = tb.Progressbar(
			self.progress_row,
			mode="indeterminate",
			bootstyle="success-striped",
			length=100,
		)
		self.progress.grid(row=0, column=2, sticky="e")
		self.progress.grid_remove()
		self.composer = tk.Frame(
			bottom,
			bg=COLOR_PANEL,
			highlightthickness=1,
			highlightbackground=COLOR_BORDER,
		)
		self.composer.grid(row=1, column=0, sticky="ew")
		self.composer.grid_columnconfigure(0, weight=1)
		self.prompt_placeholder = "Ask any question about your document…"
		self.question_entry = tk.Text(
			self.composer,
			height=3,
			wrap="word",
			undo=True,
			bg=COLOR_PANEL,
			fg=COLOR_MUTED,
			insertbackground=COLOR_ACCENT,
			selectbackground="#28685E",
			relief="flat",
			borderwidth=0,
			padx=13,
			pady=11,
			font=(FONT_FAMILY, 10),
		)
		self.question_entry.grid(row=0, column=0, sticky="nsew", padx=(3, 0), pady=3)
		self.question_entry.insert("1.0", self.prompt_placeholder)
		self.question_entry.bind("<FocusIn>", self._clear_prompt_placeholder)
		self.question_entry.bind("<FocusOut>", self._restore_prompt_placeholder)
		self.question_entry.bind("<Return>", self._handle_enter)
		self.send_button = self._button(
			self.composer,
			"➤",
			self.send_question,
			"success",
			"Send your question. Enter sends; Shift+Enter adds a line.",
		)
		self.send_button.grid(row=0, column=1, padx=9, pady=8, sticky="se")
		tk.Label(
			bottom,
			text="Enter to send  ·  Shift+Enter for a new line",
			bg=COLOR_BG,
			fg=COLOR_MUTED,
			font=(FONT_FAMILY, 8),
		).grid(row=2, column=0, sticky="w", pady=(5, 0))

		self.status_bar = tk.Frame(self.main, bg=COLOR_PANEL, height=30)
		self.status_bar.grid(row=2, column=0, sticky="ew")
		self.status_bar.grid_propagate(False)
		self.status_message = tk.Label(
			self.status_bar,
			text="Ready",
			bg=COLOR_PANEL,
			fg=COLOR_MUTED,
			font=(FONT_FAMILY, 8),
			anchor="w",
		)
		self.status_message.pack(side="left", padx=14)
		self.conversation_stats = tk.Label(
			self.status_bar,
			text="Conversation 1  ·  0 words  ·  0 characters",
			bg=COLOR_PANEL,
			fg=COLOR_MUTED,
			font=(FONT_FAMILY, 8),
			anchor="e",
		)
		self.conversation_stats.pack(side="right", padx=14)
		self._render_document_preview()

	def _clear_prompt_placeholder(self, _event: tk.Event[Any] | None = None) -> None:
		if self.question_entry.get("1.0", "end-1c") == self.prompt_placeholder:
			self.question_entry.delete("1.0", "end")
			self.question_entry.configure(fg=COLOR_TEXT)

	def _restore_prompt_placeholder(self, _event: tk.Event[Any] | None = None) -> None:
		if not self.question_entry.get("1.0", "end-1c").strip():
			self.question_entry.delete("1.0", "end")
			self.question_entry.insert("1.0", self.prompt_placeholder)
			self.question_entry.configure(fg=COLOR_MUTED)

	def _render_document_preview(self) -> None:
		if not hasattr(self, "preview_text"):
			return
		if self.document is None:
			content = "Your selected document will appear here.\n\nOpen a PDF to navigate its extracted pages, or open a TXT file to read it in one continuous view."
			self.preview_metadata_label.configure(text="")
			self.page_label.configure(text="No document")
			self.previous_page_button.configure(state="disabled")
			self.next_page_button.configure(state="disabled")
		else:
			pages = self.document.pages or (self.document.text,)
			self.preview_page_index = min(self.preview_page_index, max(0, len(pages) - 1))
			content = pages[self.preview_page_index] or "No selectable text was found on this page."
			if len(content) > PREVIEW_CHARACTER_LIMIT:
				content = (
					content[:PREVIEW_CHARACTER_LIMIT].rstrip()
					+ "\n\n[Preview shortened to keep the interface responsive. The original document remains loaded.]"
				)
			if self.document.page_count is None:
				self.page_label.configure(text="Text document")
				self.previous_page_button.configure(state="disabled")
				self.next_page_button.configure(state="disabled")
			else:
				self.page_label.configure(
					text=f"Page {self.preview_page_index + 1} of {self.document.page_count}"
				)
				self.previous_page_button.configure(
					state="normal" if self.preview_page_index > 0 else "disabled"
				)
				self.next_page_button.configure(
					state=(
						"normal"
						if self.preview_page_index < self.document.page_count - 1
						else "disabled"
					)
				)
		self.preview_text.configure(state="normal", font=("Georgia", self.preview_font_size))
		self.preview_text.delete("1.0", "end")
		self.preview_text.insert("1.0", content)
		self.preview_text.configure(state="disabled")
		self.preview_text.yview_moveto(0)

	def _change_preview_page(self, amount: int) -> None:
		if not self.document or self.document.page_count is None:
			return
		self.preview_page_index = max(
			0,
			min(self.preview_page_index + amount, self.document.page_count - 1),
		)
		self._render_document_preview()

	def _previous_page(self) -> None:
		self._change_preview_page(-1)

	def _next_page(self) -> None:
		self._change_preview_page(1)

	def _zoom_in(self) -> None:
		self.preview_font_size = min(20, self.preview_font_size + 1)
		self._render_document_preview()

	def _zoom_out(self) -> None:
		self.preview_font_size = max(8, self.preview_font_size - 1)
		self._render_document_preview()

	def _section_label(self, parent: tk.Misc, text: str) -> tk.Label:
		label = tk.Label(
			parent,
			text=text,
			bg=parent.cget("bg"),
			fg=COLOR_MUTED,
			font=(FONT_FAMILY, 8, "bold"),
			anchor="w",
		)
		label.pack(fill="x", padx=20)
		return label

	@staticmethod
	def _button(
		parent: tk.Misc,
		text: str,
		command: Callable[[], None],
		style: str,
		tooltip: str,
	) -> tb.Button:
		return create_button(parent, text, command, style, tooltip)

	def _render_messages(self) -> None:
		for child in self.message_container.winfo_children():
			child.destroy()
		self.message_labels.clear()
		if not self.chat_manager.messages:
			welcome = tk.Frame(self.message_container, bg=COLOR_BG)
			welcome.pack(fill="x", pady=(100, 35))
			tk.Label(
				welcome,
				text="Your documents, in focus.",
				bg=COLOR_BG,
				fg=COLOR_TEXT,
				font=(FONT_FAMILY, 25, "bold"),
			).pack()
			tk.Label(
				welcome,
				text="Open a local PDF or TXT file, then ask a question.",
				bg=COLOR_BG,
				fg=COLOR_MUTED,
				font=(FONT_FAMILY, 11),
			).pack(pady=(10, 0))
			return

		for message in self.chat_manager.messages:
			self._render_message(message)
		self.root.after_idle(lambda: self.chat_canvas.yview_moveto(1.0))

	def _render_message(self, message: ChatMessage) -> None:
		is_user = message.role == "user"
		row = tk.Frame(self.message_container, bg=COLOR_BG)
		row.pack(fill="x", padx=22, pady=(10, 3))
		bubble_color = COLOR_USER if is_user else COLOR_ASSISTANT
		bubble = tk.Frame(row, bg=bubble_color, padx=15, pady=11)
		bubble.pack(side="right" if is_user else "left", anchor="e" if is_user else "w")
		width = max(280, min(720, int(self.chat_canvas.winfo_width() * 0.67)))
		tk.Label(
			bubble,
			text="You" if is_user else "AI Assistant",
			bg=bubble_color,
			fg=COLOR_ACCENT if not is_user else "#B5EDE2",
			font=(FONT_FAMILY, 9, "bold"),
			anchor="w",
		).pack(fill="x", pady=(0, 5))
		content = tk.Label(
			bubble,
			text=message.content,
			bg=bubble_color,
			fg=COLOR_TEXT,
			font=(FONT_FAMILY, 10),
			justify="left",
			anchor="w",
			wraplength=width,
		)
		content.pack(fill="x")
		self.message_labels.append(content)
		tk.Label(
			bubble,
			text=message.timestamp.strftime("%I:%M %p").lstrip("0"),
			bg=bubble_color,
			fg=COLOR_MUTED,
			font=(FONT_FAMILY, 8),
			anchor="e" if is_user else "w",
		).pack(fill="x", pady=(7, 0))

	def _resize_message_container(self, event: tk.Event[Any]) -> None:
		self.chat_canvas.itemconfigure(self.canvas_window, width=event.width)
		wraplength = max(220, min(720, int(event.width * 0.67)))
		for label in self.message_labels:
			label.configure(wraplength=wraplength)

	def _update_scroll_region(self, _event: tk.Event[Any]) -> None:
		self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all"))

	def _scroll_chat(self, event: tk.Event[Any]) -> None:
		self.chat_canvas.yview_scroll(int(-event.delta / 120), "units")

	def _handle_enter(self, event: tk.Event[Any]) -> str | None:
		if event.state & 0x0001:
			return None
		self.send_question()
		return "break"

	def _add_message(self, role: str, content: str) -> None:
		self.chat_manager.add_message(role, content)
		self._render_messages()
		self._update_conversation_stats()

	def _update_conversation_stats(self) -> None:
		self.conversation_stats.configure(
			text=(
				f"Conversation {self.chat_manager.conversation_number}  ·  "
				f"{self.chat_manager.word_count:,} words  ·  "
				f"{self.chat_manager.character_count:,} characters"
			)
		)

	def _set_status(self, text: str, color: str = COLOR_MUTED) -> None:
		self.status_message.configure(text=text, fg=color)

	def _set_busy(self, busy: bool, label: str = "Working…") -> None:
		self.is_busy = busy
		self.send_button.configure(state="disabled" if busy else "normal")
		if busy:
			self.progress_label.configure(text=label)
			self.progress.grid()
			self.progress.start(12)
			self._set_status(label, COLOR_ACCENT)
		else:
			self.progress.stop()
			self.progress.grid_remove()
			self.progress_label.configure(text="")

	def _submit(self, kind: str, operation: Callable[[], Any]) -> None:
		future = self.executor.submit(operation)

		def completed(task: Future[Any]) -> None:
			try:
				self.ui_events.put((kind, True, task.result()))
			except Exception as exc:
				self.logger.exception("Background operation '%s' failed", kind)
				self.ui_events.put((kind, False, exc))

		future.add_done_callback(completed)

	def _poll_events(self) -> None:
		try:
			while True:
				kind, succeeded, result = self.ui_events.get_nowait()
				self._handle_event(kind, succeeded, result)
		except queue.Empty:
			pass
		if self.root.winfo_exists():
			self.root.after(EVENT_POLL_INTERVAL_MS, self._poll_events)

	def _handle_event(self, kind: str, succeeded: bool, result: Any) -> None:
		if kind == "status":
			self.status_check_pending = False
			if succeeded:
				self.ollama_status = result
				self._update_ollama_status(result)
			else:
				self.logger.warning("Ollama status check failed: %s", result)
				self.ollama_status = OllamaStatus(False, False, str(result))
				self._update_ollama_status(self.ollama_status)
			return

		self._set_busy(False)
		if kind == "document":
			if succeeded:
				self.document = result
				self._update_document_info(result)
				self._record_activity(f"Opened {result.name}")
				self._set_status(f"Loaded {result.name}", COLOR_GREEN)
				if not result.text.strip():
					show_warning(
						"No extractable text",
						"This document contains no selectable text. Scanned PDFs may need OCR first.",
						parent=self.root,
					)
			else:
				self._set_status("Document could not be opened", COLOR_RED)
				show_error("Could not open document", str(result), parent=self.root)
			return

		if not succeeded:
			self._set_status("Request failed", COLOR_RED)
			show_error("SmartDesk AI", str(result), parent=self.root)
			return

		response, activity = result
		self._add_message("assistant", response)
		self._record_activity(activity)
		self._set_status("Response ready", COLOR_GREEN)

	def _update_ollama_status(self, status: OllamaStatus) -> None:
		if status.ready:
			color, label = COLOR_GREEN, "Connected"
		elif status.connected:
			color, label = COLOR_AMBER, "Model missing"
		else:
			color, label = COLOR_RED, "Offline"
		self.status_dot.configure(fg=color)
		self.status_badge.configure(text=label, fg=color)
		self.header_status_badge.configure(text=f"● {label}", fg=color)
		self.model_label.configure(text=f"Model  ·  {DEFAULT_MODEL}")
		self.header_model_label.configure(text=DEFAULT_MODEL)
		if status.ready and not self.is_busy:
			self._set_status("Ollama ready", COLOR_GREEN)
		elif not self.is_busy:
			self._set_status(status.message, color)
		self.status_tooltip.text = status.message

	def _request_status_check(self) -> None:
		if self.status_check_pending:
			return
		self.status_check_pending = True
		self._submit("status", self.ollama_service.check_status)

	def _schedule_status_check(self) -> None:
		if not self.root.winfo_exists():
			return
		self._request_status_check()
		self.root.after(STATUS_CHECK_INTERVAL_MS, self._schedule_status_check)

	def open_document(self) -> None:
		if self.is_busy:
			return
		file_path = filedialog.askopenfilename(
			parent=self.root,
			title="Open a document",
			filetypes=(
				("Supported documents", "*.pdf *.txt"),
				("PDF documents", "*.pdf"),
				("Text documents", "*.txt"),
			),
		)
		if not file_path:
			return
		self._set_busy(True, "Reading document…")
		self._submit("document", lambda: self.document_service.load(file_path))

	def _update_document_info(self, document: DocumentInfo) -> None:
		self.document_name_label.configure(text=document.name)
		self.document_path_label.configure(text=str(document.path.parent))
		pages = str(document.page_count) if document.page_count is not None else "—"
		self.document_stats_label.configure(
			text=(
				f"Type  {document.file_type}     Size  {document.size_label}\n"
				f"Words  {document.word_count:,}     Characters  {document.character_count:,}\n"
				f"Pages  {pages}"
			)
		)
		if document.file_type == "PDF":
			metadata = "  ·  ".join(f"{key}: {value}" for key, value in document.metadata)
			self.preview_metadata_label.configure(
				text=metadata or "No PDF metadata available"
			)
		else:
			self.preview_metadata_label.configure(text="Plain text document")
		self.top_document_label.configure(
			text=document.name,
			fg=COLOR_TEXT,
		)
		self.preview_name_label.configure(text=document.name)
		self.chat_document_label.configure(text=document.name)
		self.preview_page_index = 0
		self._render_document_preview()
		self.root.title(f"{document.name} - {WINDOW_TITLE}")

	def send_question(self) -> None:
		question_text = self.question_entry.get("1.0", "end-1c").strip()
		if question_text == self.prompt_placeholder or not question_text or self.is_busy:
			return
		question = question_text
		if not self.document:
			show_warning(
				"No document selected",
				"Open a PDF or TXT document before asking a question.",
				parent=self.root,
			)
			return
		if not self._ensure_ollama_ready():
			return

		self.question_entry.delete("1.0", "end")
		self.question_entry.configure(fg=COLOR_TEXT)
		self._add_message("user", question)
		prompt = self.chat_manager.build_prompt(self.document.text, question)
		self._set_busy(True, "AI is thinking...")
		self._submit("answer", lambda: (self.ollama_service.generate(prompt), "Answered a question"))

	def summarize_document(self) -> None:
		if self.is_busy:
			return
		if not self.document:
			show_warning(
				"No document selected",
				"Open a document before requesting a summary.",
				parent=self.root,
			)
			return
		if not self._ensure_ollama_ready():
			return
		self._add_message("user", f"Summarize {self.document.name}")
		prompt = self.chat_manager.build_summary_prompt(self.document.text)
		self._set_busy(True, "AI is thinking...")
		self._submit("summary", lambda: (self.ollama_service.generate(prompt), "Summarized the document"))

	def _ensure_ollama_ready(self) -> bool:
		if self.ollama_status is None:
			self._request_status_check()
			show_info(
				"Checking Ollama",
				"The app is checking the local Ollama connection. Try again in a moment.",
				parent=self.root,
			)
			return False
		if not self.ollama_status.ready:
			show_error(
				"Ollama is not ready",
				f"{self.ollama_status.message}\n\n"
				f"Start Ollama and make sure '{DEFAULT_MODEL}' is installed.\n"
				f"To install it, run: ollama pull {DEFAULT_MODEL}",
				parent=self.root,
			)
			self._request_status_check()
			return False
		return True

	def new_chat(self) -> None:
		if self.is_busy:
			return
		self.chat_manager.clear(new_conversation=True)
		self._render_messages()
		self._update_conversation_stats()
		self._record_activity("Started a new conversation")
		self._set_status("New conversation", COLOR_GREEN)

	def clear_chat(self) -> None:
		if self.is_busy or not self.chat_manager.messages:
			return
		confirmed = confirm(
			"Clear chat",
			"Remove all messages from this conversation?",
			parent=self.root,
		)
		if not confirmed:
			return
		self.chat_manager.clear()
		self._render_messages()
		self._update_conversation_stats()
		self._record_activity("Cleared the current conversation")
		self._set_status("Chat cleared", COLOR_GREEN)

	def save_conversation(self) -> None:
		self._save_chat("text")

	def export_chat(self) -> None:
		self._save_chat("markdown")

	def _save_chat(self, format_name: str) -> None:
		if not self.chat_manager.messages:
			show_info(
				"Nothing to save",
				"This conversation does not contain any messages yet.",
				parent=self.root,
			)
			return
		is_markdown = format_name == "markdown"
		extension = ".md" if is_markdown else ".txt"
		file_types = (("Markdown files", "*.md"),) if is_markdown else (("Text files", "*.txt"),)
		file_path = filedialog.asksaveasfilename(
			parent=self.root,
			title="Export conversation" if is_markdown else "Save conversation",
			defaultextension=extension,
			initialfile=f"smartdesk_conversation_{self.chat_manager.conversation_number}{extension}",
			initialdir=str(EXPORT_DIRECTORY),
			filetypes=file_types,
		)
		if not file_path:
			return
		try:
			self.chat_manager.save(file_path, format_name)
			action = "Exported chat" if is_markdown else "Saved conversation"
			self._record_activity(action)
			self._set_status(f"{action} to {Path(file_path).name}", COLOR_GREEN)
			Toast(self.root, f"{action} successfully")
		except OSError as exc:
			self.logger.exception("Could not save conversation")
			show_error("Could not save conversation", str(exc), parent=self.root)

	def _record_activity(self, text: str) -> None:
		self.activity_items.insert(0, (text, datetime.now().strftime("%H:%M")))
		self.activity_items = self.activity_items[:4]
		self._render_activity()

	def _render_activity(self) -> None:
		for child in self.activity_frame.winfo_children():
			child.destroy()
		if not self.activity_items:
			tk.Label(
				self.activity_frame,
				text="Nothing yet",
				bg=COLOR_SIDEBAR,
				fg=COLOR_MUTED,
				font=(FONT_FAMILY, 9),
				anchor="w",
			).pack(fill="x")
			return
		for text, timestamp in self.activity_items:
			item = tk.Frame(self.activity_frame, bg=COLOR_SIDEBAR)
			item.pack(fill="x", pady=3)
			tk.Label(
				item,
				text="·",
				bg=COLOR_SIDEBAR,
				fg=COLOR_ACCENT,
				font=(FONT_FAMILY, 13, "bold"),
			).pack(side="left", anchor="n", padx=(0, 6))
			detail = tk.Frame(item, bg=COLOR_SIDEBAR)
			detail.pack(side="left", fill="x", expand=True)
			tk.Label(
				detail,
				text=text,
				bg=COLOR_SIDEBAR,
				fg="#CFD7DA",
				font=(FONT_FAMILY, 9),
				anchor="w",
				justify="left",
				wraplength=205,
			).pack(fill="x")
			tk.Label(
				detail,
				text=timestamp,
				bg=COLOR_SIDEBAR,
				fg=COLOR_MUTED,
				font=(FONT_FAMILY, 8),
				anchor="w",
			).pack(fill="x")

	def _close(self) -> None:
		self.executor.shutdown(wait=False, cancel_futures=True)
		self.root.destroy()

