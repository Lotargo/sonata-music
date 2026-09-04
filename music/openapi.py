"""
OpenAPI 3.1.0 Specification Generator for Music Upscaler Pro API.
Provides full interactive API documentation schema for Scalar UI (/api/docs/).
"""

def get_openapi_spec():
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "Music Upscaler Pro API",
            "version": "2.4.0",
            "description": (
                "Professional AI-powered audio super-resolution, Anti-AI stealth processing, "
                "parametric mastering DSP, and stereo acoustic metrics API."
            ),
            "contact": {
                "name": "Music Upscaler Engineering",
                "url": "https://github.com/Lotargo/private--music_upscaler"
            },
            "license": {
                "name": "Proprietary / Studio License"
            }
        },
        "servers": [
            {
                "url": "/",
                "description": "Current Environment Server"
            }
        ],
        "tags": [
            {
                "name": "Upload & Analysis",
                "description": "File ingestion, acoustic extraction (BPM, Key, Centroid), and upload lifecycle"
            },
            {
                "name": "Processing & AI Upscaling",
                "description": "Multi-engine AI generation (AudioSR, Stealth, Apollo, FLowHigh) & DSP chains"
            },
            {
                "name": "Library & Tracks",
                "description": "Track management, pagination, metadata updates, and audio streaming"
            },
            {
                "name": "Studio Metrics",
                "description": "Dual-channel L/R spectrograms, phase correlation, PESQ, and SI-SDR comparison"
            },
            {
                "name": "Stems & Karaoke",
                "description": "Stem separation, Demucs neural isolation, and vocal subtraction"
            }
        ],
        "paths": {
            "/api/health/": {
                "get": {
                    "tags": ["System & Health"],
                    "summary": "Service health check",
                    "description": "Returns service status and version for launchers and monitoring.",
                    "responses": {
                        "200": {
                            "description": "Service is healthy and ready",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "status": {"type": "string", "example": "healthy"},
                                            "service": {"type": "string", "example": "music_upscaler"},
                                            "version": {"type": "string", "example": "2.4.0"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "/upload/": {
                "post": {
                    "tags": ["Upload & Analysis"],
                    "summary": "Upload and analyze audio file",
                    "description": "Uploads an audio file, extracts acoustic parameters (BPM, musical key, spectral centroid), generates spectrogram and album cover preview.",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "multipart/form-data": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "audio_file": {
                                            "type": "string",
                                            "format": "binary",
                                            "description": "Audio file (MP3, WAV, FLAC, OGG, M4A, Opus up to 50MB)"
                                        }
                                    },
                                    "required": ["audio_file"]
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Track analyzed and registered successfully",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/TrackUploadResponse"
                                    }
                                }
                            }
                        },
                        "400": {
                            "description": "Invalid file format or corrupt audio"
                        }
                    }
                }
            },
            "/process/{track_id}/": {
                "post": {
                    "tags": ["Processing & AI Upscaling"],
                    "summary": "Start AI super-resolution or DSP mastering",
                    "description": "Initiates asynchronous processing thread with configured AI engine, DDIM parameters, and Studio DSP effects.",
                    "parameters": [
                        {
                            "name": "track_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                            "description": "ID of the uploaded track"
                        }
                    ],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/ProcessTrackRequest"
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Processing started in background",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "message": {"type": "string", "example": "Processing started"},
                                            "status": {"type": "string", "example": "processing"}
                                        }
                                    }
                                }
                            }
                        },
                        "400": {
                            "description": "Track is already processing or payload is invalid"
                        },
                        "404": {
                            "description": "Track not found"
                        }
                    }
                }
            },
            "/library/": {
                "get": {
                    "tags": ["Library & Tracks"],
                    "summary": "Get track library",
                    "description": "Returns a list of tracks with their processing status, formats, and acoustic metadata.",
                    "parameters": [
                        {
                            "name": "search",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "string"},
                            "description": "Search keyword matching title or artist"
                        },
                        {
                            "name": "status",
                            "in": "query",
                            "required": False,
                            "schema": {
                                "type": "string",
                                "enum": ["all", "completed", "processing", "failed"]
                            },
                            "description": "Filter by processing status"
                        },
                        {
                            "name": "sort",
                            "in": "query",
                            "required": False,
                            "schema": {
                                "type": "string",
                                "enum": ["-created_at", "title", "artist", "duration"]
                            },
                            "description": "Sort order"
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "List of library tracks",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {"$ref": "#/components/schemas/TrackSummary"}
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "/metrics/{track_id}/": {
                "get": {
                    "tags": ["Studio Metrics"],
                    "summary": "Get stereo comparison metrics",
                    "description": "Returns objective quality metrics (PESQ, SI-SDR, LSD) and stereo L/R channel dynamics (Pearson correlation, Mid/Side balance, Stereo Width).",
                    "parameters": [
                        {
                            "name": "track_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                            "description": "ID of the track"
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Stereo acoustic metrics data",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/StereoMetricsResponse"
                                    }
                                }
                            }
                        },
                        "404": {
                            "description": "Track or metrics report not found"
                        }
                    }
                }
            },
            "/karaoke/{track_id}/": {
                "get": {
                    "tags": ["Stems & Karaoke"],
                    "summary": "Get vocal and instrumental stems",
                    "description": "Generates or retrieves separated vocal and backing track audio URLs.",
                    "parameters": [
                        {
                            "name": "track_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"}
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Separated stems audio URLs",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "vocals_url": {"type": "string", "format": "uri"},
                                            "instrumental_url": {"type": "string", "format": "uri"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "/edit/{track_id}/": {
                "patch": {
                    "tags": ["Library & Tracks"],
                    "summary": "Edit track metadata",
                    "description": "Updates track title, artist, or tags.",
                    "parameters": [
                        {"name": "track_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                    ],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "title": {"type": "string"},
                                        "artist": {"type": "string"}
                                    }
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Track updated successfully"
                        }
                    }
                }
            },
            "/delete/{track_id}/": {
                "delete": {
                    "tags": ["Library & Tracks"],
                    "summary": "Delete track",
                    "description": "Deletes track record and removes source and processed files from disk.",
                    "parameters": [
                        {"name": "track_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                    ],
                    "responses": {
                        "200": {
                            "description": "Track deleted successfully"
                        }
                    }
                }
            },
            "/api/like/{track_id}/": {
                "post": {
                    "tags": ["Library & Tracks"],
                    "summary": "Toggle track like status",
                    "parameters": [
                        {"name": "track_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                    ],
                    "responses": {
                        "200": {
                            "description": "Like state updated",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "is_liked": {"type": "boolean"},
                                            "liked_count": {"type": "integer"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "/api/play/{track_id}/": {
                "post": {
                    "tags": ["Library & Tracks"],
                    "summary": "Record audio play event",
                    "parameters": [
                        {"name": "track_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                    ],
                    "responses": {
                        "200": {
                            "description": "Play event recorded",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "play_count": {"type": "integer"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "components": {
            "schemas": {
                "TrackUploadResponse": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer", "example": 42},
                        "title": {"type": "string", "example": "Cyberpunk Sunset"},
                        "artist": {"type": "string", "example": "Synth Master"},
                        "duration": {"type": "number", "example": 184.2},
                        "bpm": {"type": "number", "example": 128.0},
                        "musical_key": {"type": "string", "example": "C Minor"},
                        "spectral_centroid": {"type": "number", "example": 3200.5},
                        "cover_url": {"type": "string", "nullable": True},
                        "status": {"type": "string", "example": "pending"}
                    }
                },
                "ProcessTrackRequest": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "example": "Cyberpunk Sunset (Remastered)"},
                        "artist": {"type": "string", "example": "Synth Master"},
                        "mode": {
                            "type": "string",
                            "enum": ["ai", "stealth", "dsp", "hybrid", "direct", "restoration"],
                            "default": "ai",
                            "description": "Target pipeline mode"
                        },
                        "engine": {
                            "type": "string",
                            "enum": ["stealth", "audiosr", "apollo", "flowhigh"],
                            "default": "audiosr",
                            "description": "AI generative engine"
                        },
                        "format": {
                            "type": "string",
                            "enum": ["wav", "flac", "mp3", "ogg", "m4a", "opus"],
                            "default": "wav"
                        },
                        "sample_rate": {
                            "type": "integer",
                            "enum": [44100, 48000, 96000],
                            "default": 48000
                        },
                        "bitrate": {
                            "type": "string",
                            "default": "320k",
                            "example": "320k"
                        },
                        "quality_preset": {
                            "type": "string",
                            "enum": ["fast", "balanced", "high", "custom"],
                            "default": "balanced"
                        },
                        "steps": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 200,
                            "default": 50
                        },
                        "guidance": {
                            "type": "number",
                            "minimum": 1.0,
                            "maximum": 15.0,
                            "default": 3.5
                        },
                        "seed": {
                            "type": "integer",
                            "default": 42
                        },
                        "batch_size": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 8,
                            "default": 2
                        },
                        "dsp_preset": {
                            "type": "string",
                            "enum": [
                                "mastering", "vocal_polish", "club_bass", "broadcast",
                                "tape_warmth", "natural_air", "music_fix", "audio_repair",
                                "deep_bass", "clear", "warm", "punchy", "stealth"
                            ],
                            "default": "mastering"
                        },
                        "crossover_freq": {
                            "type": "number",
                            "minimum": 10000.0,
                            "maximum": 20000.0,
                            "default": 15500.0,
                            "description": "Pro-Q 3 Crossover split frequency (Hz)"
                        },
                        "mud_cut_db": {
                            "type": "number",
                            "minimum": -12.0,
                            "maximum": 0.0,
                            "default": -1.5,
                            "description": "Pro-Q 3 De-Mud Notch gain at 350 Hz (dB)"
                        },
                        "stereo_width": {
                            "type": "number",
                            "minimum": 0.0,
                            "maximum": 2.0,
                            "default": 1.0
                        },
                        "bass_boost": {
                            "type": "number",
                            "minimum": -10.0,
                            "maximum": 10.0,
                            "default": 0.0
                        },
                        "voice_clarity": {
                            "type": "number",
                            "minimum": -5.0,
                            "maximum": 10.0,
                            "default": 0.0
                        },
                        "compressor_amount": {
                            "type": "number",
                            "minimum": 0.0,
                            "maximum": 1.0,
                            "default": 0.5
                        },
                        "reverb_enabled": {
                            "type": "boolean",
                            "default": False
                        },
                        "reverb_size": {
                            "type": "number",
                            "minimum": 0.0,
                            "maximum": 1.0,
                            "default": 0.5
                        },
                        "reverb_amount": {
                            "type": "number",
                            "minimum": 0.0,
                            "maximum": 1.0,
                            "default": 0.3
                        }
                    }
                },
                "TrackSummary": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "title": {"type": "string"},
                        "artist": {"type": "string"},
                        "status": {"type": "string"},
                        "duration": {"type": "number"},
                        "created_at": {"type": "string", "format": "date-time"},
                        "cover_url": {"type": "string", "nullable": True},
                        "is_liked": {"type": "boolean"}
                    }
                },
                "StereoMetricsResponse": {
                    "type": "object",
                    "properties": {
                        "si_sdr": {"type": "number", "example": 18.4},
                        "pesq": {"type": "number", "example": 3.85},
                        "lsd": {"type": "number", "example": 1.12},
                        "left_channel": {
                            "type": "object",
                            "properties": {
                                "peak_original": {"type": "number", "example": 0.89},
                                "peak_processed": {"type": "number", "example": 0.94},
                                "rms_original": {"type": "number", "example": 0.22},
                                "rms_processed": {"type": "number", "example": 0.28}
                            }
                        },
                        "right_channel": {
                            "type": "object",
                            "properties": {
                                "peak_original": {"type": "number", "example": 0.88},
                                "peak_processed": {"type": "number", "example": 0.93},
                                "rms_original": {"type": "number", "example": 0.21},
                                "rms_processed": {"type": "number", "example": 0.27}
                            }
                        },
                        "stereo": {
                            "type": "object",
                            "properties": {
                                "correlation": {"type": "number", "example": 0.78},
                                "mid_rms": {"type": "number", "example": 0.32},
                                "side_rms": {"type": "number", "example": 0.14},
                                "width_ratio": {"type": "number", "example": 0.44}
                            }
                        }
                    }
                }
            }
        }
    }
