from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    phone = models.CharField(max_length=20, blank=True, null=True)
    line_id = models.CharField(max_length=50, blank=True, null=True)

    # Location สำหรับ broadcast
    location_lat = models.FloatField(blank=True, null=True)
    location_lng = models.FloatField(blank=True, null=True)

    # Role ของ user
    ROLE_CHOICES = [
        ('user', 'สมาชิก'),
        ('adoptive_parents', 'พ่อแม่บุญธรรม'),
        ('org_admin', 'แอดมินองค์กร'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='user')

    def __str__(self):
        return f"{self.username} ({self.role})"
    

class Organization(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    contact_info = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return self.name


class Dog(models.Model):
    GENDER_CHOICES = [
        ('M', 'Male (ตัวผู้)'),
        ('F', 'Female (ตัวเมีย)'),
    ]
    SIZE_CHOICES = [
        ('S', 'Small (เล็ก)'),
        ('M', 'Medium (กลาง)'),
        ('L', 'Large (ใหญ่)'),
    ]
    
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    organization = models.ForeignKey(Organization, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=100 ,verbose_name="ชื่อสุนัข")
    gender = models.CharField(max_length=1, null=True,choices=GENDER_CHOICES, verbose_name="เพศ")
    age = models.PositiveIntegerField(blank=True, null=True,verbose_name="อายุ")
    breed = models.CharField(max_length=100, null=True, verbose_name="สายพันธุ์")
    personality = models.TextField(blank=True, null=True,verbose_name="นิสัยของสุนัข")
    favorite_food = models.TextField(blank=True, null=True,verbose_name="อาหารโปรด")
    allergies = models.TextField(blank=True, null=True,verbose_name="อาหารที่แพ้")
    is_lost = models.BooleanField(default=False,null=True,verbose_name="สุนัขหาย")
    
    # --- 2. ลักษณะทางกายภาพ ---
    primary_color = models.CharField(max_length=50, null=True, verbose_name="สีหลัก")
    secondary_color = models.CharField(max_length=50, blank=True, null=True, verbose_name="สีรอง")
    
    weight = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        blank=True, 
        null=True, 
        verbose_name="น้ำหนัก (กก.)"
    )
    size = models.CharField(max_length=1, null=True,choices=SIZE_CHOICES, verbose_name="ขนาด")
    distinguishing_marks = models.TextField(blank=True, verbose_name="ลักษณะ/รอยตำหนิเด่น")

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
