# Audio Upscaler for Suno

A professional audio upscaling backend using [AudioSR](https://github.com/haoheliu/AudioSR) to enhance Suno-generated tracks from low quality to high-fidelity 48kHz audio.

## Features

- **High-Quality Upscaling**: Uses AudioSR diffusion models for crystal clear audio.
- **CUDA Support**: Automatically detects NVIDIA GPUs for ultra-fast processing, with a graceful CPU fallback.
- **Flask API**: Simple RESTful API for integration with any frontend.
- **Library Management**: Organizes uploads and processed tracks.

## Technical Stack

- **Python**: 3.10
- **Dependency Management**: `uv`
- **Backend**: Flask
- **AI Models**: AudioSR (based on PyTorch & Latent Diffusion)

## Installation

1.  Ensure you have `uv` installed.
2.  Install dependencies:
    ```bash
    uv sync
    ```

## Running the Backend

Start the Flask server:
```bash
uv run python -m audio_upscaler.app
```
The server will be available at `http://localhost:5000`.

## API Endpoints

### 1. Upload Audio
`POST /api/upload`
- Body: `multipart/form-data` with a `file` field.
- Returns: `{"message": "File uploaded successfully", "filename": "track.mp3"}`

### 2. Upscale Audio
`POST /api/upscale`
- Body (JSON):
  ```json
  {
    "filename": "track.mp3",
    "ddim_steps": 50,
    "guidance_scale": 3.5
  }
  ```
- Returns: `{"message": "Upscaling complete", "processed_filename": "track_upscaled.wav"}`

### 3. List Library
`GET /api/library`
- Returns lists of uploaded and processed filenames.

### 4. Download File
`GET /api/download/<folder_type>/<filename>`
- `folder_type`: `uploads` or `processed`.

### 5. Health Check
`GET /api/health`
- Returns status and CUDA availability.

## Project Structure

- `src/audio_upscaler/`: Core logic and API.
- `library/uploads/`: Original tracks.
- `library/processed/`: Upscaled tracks.
- `pyproject.toml`: Dependency configuration.
