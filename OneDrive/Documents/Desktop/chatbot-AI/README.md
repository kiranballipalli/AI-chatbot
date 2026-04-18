# 🔥 CodeSage – AI Code Reviewer

> Instant AI-powered code reviews for cleaner, safer Python.

CodeSage is a lightweight web application that uses a local **Ollama** LLM to analyze your Python code and provide detailed feedback on bugs, style, performance, and security.

![CodeSage Screenshot](https://via.placeholder.com/800x400?text=CodeSage+UI+Preview)

## ✨ Features

- 🧠 **Local AI Review** – Uses Ollama (Llama3, CodeLlama, etc.) running on your machine.
- 📝 **Markdown Output** – Reviews are formatted with clear sections and syntax-highlighted code blocks.
- ⚡ **Real‑time Streaming** – See the AI response as it's generated (optional branch).
- 🎨 **Modern Dark UI** – Glassmorphism design with smooth animations.
- 📱 **Responsive** – Works on desktop and mobile.

## 🚀 Quick Start

### 1. Prerequisites

- Python 3.9+
- [Ollama](https://ollama.ai) installed and running
- A pulled model (e.g., `llama3`, `codellama`, `mistral`)

```bash
# Install Ollama (macOS/Linux)
curl -fsSL https://ollama.ai/install.sh | sh

# Pull a model
ollama pull llama3

python main.py