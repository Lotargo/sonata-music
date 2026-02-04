# AudioSR Pro: AI-Powered Music Platform

An ambitious project to transform low-quality audio (e.g., from Suno) into high-fidelity music using state-of-the-art AI, now featuring a scalable Django backend and a sleek "Yandex Music"-style interface.

## 🚀 Features

### ✨ AI-Powered Upscaling
- **Audio Super Resolution**: Powered by [AudioSR](https://github.com/haoheliu/AudioSR), converting muffled audio (16kHz/24kHz) into crystal clear 48kHz+ signals.
- **Customizable Output**: Choose your preferred format (**MP3, WAV, FLAC, OGG**).
- **Quality Control**: Configure target **Sample Rate** (up to 96kHz) and **Bitrate** (up to 4608kbps).

### 🎨 Professional Web Interface (New!)
- **Yandex Music Aesthetic**: Dark theme, fixed player bar, and intuitive sidebar navigation.
- **Modern Library**: Card-based grid with auto-extracted **Cover Art** and **Metadata** (Title, Artist).
- **Seamless Playback**: Integrated HTML5 audio player with persistent controls.

### ⚙️ Robust Backend (Django)
- **Framework**: Migrated to **Django 5** for scalability, security, and built-in administration.
- **NVIDIA CUDA Ready**: Automatic GPU detection with a reliable CPU fallback.
- **Async Processing**: Multi-threaded upscaling (logic preserved in `music/services`).

## 🛠️ Technology Stack

- **Backend**: Python 3.10, Django 5, SQLite
- **AI/DSP**: AudioSR, PyTorch, Torchaudio, Pydub, Mutagen
- **Frontend**: Django Templates, Tailwind CSS (CDN), Vanilla JS
- **Tooling**: `uv` for lightning-fast dependency management

## 📦 Installation

This project uses `uv` for dependency management.

1.  **Install `uv`** (if not already installed):
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

2.  **Install Dependencies**:
    ```bash
    uv sync
    ```

3.  **Apply Database Migrations**:
    ```bash
    uv run python manage.py migrate
    ```

## 🚀 Getting Started

The frontend is integrated directly into the Django backend. You only need to start one server.

1.  **Launch the Server**:
    ```bash
    uv run python manage.py runserver
    ```
2.  **Open in Browser**:
    Navigate to `http://127.0.0.1:8000` to access the interface.

## 📁 Project Structure

- `config/`: Django project settings and configuration.
- `music/`: Main Django application.
    - `templates/`: HTML interface (base, index, upload).
    - `services/`: AI upscaling, DSP, and logic (ported from Flask).
    - `models.py`: Database schema for Tracks.
    - `views.py`: Request handlers.
- `legacy_flask/`: Archived Flask application (for reference).
- `media/`:
    - `uploads/`: Raw original files.
    - `covers/`: Uploaded cover art.
    - `processed/`: Upscaled results.

## ⚠️ Notes

- **Initial Run**: The first upscaling task will automatically download the required AudioSR model weights (~2GB).
- **Performance**: While CPU works perfectly, an **NVIDIA GPU** is highly recommended for near-instant generation.
- **Development**: This project currently runs in `DEBUG` mode with a development secret key unless configured via environment variables.
