import os
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from .config import UPLOAD_FOLDER, PROCESSED_FOLDER, ALLOWED_EXTENSIONS, allowed_file
from .upscaler import AudioUpscaler
from .logger import logger

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROCESSED_FOLDER'] = PROCESSED_FOLDER

# Global upscaler instance for lazy loading
_upscaler = None

def get_upscaler():
    global _upscaler
    if _upscaler is None:
        try:
            _upscaler = AudioUpscaler()
        except Exception as e:
            logger.error(f"Failed to initialize upscaler: {e}")
            raise
    return _upscaler

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        logger.info(f"File uploaded: {filename}")
        return jsonify({"message": "File uploaded successfully", "filename": filename}), 201
    else:
        return jsonify({"error": "File type not allowed"}), 400

@app.route('/api/upscale', methods=['POST'])
def upscale_file():
    data = request.json or {}
    if 'filename' not in data:
        return jsonify({"error": "Missing filename"}), 400

    filename = secure_filename(data['filename'])
    input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    if not os.path.exists(input_path):
        return jsonify({"error": f"File {filename} not found in uploads"}), 404

    ddim_steps = data.get('ddim_steps', 50)
    guidance_scale = data.get('guidance_scale', 3.5)

    try:
        upscaler = get_upscaler()
        output_path = upscaler.upscale(input_path, ddim_steps=ddim_steps, guidance_scale=guidance_scale)
        return jsonify({
            "message": "Upscaling complete",
            "processed_filename": os.path.basename(output_path)
        }), 200
    except Exception as e:
        logger.error(f"Upscaling failed for {filename}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/library', methods=['GET'])
def list_library():
    try:
        uploads = os.listdir(app.config['UPLOAD_FOLDER'])
        processed = os.listdir(app.config['PROCESSED_FOLDER'])
        return jsonify({
            "uploads": sorted(uploads),
            "processed": sorted(processed)
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/download/<string:folder_type>/<string:filename>', methods=['GET'])
def download_file(folder_type, filename):
    if folder_type == 'uploads':
        directory = app.config['UPLOAD_FOLDER']
    elif folder_type == 'processed':
        directory = app.config['PROCESSED_FOLDER']
    else:
        return jsonify({"error": "Invalid folder type. Use 'uploads' or 'processed'."}), 400

    filename = secure_filename(filename)
    if not os.path.exists(os.path.join(directory, filename)):
        return jsonify({"error": "File not found"}), 404

    return send_from_directory(directory, filename)

@app.route('/api/health', methods=['GET'])
def health_check():
    import torch
    return jsonify({
        "status": "healthy",
        "cuda_available": torch.cuda.is_available()
    }), 200

if __name__ == '__main__':
    # For local development
    app.run(host='0.0.0.0', port=5000, debug=False)
