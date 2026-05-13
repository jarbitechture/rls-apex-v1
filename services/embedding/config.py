"""embedding-service configuration."""
import os

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://bcc-ap-infer01:11434")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "mxbai-embed-large")
EMBED_DIM = 1024
HTTP_TIMEOUT_SECONDS = 10
BREAKER_FAILURE_THRESHOLD = 3
BREAKER_OPEN_SECONDS = 30
KEEP_ALIVE = os.environ.get("OLLAMA_KEEP_ALIVE", "24h")  # passed to Ollama per ADR-005
