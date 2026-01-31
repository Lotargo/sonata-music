# Audio Upscaler Backend

A Flask-based backend for upscaling audio using [AudioSR](https://github.com/haoheliu/AudioSR).

## Features

- **Audio Super Resolution**: Upscale low-quality audio to 48kHz.
- **Library Management**: Store and manage original and processed tracks.
- **GPU Acceleration**: Automatically detects and uses CUDA if available.
- **REST API**: Simple endpoints for upload, processing, and retrieval.

## Requirements

- Python 3.10+
- `uv` (for dependency management)
- NVIDIA GPU with CUDA (recommended)

## Installation

1.  **Install `uv`** (if not already installed):
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

2.  **Install dependencies**:
    ```bash
    uv sync
    ```

3.  **Check Environment**:
    Run the environment check script to verify Python version and CUDA availability.
    ```bash
    uv run check_env.py
    ```

## Usage

1.  **Start the server**:
    ```bash
    uv run main.py
    ```
    The server will start at `http://0.0.0.0:5000`.

2.  **API Endpoints**:

    -   `POST /upload`: Upload an audio file (key: `file`). Returns track info including ID.
    -   `POST /process/<track_id>`: Start upscaling for a track.
    -   `GET /library`: List all tracks.
    -   `GET /uploads/<filename>`: Download original file.
    -   `GET /library/<filename>`: Download processed file.

## Project Structure

-   `app/`: Application source code.
    -   `models.py`: Database models.
    -   `routes.py`: API routes.
    -   `services/upscaler.py`: Wrapper for AudioSR.
-   `uploads/`: Stores uploaded original files.
-   `library/`: Stores processed (upscaled) files.
-   `tests/`: Unit tests.

## Notes

-   First run of the upscaler will download the AudioSR model checkpoints automatically.
-   Processing on CPU is significantly slower than on GPU.
