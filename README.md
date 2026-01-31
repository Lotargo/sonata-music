# AudioSR Pro: AI-Powered Audio Upscaler & Library

An ambitious project to transform low-quality audio (e.g., from Suno) into high-fidelity music using state-of-the-art AI.

## 🚀 Features

### ✨ AI-Powered Upscaling
- **Audio Super Resolution**: Powered by [AudioSR](https://github.com/haoheliu/AudioSR), converting muffled audio (16kHz/24kHz) into crystal clear 48kHz+ signals.
- **Customizable Output**: Choose your preferred format (**MP3, WAV, FLAC, OGG**).
- **Quality Control**: Configure target **Sample Rate** (up to 96kHz) and **Bitrate** (up to 320kbps).

### 🎨 Professional Web Interface
- **SoundCloud-Style Player**: Interactive waveforms powered by `Wavesurfer.js`.
- **Modern Library**: Card-based grid with auto-extracted **Cover Art** and **Metadata** (Title, Artist).
- **Seamless Experience**: Drag & drop uploads, real-time processing status, and responsive design using Tailwind CSS.
- **Full Control**: Edit track details or remove files from your library directly from the UI.

### ⚙️ Robust Backend
- **NVIDIA CUDA Ready**: Automatic GPU detection with a reliable CPU fallback.
- **Async Processing**: Multi-threaded upscaling so you can keep browsing while the AI works.
- **SQLite Persistence**: Reliable storage for your library and settings.

## 🛠️ Technology Stack

- **Backend**: Python 3.10, Flask, SQLAlchemy
- **AI/DSP**: AudioSR, PyTorch, Torchaudio, Pydub, Mutagen
- **Frontend**: Tailwind CSS, Wavesurfer.js, Lucide Icons
- **Tooling**: `uv` for lightning-fast dependency management

## 📦 Installation

1.  **Install `uv`** (the modern Python package manager):
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

2.  **Clone & Install Dependencies**:
    ```bash
    uv sync
    ```

3.  **Verify Environment**:
    Check if your system is ready for AI upscaling (detects Python version and CUDA):
    ```bash
    uv run check_env.py
    ```

## 🚀 Getting Started

1.  **Launch the Application**:
    ```bash
    uv run main.py
    ```
2.  **Open in Browser**:
    Navigate to `http://localhost:5000` to access the interface.

## 📁 Project Structure

- `app/`:
    - `templates/`: HTML interface.
    - `static/`: Frontend assets (CSS, JS, Extracted Covers).
    - `services/`: AI upscaling, metadata extraction, and format conversion.
    - `models.py`: SQLite database schema.
    - `routes.py`: API and frontend routing.
- `uploads/`: Raw original files.
- `library/`: High-quality upscaled results.

## ⚠️ Notes

- **Initial Run**: The first upscaling task will automatically download the required AudioSR model weights (~2GB).
- **Performance**: While CPU works perfectly, an **NVIDIA GPU** is highly recommended for near-instant generation.
