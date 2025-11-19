from django.db.models.signals import post_delete, pre_delete
from django.dispatch import receiver
import os
from .models import DogImage


@receiver(pre_delete, sender=DogImage)
def delete_dog_image_file(sender, instance, **kwargs):
    """
    Signal handler ที่จะลบไฟล์รูปภาพจริงๆ ออกจากโฟลเดอร์
    เมื่อลบ DogImage object ออกจาก database
    
    ใช้ pre_delete แทน post_delete เพื่อให้แน่ใจว่าไฟล์ถูกลบก่อนที่ object จะถูกลบ
    และเรายังสามารถเข้าถึง instance.image ได้
    """
    if instance.image:
        try:
            # ตรวจสอบว่าไฟล์มีอยู่จริง
            if os.path.isfile(instance.image.path):
                os.remove(instance.image.path)
                # ลบโฟลเดอร์ว่างถ้ามี (optional)
                try:
                    directory = os.path.dirname(instance.image.path)
                    if os.path.exists(directory) and not os.listdir(directory):
                        os.rmdir(directory)
                except OSError:
                    pass  # ไม่ต้องลบโฟลเดอร์ถ้ามีไฟล์อื่นอยู่
        except Exception as e:
            # ถ้าลบไฟล์ไม่สำเร็จ ให้ log error (ใน production ควรใช้ logging)
            print(f"Error deleting image file {instance.image.path}: {e}")

