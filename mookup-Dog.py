import os
import django
from django.core.files import File
from django.contrib.auth.models import User
import random

# ตั้งค่า Django Environment (เปลี่ยน 'your_project_name' เป็นชื่อโปรเจกต์ของคุณ)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'findmydog.settings')
django.setup()

from myapp.models import Dog, DogImage  # เปลี่ยน your_app_name เป็นชื่อแอปของคุณ

def run_mockup():
    print("--- Starting Mockup Data ---")
    
    # 1. ดึง User มาเป็นเจ้าของ (สมมติว่ามี user อยู่แล้วอย่างน้อย 1 คน)
    admin_user = User.objects.first()
    if not admin_user:
        print("Error: No User found. Please create a superuser first.")
        return

    # 2. ข้อมูล Mockup รายละเอียดสุนัข
    dogs_data = [
        {
            "folder_name": "Cooper",
            "name": "คูเปอร์",
            "gender": "M",
            "age": 3,
            "is_lost": False,
            "primary_color": "น้ำตาลเข้ม",
            "secondary_color": "ขาว",
            "size": "M",
            "personality": "ขี้เล่น เข้ากับคนง่าย ชอบวิ่งคาบบอล",
            "favorite_food": "เนื้อวัวอบแห้ง",
            "allergies": "ไก่",
            "distinguishing_marks": "มีปานสีดำที่ลิ้น หางขด",
            "organization": False
        },
        {
            "folder_name": "Luna",
            "name": "ลูน่า",
            "gender": "F",
            "age": 1,
            "is_lost": True,
            "primary_color": "ขาว",
            "secondary_color": "เทา",
            "size": "S",
            "personality": "เรียบร้อย ขี้อ้อน กลัวเสียงดัง",
            "favorite_food": "ปลาแซลมอน",
            "allergies": "-",
            "distinguishing_marks": "ตาคนละสี (ฟ้า-น้ำตาล)",
            "organization": True,
            "lost_location_description": "สวนสาธารณะหมู่บ้าน A"
        }
    ]

    base_path = 'data_mockup'  # ชื่อโฟลเดอร์หลักที่เก็บรูป

    for data in dogs_data:
        # สร้าง Object Dog
        dog = Dog.objects.create(
            owner=admin_user,
            name=data['name'],
            gender=data['gender'],
            age=data['age'],
            is_lost=data['is_lost'],
            primary_color=data['primary_color'],
            secondary_color=data['secondary_color'],
            size=data['size'],
            personality=data['personality'],
            favorite_food=data['favorite_food'],
            allergies=data['allergies'],
            distinguishing_marks=data['distinguishing_marks'],
            organization=data['organization'],
            lost_location_description=data.get('lost_location_description', '')
        )
        print(f"Created Dog: {dog.name}")

        # วนลูปเอารูปภาพจากโฟลเดอร์ตามชื่อ folder_name
        folder_path = os.path.join(base_path, data['folder_name'])
        
        if os.path.exists(folder_path):
            for filename in os.listdir(folder_path):
                if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                    img_path = os.path.join(folder_path, filename)
                    
                    # บันทึกรูปภาพลงใน DogImage model
                    with open(img_path, 'rb') as f:
                        dog_image = DogImage(dog=dog)
                        dog_image.image.save(filename, File(f), save=True)
                    print(f"  - Added image: {filename}")
        else:
            print(f"  - Warning: Folder {folder_path} not found.")

    print("--- Mockup Completed Successfully! ---")

if __name__ == '__main__':
    run_mockup()