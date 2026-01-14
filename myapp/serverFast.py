import requests
import logging

logger = logging.getLogger(__name__)

FASTAPI_BASE_URL = "http://127.0.0.1:8001"  # แก้ตามที่คุณรัน fastapi
TRAIN_ENDPOINT = "/TRAIN-KNN02/"

def trainKNN():
    """
    เรียก FastAPI เพื่อ train KNN จาก embeddings ใน DogImage
    """
    url = FASTAPI_BASE_URL + TRAIN_ENDPOINT

    try:
        resp = requests.post(url, timeout=300)

        if resp.status_code != 200:
            logger.error(f"Train KNN failed: {resp.status_code} {resp.text}")
            return {
                "status": "error",
                "code": resp.status_code,
                "detail": resp.text
            }

        data = resp.json()
        logger.info(f"Train KNN success: {data}")

        return data

    except requests.exceptions.RequestException as e:
        logger.exception("Cannot connect to FastAPI")
        return {
            "status": "error",
            "detail": str(e)
        }

