# SmartDesk AI

SmartDesk AI is a local-first desktop assistant for reading PDF and TXT documents, asking questions about their contents, and generating summaries with Ollama. The interface pairs a navigable document preview with a timestamped chat workspace.

## Features

- PDF text extraction, page navigation, page count, and available metadata display
- TXT loading with UTF-8 and legacy Windows-encoding fallback
- Document-grounded question answering and summarization
- Local Ollama connection checks, model detection, retries, and friendly failure messages
- Background document and model work so the Tkinter interface remains responsive
- Timestamped chat history, clear chat, TXT save, and Markdown export
- Document statistics, recent activity, progress indication, and non-modal success toasts

## Technologies

- Python 3.12
- Tkinter and ttkbootstrap
- Ollama with the `llama3.2` model
- PyPDF for PDF reading
- Requests for local Ollama HTTP communication

## Offline Operation

Document contents are processed on the local computer and sent only to the local Ollama service at `http://localhost:11434`. No cloud AI provider or remote document service is used. Internet access is needed to install Python dependencies and download the Ollama model; after setup, document analysis works locally while Ollama is running.

## Installation

1. Install Python 3.12 and [Ollama](https://ollama.com/download).
2. Clone or download this repository and open a terminal in the project root.
3. Create and activate a virtual environment:

   ```powershell
   py -3.12 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   On macOS or Linux, activate with `source .venv/bin/activate`.
4. Install the Python dependencies:

   ```text
   python -m pip install -r requirements.txt
   ```
5. Download and start the model:

   ```text
   ollama pull llama3.2
   ollama serve
   ```

   If the Ollama desktop app is already running the service, `ollama serve` may not be needed.
6. Launch SmartDesk AI:

   ```text
   python main.py
   ```

   The package entry point is also available with `python -m smart_desk.main`.

## Screenshots

Add application screenshots under `assets/` and link them here. The desktop layout is designed around a left navigation rail, document preview pane, and conversation pane.

## Project Structure

```text
smart_agent_ai/
├── main.py
├── smart_desk/
│   ├── main.py
│   ├── services/
│   └── ui/
├── services/        # Backward-compatible service implementations
├── ui/               # Backward-compatible desktop window
├── assets/
├── logs/             # Created when the application starts; gitignored
├── exports/          # Created when the application starts; gitignored
├── requirements.txt
└── README.md
```

The `smart_desk` package is the canonical application entry point. Existing root-level service and UI modules remain available for compatibility with earlier project versions.

## Future Enhancements

- OCR for scanned PDFs
- Streaming responses and cancellation
- Persistent named conversations
- Search within long documents and citations linked to source pages
- Optional multi-document workspaces
