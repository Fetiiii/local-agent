# config.py - Now just a proxy to backend.core.settings

from backend.core.settings import settings

# Proxy variables for backward compatibility
MODEL_NAME = settings.model_name
VISION_MODEL = settings.vision_model
RETRY_COUNT = settings.retry_count
MAX_STEPS = settings.max_steps
