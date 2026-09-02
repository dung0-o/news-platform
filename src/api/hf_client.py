"""Hugging Face inference client for sentiment scoring."""

from __future__ import annotations

import structlog
import httpx
from config import settings

logger = structlog.get_logger(__name__)


HF_BASE_URL = "https://router.huggingface.co/hf-inference/models"


def query_sentiment(text: str) -> dict | None:
    """Call Hugging Face inference API and return sentiment score.

    Returns the model's output as a float between -1 and 1.
    """
    client = httpx.Client(timeout=30.0)

    try:
        resp = client.post(
            f"{HF_BASE_URL}/{settings.huggingface_model_id}",
            json={"inputs": text},
            headers={
                "Authorization": f"Bearer {settings.huggingface_api_key}",
                "Content-Type": "application/json",
            },
        )
        resp.raise_for_status()
        result = resp.json()

        # Some models return a list; some return a dict with "score"
        if isinstance(result, list) and len(result) > 0:
            predictions = result[0]
            if isinstance(predictions, list) and len(predictions) > 0:
                score = predictions[0]["score"]
            elif isinstance(predictions, dict):
                score = predictions.get("score")
            else:
                score = float(predictions)
        elif isinstance(result, dict):
            score = result.get("score")
        else:
            raise ValueError(f"Unexpected Hugging Face response format: {result}")

        if score is None:
            logger.warning("Hugging Face returned no score", text_preview=text[:50])
            return None

        return float(score)

    except httpx.HTTPStatusError as exc:
        logger.error("Hugging Face HTTP error", status=exc.response.status_code)
        raise
    except httpx.RequestError as exc:
        logger.error("Hugging Face request error", error=str(exc))
        raise
    except Exception as exc:
        logger.error("Hugging Face error", error=str(exc))
        raise


def health_check() -> bool:
    """Verify the Hugging Face model endpoint is reachable."""
    try:
        client = httpx.Client(timeout=10.0)
        resp = client.get(
            f"{HF_BASE_URL}/{settings.huggingface_model_id}",
            headers={"Authorization": f"Bearer {settings.huggingface_api_key}"},
        )
        return resp.status_code in (200, 405)  # 405 = model loading, is OK
    except Exception:
        return False
