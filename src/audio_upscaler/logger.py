import logging
import torch

def setup_logger():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger("audio-upscaler")

    if torch.cuda.is_available():
        logger.info("CUDA detected! Using GPU for processing.")
    else:
        logger.warning("CUDA NOT detected! Falling back to CPU. Processing will be slow.")

    return logger

logger = setup_logger()
