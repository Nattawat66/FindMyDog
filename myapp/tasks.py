import requests
import jwt
from django.conf import settings
from datetime import datetime, timedelta

def generate_jwt():
    payload = {
        "iss": "django",
        "scope": "auto_retrain",
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(minutes=5),
    }
    token = jwt.encode(payload, settings.AUTO_TRAIN_SECRET, algorithm="HS256")
    return token

def retrain_model():
    print(" Django Task: Sending command to FastAPI...")

    token = generate_jwt()
    headers = {
        "Authorization": f"Bearer {token}"
    }

    fastapi_url = "http://localhost:8000/retrain-model-face"
 
    try:
        response = requests.post(fastapi_url, headers=headers, timeout=5)
        print("FastAPI Status:", response.status_code)

        if response.status_code == 200:
            print(" Django Task: FastAPI accepted token.")
        else:
            print(" Django Task: FastAPI rejected token", response.text)

    except Exception as e:
        print("Django Task: Connection failed", e)
