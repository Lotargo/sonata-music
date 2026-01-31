import torch
import sys
import logging

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

    except Exception as e:
        logging.error(f"Error checking PyTorch/CUDA: {e}")

    logging.info("Environment check complete.")

if __name__ == "__main__":
    check_environment()
