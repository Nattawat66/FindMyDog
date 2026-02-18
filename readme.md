Docker Setup Walkthrough - FindMyDog
สรุปการทำงาน
ผมได้สร้างการตั้งค่า Docker ที่สมบูรณ์สำหรับโปรเจ็กต์ Django FindMyDog พร้อมกับ PostgreSQL, Redis, และ Celery

ไฟล์ที่สร้าง
1. 
Dockerfile
Multi-stage Dockerfile สำหรับ Django application:

Stage 1: ติดตั้ง dependencies
Stage 2: Runtime container พร้อม non-root user
รองรับ PostgreSQL และ Gunicorn
2. 
docker-compose.yml
Orchestration configuration ประกอบด้วย 5 services:

postgres: PostgreSQL 16 database
redis: Redis 7 สำหรับ Celery broker
web: Django web application (port 8000)
celery: Celery worker สำหรับ background tasks
celery-beat: Celery beat scheduler
3. 
.dockerignore
ยกเว้นไฟล์ที่ไม่จำเป็นออกจาก Docker build context

4. 
.env.docker
Environment variables template สำหรับ Docker deployment

5. 
entrypoint.sh
Shell script ที่:

รอให้ PostgreSQL พร้อมใช้งาน
รัน migrations
Collect static files
เริ่ม application
6. การแก้ไข 
settings.py
อัพเดต database และ Redis configuration ให้อ่านค่าจาก environment variables:

python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "mydb"),
        "USER": os.getenv("POSTGRES_USER", "admin"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "1234"),
        "HOST": os.getenv("DB_HOST", "localhost"),
        "PORT": os.getenv("DB_PORT", "5432"),
    }
}
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
7. อัพเดต 
requirements.txt
เพิ่ม gunicorn สำหรับ production server

วิธีการใช้งาน
🚀 Build และรัน Docker containers
bash
# 1. ไปที่ directory โปรเจ็กต์
cd /Users/macbookair/Documents/projects_dog/django/FindMyDog
# 2. Build Docker image
docker-compose build
# 3. Start all services
docker-compose up -d
# 4. ตรวจสอบสถานะ containers
docker-compose ps
# 5. ดู logs (optional)
docker-compose logs -f web
📱 เข้าถึง Application
เปิด browser และไปที่: http://localhost:8000

🛠️ คำสั่งที่เป็นประโยชน์
bash
# ดู logs ของ service
docker-compose logs web
docker-compose logs celery
docker-compose logs postgres
# เข้าถึง Django shell
docker-compose exec web python manage.py shell
# สร้าง superuser
docker-compose exec web python manage.py createsuperuser
# รัน migrations ใหม่
docker-compose exec web python manage.py migrate
# เข้าถึง PostgreSQL
docker-compose exec postgres psql -U admin -d mydb
# หยุด containers
docker-compose down
# หยุดและลบ volumes (ลบ database!)
docker-compose down -v
# Restart service เดียว
docker-compose restart web
🔄 อัพเดตโค้ด
เมื่อแก้ไขโค้ด Django:

bash
# Rebuild และ restart
docker-compose up -d --build web
# หรือ restart เฉพาะ web service
docker-compose restart web
โครงสร้าง Services
Django Web :8000
PostgreSQL :5432
Redis :6379
Celery Worker
Celery Beat
Volumes
Docker จะสร้าง persistent volumes สำหรับ:

postgres_data: เก็บข้อมูล PostgreSQL database
redis_data: เก็บข้อมูล Redis
static_volume: เก็บ static files ของ Django
./dog_images: Mount จาก host สำหรับเก็บรูปภาพสุนัข (synced กับ host)
Environment Variables
ทุกค่าที่สำคัญถูกตั้งค่าผ่าน 
.env.docker
:

Database credentials
Django SECRET_KEY
API keys (Google Maps)
Redis URL
Celery configuration
การตรวจสอบความพร้อม (Health Checks)
Docker Compose มี health checks สำหรับ:

PostgreSQL: ตรวจสอบว่า database พร้อมใช้งาน
Redis: ตรวจสอบด้วย redis-cli ping
Web service จะรอจนกว่า PostgreSQL และ Redis จะพร้อมก่อนเริ่มทำงาน

Troubleshooting
ปัญหา: Container ไม่ start
bash
docker-compose logs web
ปัญหา: Database connection error
bash
# ตรวจสอบว่า postgres container ทำงานอยู่
docker-compose ps postgres
# ดู logs
docker-compose logs postgres
ปัญหา: Migration errors
bash
# รัน migrations manually
docker-compose exec web python manage.py migrate
ปัญหา: Port 8000 ถูกใช้งานแล้ว
แก้ไข 
docker-compose.yml
:

yaml
ports:
  - "8001:8000"  # เปลี่ยนจาก 8000 เป็น 8001
การ Deploy Production
WARNING

ก่อน deploy production ควรแก้ไข:

เปลี่ยน SECRET_KEY ใน 
.env.docker
ตั้ง DEBUG=False
อัพเดต ALLOWED_HOSTS ให้ตรงกับ domain
ใช้ strong passwords สำหรับ database
ตั้งค่า proper volume backups
สรุป
✅ สร้าง Docker configuration ครบถ้วน
✅ รองรับ PostgreSQL, Redis, และ Celery
✅ ใช้ environment variables สำหรับความยืดหยุ่น
✅ มี health checks และ proper dependency management
✅ พร้อมใช้งานทั้ง development และ production

คุณสามารถเริ่มต้นได้ทันทีด้วย docker-compose up -d 🚀