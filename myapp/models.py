from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings

class User(AbstractUser):
    phone = models.CharField(max_length=20, blank=True, null=True)
    line_id = models.CharField(max_length=50, blank=True, null=True)

    # Location สำหรับ broadcast
    location_lat = models.FloatField(blank=True, null=True)
    location_lng = models.FloatField(blank=True, null=True)

    # Role ของ user
    ROLE_CHOICES = [
        ('user', 'สมาชิก'),
        # ('adoptive_parents', 'พ่อแม่บุญธรรม'),
        ('org_admin', 'แอดมินองค์กร'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='user')

    def __str__(self):
        return f"{self.username} ({self.role})"
    

class Dog(models.Model):
    GENDER_CHOICES = [
        ('M', 'Male (ตัวผู้)'),
        ('F', 'Female (ตัวเมีย)'),
    ]
    SIZE_CHOICES = [
        ('ES', 'Extra Small (เล็กมาก)'), 
        ('S', 'Small (เล็ก)'), 
        ('M', 'Medium (กลาง)'),
        ('L', 'Large (ใหญ่)'),
        ('XL', 'Extra Large (ใหญ่มาก)'),
        ('XXL', 'XX Extra Large (ใหญ่พิเศษ)'),
    ]

    
    is_lost = models.BooleanField(default=False,verbose_name="สุนัขหาย")
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=100 ,verbose_name="ชื่อสุนัข")
    gender = models.CharField(max_length=1, null=True,choices=GENDER_CHOICES, verbose_name="เพศ")
    age = models.PositiveIntegerField(blank=True, null=True,verbose_name="อายุ")
    # breed = models.CharField(max_length=100, null=True, verbose_name="สายพันธุ์")
    personality = models.TextField(blank=True, null=True,verbose_name="นิสัยของสุนัข")
    favorite_food = models.TextField(blank=True, null=True,verbose_name="อาหารโปรด")
    allergies = models.TextField(blank=True, null=True,verbose_name="อาหารที่แพ้")
    
    # --- 2. ลักษณะทางกายภาพ ---
    primary_color = models.CharField(max_length=50, null=True, verbose_name="สีหลัก")
    secondary_color = models.CharField(max_length=50, blank=True, null=True, verbose_name="สีรอง")
    
    
    #-- 3. รายละเอียดสุนัขโฮงเกลือหมา#
    organization = models.BooleanField(default=False,null=True,verbose_name="อยู่ในการดูแลของโฮงเกลือหมาหรือไม่")
    
    vaccination_history = models.CharField(
        max_length=255, 
        blank=True, 
        default='', 
        verbose_name="รายการวัคซีนที่ฉีดแล้ว",
        help_text="กรอกชื่อวัคซีนที่ฉีดแล้ว โดยคั่นด้วยเครื่องหมายคอมมา (เช่น DHPPL, Rabies)"
    )
    
    STERILIZATION_CHOICES = [
        ('NO', 'ยังไม่ทำ/ไม่ได้คุมกำเนิด'),
        ('SURGICAL', 'ทำหมันถาวร (ผ่าตัด)'),
        ('CHEMICAL', 'คุมกำเนิดชั่วคราว (เช่น ฉีดยาคุม)'),
    ]

    sterilization_status = models.CharField(
        max_length=10,
        choices=STERILIZATION_CHOICES,
        default='NO',
        verbose_name="สถานะการควบคุมกำเนิด",
        help_text="ระบุว่าสุนัขได้ทำหมันหรือคุมกำเนิดแบบใด"
    )
    
    # ฟิลด์สำหรับเก็บวัน/เดือน/ปี ที่ทำหมัน/คุมกำเนิดล่าสุด (ทางเลือก)
    sterilization_date = models.DateField(
        null=True, 
        blank=True, 
        verbose_name="วันที่ทำหมัน/คุมกำเนิดล่าสุด",
        help_text="ระบุวันที่ดำเนินการล่าสุด"
    )
    
    size = models.CharField(max_length=3, null=True,choices=SIZE_CHOICES, verbose_name="ขนาด")
    distinguishing_marks = models.TextField(blank=True, verbose_name="ลักษณะ/รอยตำหนิเด่น")
    
    
    lost_latitude = models.DecimalField(
        max_digits=9, 
        decimal_places=6, 
        null=True, 
        blank=True, 
        verbose_name="ละติจูด (Latitude)"
    )
    lost_longitude = models.DecimalField(
        max_digits=9, 
        decimal_places=6, 
        null=True, 
        blank=True, 
        verbose_name="ลองจิจูด (Longitude)"
    )
    lost_location_description = models.CharField(
        max_length=255, 
        null=True, 
        blank=True, 
        verbose_name="รายละเอียดสถานที่สูญหาย"
    )

    def __str__(self):
        return self.name


class DogImage(models.Model):
    dog = models.ForeignKey(Dog, related_name="images", on_delete=models.CASCADE)
    image = models.ImageField(upload_to="dog_images/")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    embedding_binary = models.BinaryField(blank=True, null=True)  # เก็บ vector แบบ binary


class LostDogReport(models.Model):
    dog = models.ForeignKey(Dog, on_delete=models.CASCADE)
    reported_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    location_lat = models.FloatField()
    location_lng = models.FloatField()
    description = models.TextField(blank=True, null=True)
    reported_at = models.DateTimeField(auto_now_add=True)
    is_found = models.BooleanField(default=False)


class FoundDogReport(models.Model):
    reported_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    location_lat = models.FloatField()
    location_lng = models.FloatField()
    description = models.TextField(blank=True, null=True)
    reported_at = models.DateTimeField(auto_now_add=True)


class FoundDogImage(models.Model):
    report = models.ForeignKey(FoundDogReport, related_name="images", on_delete=models.CASCADE)
    image = models.ImageField(upload_to="found_dogs/")
    uploaded_at = models.DateTimeField(auto_now_add=True)



class Notification(models.Model):
    # ประเภทของการแจ้งเตือน (อิงตามที่คุณต้องการ)
    NOTIFICATION_TYPES = [
        ('ACTIVITY', 'กิจกรรมองค์กร/ทั่วไป'),
        ('DOG_SPECIFIC', 'ประกาศเฉพาะสุนัข'),
        ('LOST_DOG', 'สุนัขสูญหาย'),
    ]

    title = models.CharField(max_length=200, verbose_name="หัวข้อข่าวสาร")
    content = models.TextField(verbose_name="รายละเอียดเนื้อหา")
    notification_type = models.CharField(
        max_length=20, 
        choices=NOTIFICATION_TYPES, 
        default='ACTIVITY', 
        verbose_name="ประเภทข่าวสาร"
    )
    is_important = models.BooleanField(default=False, verbose_name="สำคัญมาก")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="วันที่สร้าง")
    
    # รูปภาพประกอบ (ถ้ามี)
    image = models.ImageField(
        upload_to='notifications/', 
        null=True, 
        blank=True, 
        verbose_name="รูปภาพประกอบ"
    )

    # 💡 [Foreign Key] เชื่อมกับ Dog: ใช้สำหรับประเภท DOG_SPECIFIC และ LOST_DOG
    dog = models.ForeignKey(
        Dog, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='notifications',
        verbose_name="สุนัขที่เกี่ยวข้อง"
    )
    
    # 💡 [Foreign Key] องค์กรที่สร้าง (ถ้าต้องการรู้ว่าใครประกาศ)
    organization = models.ForeignKey(
        settings.AUTH_USER_MODEL, # สมมติว่า Admin เป็น User
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        limit_choices_to={'role': 'org_admin'},
        verbose_name="องค์กรผู้ประกาศ"
    )
    
    # สถานะ (อ่านแล้ว/ยังไม่อ่าน) - จัดการใน Model แยกก็ได้ แต่ตอนนี้ใช้แบบง่ายไปก่อน
    # is_read = models.BooleanField(default=False) 

    class Meta:
        ordering = ['-created_at']
        verbose_name = "ข่าวสาร/การแจ้งเตือน"

    def __str__(self):
        return f"[{self.get_notification_type_display()}] {self.title}"
    
    
class AdoptionParent(models.Model):
    # 💡 [Foreign Key] ผู้ใช้ที่เป็นพ่อแม่บุญธรรม
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='adopted_dogs',
        verbose_name="พ่อแม่บุญธรรม"
    )
    
    # 💡 [Foreign Key] สุนัขที่รับเป็นบุญธรรม
    dog = models.ForeignKey(
        Dog, 
        on_delete=models.CASCADE, 
        related_name='adoption_parents',
        verbose_name="สุนัข"
    )

    adoption_date = models.DateField(auto_now_add=True, verbose_name="วันที่รับดูแล")
    
    class Meta:
        # กำหนดให้ User คนเดียวเป็นพ่อแม่บุญธรรมของ Dog ตัวเดิมได้ครั้งเดียว
        unique_together = ('user', 'dog') 
        verbose_name = "พ่อแม่บุญธรรม"
        
    def __str__(self):
        return f"{self.user.username} เป็นพ่อแม่บุญธรรมของ {self.dog.name}"

class TrainingConfig(models.Model):

    scheduled_time = models.CharField(max_length=5, default="00:00", help_text="Format: HH:MM (24h)")
    
    # เก็บความถี่
    frequency = models.CharField(max_length=10, choices=[
        ('daily', 'รายวัน'),
        ('weekly', 'รายสัปดาห์'),
        ('monthly', 'รายเดือน'),
    ], default='daily')
    
    # เก็บสถานะว่าเปิดใช้งานการตั้งเวลาอยู่หรือไม่
    is_active = models.BooleanField(default=True)
    
    # เก็บเวลาที่มีการแก้ไขข้อมูลล่าสุด
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Schedule at: {self.scheduled_time} (Active: {self.is_active})"

    class Meta:
        verbose_name = "Training Configuration"
        verbose_name_plural = "Training Configurations"


class AdoptionRequest(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'รอการตรวจสอบ'),
        ('APPROVED', 'อนุมัติ'),
        ('REJECTED', 'ปฏิเสธ'),
    ]
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='adoption_requests',
        verbose_name="ผู้ขออุปการะ"
    )
    dog = models.ForeignKey(
        Dog, 
        on_delete=models.CASCADE, 
        related_name='adoption_requests',
        verbose_name="สุนัข"
    )
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='PENDING',
        verbose_name="สถานะคำขอ"
    )
    request_reason = models.TextField(
        blank=True, 
        null=True, 
        verbose_name="เหตุผลความต้องการ"
    )
    admin_feedback = models.TextField(
        blank=True, 
        null=True, 
        verbose_name="เหตุผลจากแอดมิน"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="วันที่ส่งคำขอ")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "คำขอเป็นพ่อแม่บุญธรรม"
        
    def __str__(self):
        return f"คำขอจาก {self.user.username} เพื่อรับเลี้ยง {self.dog.name} ({self.get_status_display()})"
        
class KNNTrainingResult(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    tsne_image = models.ImageField(upload_to="knn/tsne/")
    knn_matrix_image = models.ImageField(upload_to="knn/matrix/")
    count = models.IntegerField()
    accuracy = models.FloatField()
    model_name = models.CharField(max_length=255, default="unknown", verbose_name="ชื่อ Model ที่ใช้")  
