import requests
import jwt
import os
from django.conf import settings
from datetime import datetime, timedelta
# สมมติว่า Model ของคุณชื่อ DogImage
from .models import DogImage 

def generate_jwt():
    payload = {
        "iss": "django",
        "scope": "auto_retrain",
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(minutes=10), # เพิ่มเวลาเป็น 10 นาทีสำหรับการเทรน
    }
    return jwt.encode(payload, settings.AUTO_TRAIN_SECRET, algorithm="HS256")
    
def retrain_model():
    print("--- Django Task: Preparing Data for FastAPI ---")

    # 1. ดึงข้อมูลจาก Database
    # สมมติว่าเก็บชื่อไฟล์ไว้ใน image และ ID สุนัขใน dog_id
    queryset = DogImage.objects.all()
    
    if not queryset.exists():
        print("Django Task: No data found in database.")
        return

    # 2. สร้าง Payload ข้อมูล
    training_data = []
    for item in queryset:
        # ส่ง Path เต็มของรูปภาพไปให้ FastAPI
        full_path = os.path.join(settings.MEDIA_ROOT, str(item.image))
        training_data.append({
            "image_path": full_path,
            "label": item.dog_id  # หรือ item.name
        })

    token = generate_jwt()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    fastapi_url = settings.FASTAPI_BASE_URL
    
    # 3. ส่ง POST request พร้อมข้อมูล training_data
    try:
        payload = {
            "data": training_data,
            "model_type": "resnet"
        }
        
        # เพิ่ม timeout เพราะการเทรนอาจใช้เวลานาน (หรือใช้ Background Task ใน FastAPI)
        response = requests.post(fastapi_url, json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            print(f"[Django] SUCCESS: {response.json().get('message')}")
        else:
            print(f"[Django] FAILED: FastAPI returned {response.status_code} - {response.text}")

    except Exception as e:
        print(f"Django Task: Connection failed - {e}")
