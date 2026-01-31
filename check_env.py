import torch
import sys
import logging
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("system.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

def check_environment():
    logging.info("Starting environment check...")

    # Check Python version
    logging.info(f"Python version: {sys.version}")

    # Check matplotlib
    try:
        import matplotlib
        logging.info(f"matplotlib version: {matplotlib.__version__}")
    except ImportError:
        logging.error("matplotlib is NOT installed! This is required for AudioSR.")

    # Check PyTorch
    try:
        logging.info(f"PyTorch version: {torch.__version__}")

        if torch.cuda.is_available():
            logging.info("CUDA is available!")
            logging.info(f"Device count: {torch.cuda.device_count()}")
            logging.info(f"Current device: {torch.cuda.current_device()}")
            logging.info(f"Device name: {torch.cuda.get_device_name(0)}")
        else:
            logging.warning("CUDA is NOT available. Falling back to CPU. Processing will be slow.")
            logging.info("Diagnostics:")
            try:
                logging.info(f"  torch.version.cuda: {torch.version.cuda}")
            except:
                logging.info("  torch.version.cuda: Not available")

            logging.info(f"  torch.backends.cudnn.enabled: {torch.backends.cudnn.enabled}")

            if sys.platform == "win32":
                logging.info("  NOTE: On Windows, ensure you have installed the CUDA-enabled version of PyTorch.")
                logging.info("  If using Poetry, ensure check your pyproject.toml has the correct source configured.")

    except Exception as e:
        logging.error(f"Error checking PyTorch/CUDA: {e}")

    logging.info("Environment check complete.")

if __name__ == "__main__":
    check_environment()
