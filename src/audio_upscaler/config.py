import os
from dotenv import load_dotenv

load_dotenv()

LIBRARY_DIR = os.getenv("LIBRARY_DIR", "library")
UPLOAD_FOLDER = os.path.join(LIBRARY_DIR, "uploads")
PROCESSED_FOLDER = os.path.join(LIBRARY_DIR, "processed")

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {'mp3', 'wav', 'flac', 'ogg'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
