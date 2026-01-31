import os
import warnings

# Suppress warnings
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
# Suppress pkg_resources deprecation warning
warnings.filterwarnings("ignore", message=".*pkg_resources is deprecated.*")
# Suppress huggingface_hub resume_download warning
warnings.filterwarnings("ignore", category=FutureWarning, module="huggingface_hub")

from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
