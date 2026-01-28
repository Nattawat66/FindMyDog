import requests
import logging
import base64

from django.http import JsonResponse
from .models import DogImage

logger = logging.getLogger(__name__)

FASTAPI_BASE_URL = "http://127.0.0.1:8001"
TRAIN_ENDPOINT = "/TRAIN-KNN02/"


def trainKNN():
    """
    เรียก FastAPI เพื่อ train KNN จาก embeddings ใน DogImage
    """

    # 1. ดึงรูปที่มี embedding
    images = DogImage.objects.exclude(embedding_binary__isnull=True)

    train_data = []

    for img in images:
        embedding_b64 = base64.b64encode(
            img.embedding_binary
        ).decode("utf-8")

        train_data.append({
            "dog_id": img.dog_id,
            "embedding_b64": embedding_b64
        })

    if not train_data:
        return JsonResponse(
            {"status": "error", "message": "ไม่มี embedding ในฐานข้อมูล"},
            status=400
        )

    url = FASTAPI_BASE_URL + TRAIN_ENDPOINT

    try:
        response = requests.post(
            url,
            json={"data": train_data},
            timeout=300
        )

        if response.status_code != 200:
            logger.error(f"Train KNN failed: {response.status_code} {response.text}")
            return JsonResponse(
                {
                    "status": "error",
                    "code": response.status_code,
                    "detail": response.text
                },
                status=response.status_code
            )

        logger.info("Train KNN success")
        return JsonResponse(response.json(), status=200)

    except requests.exceptions.RequestException as e:
        logger.exception("Cannot connect to FastAPI")
        return JsonResponse(
            {
                "status": "error",
                "detail": str(e)
            },
            status=500
        )
