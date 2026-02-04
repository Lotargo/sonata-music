import os
import warnings

# Suppress warnings
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
# Suppress pkg_resources deprecation warning
warnings.filterwarnings("ignore", message=".*pkg_resources is deprecated.*")
# Suppress huggingface_hub resume_download warning
warnings.filterwarnings("ignore", category=FutureWarning, module="huggingface_hub")

from app import create_app
import logging

# Configure werkzeug logging to ERROR only (suppress INFO requests)
log = logging.getLogger("werkzeug")
log.setLevel(logging.ERROR)

app = create_app()

if __name__ == "__main__":
    # Disable reloader to prevent server restart during processing
    # when internal libraries like resampy access files.
    logging.getLogger(__name__).info("Server starting on http://0.0.0.0:5000")
    app.run(debug=True, use_reloader=False, host="0.0.0.0", port=5000)
