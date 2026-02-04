from flask import (
    Blueprint,
    request,
    jsonify,
    send_from_directory,
    current_app,
    render_template,
)
from app.models import db, Track
from app.services.upscaler import upscaler
from app.services.metadata import extract_metadata
from werkzeug.utils import secure_filename
import os
import json
import threading

main = Blueprint("main", __name__)

ALLOWED_EXTENSIONS = {"mp3", "wav", "flac", "ogg", "m4a"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@main.route("/")
def index():
    return render_template("index.html")


@main.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        save_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
        file.save(save_path)

        # Extract metadata
        static_covers_dir = os.path.join(current_app.root_path, "static", "covers")
        os.makedirs(static_covers_dir, exist_ok=True)
        meta = extract_metadata(save_path, static_covers_dir)

        new_track = Track(
            filename=filename,
            original_path=save_path,
            status="pending",
            title=meta.get("title"),
            artist=meta.get("artist"),
            cover_path=meta.get("cover_path"),
        )
        db.session.add(new_track)
        db.session.commit()

        return jsonify(new_track.to_dict()), 201
    return jsonify({"error": "File type not allowed"}), 400


def run_upscaling(
    app,
    track_id,
    format,
    sample_rate,
    bitrate,
    steps,
    guidance,
    seed,
    batch_size,
    mode,
    dsp_preset,
    dsp_params,
):
    with app.app_context():
        track = db.session.get(Track, track_id)
        if not track:
            return

        track.status = "processing"
        track.target_format = format
        track.target_sample_rate = sample_rate
        track.target_bitrate = bitrate
        db.session.commit()

        try:
            # Generate output filename
            base, _ = os.path.splitext(track.filename)
            if mode == "dsp":
                suffix = "_dsp"
            elif mode == "hybrid":
                suffix = "_hybrid"
            elif mode == "restoration":
                suffix = "_restored"
            else:
                suffix = "_ai"
            output_filename = f"{base}{suffix}.{format}"
            output_path = os.path.join(
                current_app.config["PROCESSED_FOLDER"], output_filename
            )

            # Run upscaling
            upscaler.process_track(
                track.original_path,
                output_path,
                mode=mode,
                target_format=format,
                target_sample_rate=sample_rate,
                target_bitrate=bitrate,
                ddim_steps=steps,
                guidance_scale=guidance,
                seed=seed,
                batch_size=batch_size,
                dsp_preset=dsp_preset,
                dsp_params=dsp_params,
            )

            track.processed_path = output_path
            track.status = "completed"
            db.session.commit()
        except Exception as e:
            track.status = "failed"
            db.session.commit()
            print(f"Error processing track {track_id}: {e}")


@main.route("/process/<int:track_id>", methods=["POST"])
def process_track(track_id):
    track = db.session.get(Track, track_id)
    if not track:
        return jsonify({"error": "Track not found"}), 404

    if track.status == "processing":
        return jsonify({"error": "Track is already being processed"}), 400

    data = request.get_json() or {}
    target_format = data.get("format", "wav")
    target_sample_rate = int(data.get("sample_rate", 48000))
    target_bitrate = data.get("bitrate", "320k")

    # New parameters
    steps = int(data.get("steps", 50))
    guidance = float(data.get("guidance", 3.5))
    seed = int(data.get("seed", 42))
    batch_size = int(data.get("batch_size", 2))
    mode = data.get("mode", "ai")
    dsp_preset = data.get("dsp_preset", "mastering")

    # DSP Params
    dsp_params = {
        "reverb_enabled": data.get("reverb_enabled"),
        "reverb_size": (
            float(data.get("reverb_size", 0.5))
            if data.get("reverb_size") is not None
            else None
        ),
        "reverb_amount": (
            float(data.get("reverb_amount", 0.3))
            if data.get("reverb_amount") is not None
            else None
        ),
        "bass_boost": (
            float(data.get("bass_boost", 0.0))
            if data.get("bass_boost") is not None
            else None
        ),
        "voice_clarity": (
            float(data.get("voice_clarity", 0.0))
            if data.get("voice_clarity") is not None
            else None
        ),
        "compressor_amount": (
            float(data.get("compressor_amount", 0.5))
            if data.get("compressor_amount") is not None
            else None
        ),
        "stereo_width": (
            float(data.get("stereo_width", 1.0))
            if data.get("stereo_width") is not None
            else None
        ),
    }

    # Start processing in a separate thread
    thread = threading.Thread(
        target=run_upscaling,
        args=(
            current_app._get_current_object(),
            track_id,
            target_format,
            target_sample_rate,
            target_bitrate,
            steps,
            guidance,
            seed,
            batch_size,
            mode,
            dsp_preset,
            dsp_params,
        ),
    )
    thread.start()

    return jsonify({"message": "Processing started", "track": track.to_dict()}), 202


@main.route("/library", methods=["GET"])
def get_library():
    tracks = Track.query.order_by(Track.created_at.desc()).all()
    return jsonify([track.to_dict() for track in tracks])


@main.route("/delete/<int:track_id>", methods=["DELETE"])
def delete_track(track_id):
    track = db.session.get(Track, track_id)
    if not track:
        return jsonify({"error": "Track not found"}), 404

    # Delete files
    if os.path.exists(track.original_path):
        os.remove(track.original_path)
    if track.processed_path and os.path.exists(track.processed_path):
        os.remove(track.processed_path)
    if track.cover_path:
        # cover_path is 'static/covers/...'
        full_cover_path = os.path.join(current_app.root_path, track.cover_path)
        if os.path.exists(full_cover_path):
            os.remove(full_cover_path)

    db.session.delete(track)
    db.session.commit()
    return jsonify({"message": "Track deleted"}), 200


@main.route("/edit/<int:track_id>", methods=["PATCH"])
def edit_track(track_id):
    track = db.session.get(Track, track_id)
    if not track:
        return jsonify({"error": "Track not found"}), 404

    data = request.get_json()
    if "title" in data:
        track.title = data["title"]
    if "artist" in data:
        track.artist = data["artist"]

    db.session.commit()
    return jsonify(track.to_dict()), 200


@main.route("/uploads/<path:filename>")
def serve_uploaded_file(filename):
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)


@main.route(
    "/library_files/<path:filename>"
)  # Renamed to avoid confusion with /library route
def serve_processed_file(filename):
    response = send_from_directory(current_app.config["PROCESSED_FOLDER"], filename)
    # Disable caching to prevent stale Range requests (416) if file is rewritten
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@main.route("/favicon.ico")
def favicon():
    return "", 204


@main.route("/metrics/<int:track_id>", methods=["GET"])
def get_track_metrics(track_id):
    track = db.session.get(Track, track_id)
    if not track or not track.processed_path:
        return jsonify({"error": "Track metrics not found"}), 404

    # Construct expected metrics path: debug_output/{filename_no_ext}_metrics.json
    # processed_path is full absolute path
    base_name = os.path.basename(track.processed_path).rsplit(".", 1)[0]

    # Resolve debug_output relative to project root
    # current_app.root_path is .../app
    project_root = os.path.dirname(current_app.root_path)
    metrics_dir = os.path.join(project_root, "debug_output")
    metrics_path = os.path.join(metrics_dir, f"{base_name}_metrics.json")

    print(f"DEBUG: Looking for metrics at {metrics_path}")

    if os.path.exists(metrics_path):
        try:
            with open(metrics_path, "r") as f:
                data = json.load(f)
            return jsonify(data)
        except Exception as e:
            return jsonify({"error": f"Failed to read metrics: {str(e)}"}), 500
    else:
        # Fallback: List directory to help debug
        try:
            files = (
                os.listdir(metrics_dir)
                if os.path.exists(metrics_dir)
                else "Dir not found"
            )
            print(f"DEBUG: Files in debug_output: {files}")
        except:
            pass
        return jsonify({"error": f"Metrics file not found at {metrics_path}"}), 404
