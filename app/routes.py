from flask import Blueprint, request, jsonify, send_from_directory, current_app
from app.models import db, Track
from app.services.upscaler import upscaler
from werkzeug.utils import secure_filename
import os
import threading

main = Blueprint('main', __name__)

ALLOWED_EXTENSIONS = {'mp3', 'wav', 'flac', 'ogg', 'm4a'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@main.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(save_path)

        new_track = Track(filename=filename, original_path=save_path, status='pending')
        db.session.add(new_track)
        db.session.commit()

        return jsonify(new_track.to_dict()), 201
    return jsonify({'error': 'File type not allowed'}), 400

def run_upscaling(app, track_id):
    with app.app_context():
        # Use session.get instead of Query.get (deprecated)
        track = db.session.get(Track, track_id)
        if not track:
            return

        track.status = 'processing'
        db.session.commit()

        try:
            # Generate output filename
            base, ext = os.path.splitext(track.filename)
            output_filename = f"{base}_upscaled.wav" # audiosr output is usually wav
            output_path = os.path.join(current_app.config['PROCESSED_FOLDER'], output_filename)

            # Run upscaling
            upscaler.process_track(track.original_path, output_path)

            track.processed_path = output_path
            track.status = 'completed'
            db.session.commit()
        except Exception as e:
            track.status = 'failed'
            db.session.commit()
            print(f"Error processing track {track_id}: {e}")

@main.route('/process/<int:track_id>', methods=['POST'])
def process_track(track_id):
    track = db.session.get(Track, track_id)
    if not track:
        return jsonify({'error': 'Track not found'}), 404

    # Start processing in a separate thread
    thread = threading.Thread(target=run_upscaling, args=(current_app._get_current_object(), track_id))
    thread.start()

    return jsonify({'message': 'Processing started', 'track': track.to_dict()}), 202

@main.route('/library', methods=['GET'])
def get_library():
    tracks = Track.query.order_by(Track.created_at.desc()).all()
    return jsonify([track.to_dict() for track in tracks])

@main.route('/uploads/<path:filename>')
def serve_uploaded_file(filename):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)

@main.route('/library/<path:filename>')
def serve_processed_file(filename):
    return send_from_directory(current_app.config['PROCESSED_FOLDER'], filename)
