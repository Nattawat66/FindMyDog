
from .forms import DogForm, DogImageFormSet,OrgAdminDogForm,VACCINE_CHOICES,NotificationForm,ReportLostForm,TrainingScheduleForm
from django.shortcuts import render, redirect ,get_object_or_404
from django.http import Http404
from django.contrib.auth import authenticate, login as auth_login
from django.contrib import messages
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.decorators import login_required
from .models import Dog, DogImage, User,Notification, AdoptionParent
from django.db.models import Q
from django.db import models
from django.http import JsonResponse
import requests
import base64
import os
from .models import TrainingConfig
from django.core.cache import cache
from .scheduler import update_scheduler
import requests
import numpy as np
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from datetime import datetime

# ---------- UI Render Views ----------
@login_required
def dog_list(request):
    # กรองเอาเฉพาะสุนัขที่ผู้ใช้ที่เข้าสู่ระบบเป็นเจ้าของเท่านั้น
    # (สมมติว่าคุณได้ตั้งค่า owner = models.ForeignKey(User, ...) ไว้แล้ว)
    is_admin = request.user.is_staff
    
    is_org = request.user.role == 'org_admin'
    if is_admin:
        # Admin: ดึงสุนัขทุกตัวในระบบ
        # (คุณอาจต้องการใช้ .select_related('owner') เพื่อลดการ Query เพิ่มเติมเมื่อแสดงชื่อเจ้าของ)
        dogs_queryset = Dog.objects.all().select_related('owner').order_by('-id')
    else:
        # User ทั่วไป: ดึงเฉพาะสุนัขที่ผู้ใช้คนนั้นเป็นเจ้าของ
        dogs_queryset = Dog.objects.filter(owner=request.user).order_by('-id')

    context = {
        'dogs': dogs_queryset,
        'has_dogs': dogs_queryset.exists(),
        'is_admin': is_admin,
        'is_org': is_org,   
    }
    # Render template เดิม
    return render(request, 'myapp/dog/dog_list.html', context)


@login_required
def dog_detail(request, dog_id):
    # Admin (is_staff) สามารถดูได้ทุกตัว, User ทั่วไป (is_staff=False) ดูได้แค่ของตัวเอง
    is_org = request.user.role == 'org_admin'
    if request.user.is_staff:
        # Admin: ไม่ต้องมีเงื่อนไข owner
        # ใช้ .get() แทน .filter() เพื่อให้เกิด 404 หากไม่พบ ID
        try:
            dog = Dog.objects.get(pk=dog_id)
        except Dog.DoesNotExist:
            raise Http404("ไม่พบสุนัข ID นี้ในระบบ")
        
        # Admin มีสิทธิ์แก้ไขข้อมูลทั้งหมดได้
        can_edit = True
        
    else:
        # User ทั่วไป: ดูได้ทุกตัว แต่แก้ไขได้เฉพาะของตัวเอง
        # ดึงข้อมูลสุนัขโดยไม่ต้องเช็ค owner ก่อน (เพื่อให้ดูได้)
        dog = get_object_or_404(Dog, pk=dog_id)
        
        # ตรวจสอบว่าเป็นเจ้าของหรือไม่ เพื่อกำหนดสิทธิ์แก้ไข
        if dog.owner == request.user:
            # User ทั่วไปมีสิทธิ์แก้ไขได้เฉพาะของตัวเอง
            can_edit = True
        else:
            # ไม่ใช่เจ้าของ: ดูได้แต่แก้ไขไม่ได้
            can_edit = False

    # กำหนด Form class ตามสิทธิ์
    DogFormClass = OrgAdminDogForm if is_org else DogForm

    # ตรวจสอบว่าอยู่ในโหมดแก้ไขหรือไม่
    is_edit_mode = request.GET.get('edit', 'false').lower() == 'true' and can_edit
    
    if request.method == 'POST':
        # --- สำหรับการบันทึกข้อมูล (Edit/Update) ---
        if not can_edit and not request.user.is_staff:
            messages.error(request, 'คุณไม่มีสิทธิ์แก้ไขข้อมูลสุนัขตัวนี้')
            return redirect('dog_detail', dog_id=dog.id)
        # ⚠️ การแก้ไข: ต้องส่ง instance=dog เพื่อให้ฟอร์มโหลดข้อมูลเดิมมาแก้ไข
        form = DogFormClass(request.POST, instance=dog)
        # ⚠️ สำหรับ FormSet: ต้องส่ง request.FILES และ instance=dog ด้วย
        formset = DogImageFormSet(request.POST, request.FILES, instance=dog) 

        if form.is_valid() and formset.is_valid():
            dog = form.save()

            # ⬇️ ยังไม่ save formset ทันที
            instances = formset.save(commit=False)

            # รูปที่ต้องส่งไป embedding
            images_for_embedding = []

            for obj in instances:
                is_new = obj.pk is None

                if not is_new:
                    # เช็คว่าไฟล์รูปถูกเปลี่ยนไหม
                    old = DogImage.objects.get(pk=obj.pk)
                    image_changed = old.image != obj.image
                else:
                    image_changed = True

                obj.dog = dog
                obj.save()

                if image_changed:
                    images_for_embedding.append(obj)

            # handle deleted images
            for obj in formset.deleted_objects:
                obj.delete()

            # ===============================
            # 🔗 Call Embedding API เฉพาะรูปที่เปลี่ยน
            # ===============================
            if images_for_embedding:
                url = "https://3f03a05d7b85.ngrok-free.app/embedding-image/"

                files = []
                for img in images_for_embedding:
                    img.image.open('rb')
                    files.append((
                        'files',
                        (
                            os.path.basename(img.image.name),
                            img.image.file
                        )
                    ))

                try:
                    response = requests.post(
                        url,
                        data={'dog_id': dog.id},
                        files=files,
                        timeout=60
                    )
                except requests.RequestException as e:
                    print("❌ Embedding API error:", e)
                finally:
                    for img in images_for_embedding:
                        img.image.close()

                if response.status_code == 200:
                    results = response.json().get('results', [])

                    image_map = {
                        os.path.basename(img.image.name): img
                        for img in images_for_embedding
                    }

                    for item in results:
                        file_name = os.path.basename(item.get('file_name', ''))
                        embedding_base64 = item.get('embedding_bytes')

                        if not embedding_base64 or file_name not in image_map:
                            continue

                        if ',' in embedding_base64:
                            embedding_base64 = embedding_base64.split(',')[-1]

                        embedding_binary = base64.b64decode(embedding_base64)

                        dog_image = image_map[file_name]
                        dog_image.embedding_binary = embedding_binary
                        dog_image.save()

                        print("✅ Updated embedding:", file_name)

            return redirect('dog_detail', dog_id=dog.id)

    else:
        # --- สำหรับการแสดงผล/เปิดฟอร์มแก้ไข (Initial Load) ---
        
        # 5. โหลดข้อมูลสุนัขเดิมเข้าสู่ฟอร์ม
        form = DogFormClass(instance=dog) 
        
        # 6. โหลดรูปภาพที่มีอยู่เดิมเข้าสู่ FormSet
        formset = DogImageFormSet(instance=dog) 

    # ดึงรูปภาพทั้งหมดของสุนัขตัวนี้สำหรับแสดงผล (ทั้งใน FormSet และส่วนแสดงรายละเอียด)
    dog_images = dog.images.all() 

    VACCINE_MAP = dict(VACCINE_CHOICES)
    
    # 3. 🐍 Logic การกรองข้อความวัคซีน
    vaccine_history_raw = dog.vaccination_history
    vaccine_display_list = []

    if vaccine_history_raw:
        # แยก string ด้วยคอมมา และตัดช่องว่าง
        raw_list = [v.strip() for v in vaccine_history_raw.split(',') if v.strip()]
        
        for key in raw_list:
            # ดึงคำอธิบายจาก Map (ถ้าหาไม่เจอ ให้ใช้ key เดิม)
            display_value = VACCINE_MAP.get(key, key)
            vaccine_display_list.append(display_value)
            
    context = {
        'dog': dog,
        'form': form, # ส่งฟอร์มสำหรับแสดงผล
        'formset': formset, # ส่ง FormSet สำหรับแสดงผล
        'dog_images': dog_images, 
        'gender_display': dog.get_gender_display(),
        'size_display': dog.get_size_display(),
        'sterilization_display': dog.get_sterilization_status_display(),
        'is_edit_mode': is_edit_mode, # ส่งสถานะโหมดแก้ไข
        'can_edit': can_edit, # ส่งสิทธิ์การแก้ไข
        'vaccine_display_list': vaccine_display_list,
        'is_org': is_org,
    }
    return render(request, 'myapp/dog/dog_detail.html', context)

@login_required # บังคับให้ผู้ใช้ต้องเข้าสู่ระบบก่อน
def register_dog_page(request):
    role = request.user.role
    if role == 'org_admin':
        DogFormClass = OrgAdminDogForm
    else:
        DogFormClass = DogForm
    if request.method == 'POST':
        form = DogFormClass(request.POST)
        formset = DogImageFormSet(request.POST, request.FILES)

        if form.is_valid() and formset.is_valid():
            # 1. บันทึก Dog Model หลัก
            dog = form.save(commit=False)
            dog.owner = request.user # กำหนดเจ้าของเป็นผู้ใช้ปัจจุบัน
            # หากมี Organization Model ต้องกำหนดค่านี้ด้วย:
            # dog.organization = some_organization_object 
            dog.save()

            # 2. บันทึกรูปภาพที่เกี่ยวข้อง - ต้องส่ง instance=dog ก่อน
            formset.instance = dog
            formset.save()
            dog_images = DogImage.objects.filter(dog=dog)
            url = "https://3f03a05d7b85.ngrok-free.app/embedding-image/"

            files = []
            for img in dog_images:
                img.image.open('rb')
                files.append((
                    'files',
                    (
                        os.path.basename(img.image.name),
                        img.image.file
                    )
                ))

            data = {'dog_id': dog.id}

            try:
                response = requests.post(url, data=data, files=files, timeout=60)
            except requests.RequestException as e:
                print("❌ Embedding API error:", e)
                return redirect('dog_list')

            finally:
                for img in dog_images:
                    img.image.close()

            if response.status_code == 200:
                results = response.json().get('results', [])

                image_map = {
                    os.path.basename(img.image.name): img
                    for img in dog_images
                }

                for item in results:
                    file_name = os.path.basename(item.get('file_name', ''))
                    embedding_base64 = item.get('embedding_bytes')

                    if not embedding_base64 or file_name not in image_map:
                        continue

                    if ',' in embedding_base64:
                        embedding_base64 = embedding_base64.split(',')[-1]

                    embedding_binary = base64.b64decode(embedding_base64)

                    dog_image = image_map[file_name]
                    dog_image.embedding_binary = embedding_binary
                    dog_image.save()

                    print("✅ Saved embedding:", file_name)
            
            # 3. แสดงข้อความสำเร็จและ Redirect
            # messages.success(request, f'ลงทะเบียนสุนัข "{dog.name}" สำเร็จแล้ว!')
            return redirect('dog_list')
    else:
        form = DogFormClass()
        formset = DogImageFormSet(queryset=DogImage.objects.none()) # ฟอร์มเซ็ตเปล่า

    context = {
        'form': form,
        'formset': formset,
        'role' : role,
    }
    return render(request, 'myapp/dog/registerdog.html', context)
@csrf_protect
def register(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        
        # ตรวจสอบว่ารหัสผ่านตรงกันหรือไม่
        if password != password_confirm:
            messages.error(request, 'รหัสผ่านไม่ตรงกัน')
            return render(request, 'myapp/registeruser.html')
        
        # ตรวจสอบว่ามี username หรือ email ซ้ำหรือไม่
        if User.objects.filter(username=username).exists():
            messages.error(request, 'ชื่อผู้ใช้งานนี้มีอยู่ในระบบแล้ว')
            return render(request, 'myapp/registeruser.html')
        
        if email and User.objects.filter(email=email).exists():
            messages.error(request, 'อีเมลนี้มีอยู่ในระบบแล้ว')
            return render(request, 'myapp/registeruser.html')
        
        # สร้างผู้ใช้ใหม่
        try:
            user = User.objects.create_user(
                username=username,
                email=email if email else '',
                password=password
            )
            # messages.success(request, 'สมัครสมาชิกสำเร็จ! กรุณาเข้าสู่ระบบ')
            return redirect('login')
        except Exception as e:
            messages.error(request, f'เกิดข้อผิดพลาด: {str(e)}')
            return render(request, 'myapp/registeruser.html')
    
    return render(request, 'myapp/authen/registeruser.html')

# from django.contrib.admin.views.decorators import staff_member_required

# @staff_member_required
# def admin_page(request):
#     return render(request, 'admin_page.html')

@csrf_protect 
def login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)
            
        if not username or not password:
            messages.error(request, 'กรุณากรอกชื่อผู้ใช้งานและรหัสผ่าน')
            return render(request, 'myapp/loginuser.html')
        
        if user is not None:
            if user.is_staff:
                return redirect('admin_page')
            if user.is_active == False:
                messages.error(request, 'บัญชีผู้ใช้งานนี้ถูกระงับการใช้งาน')
                return render(request, 'myapp/loginuser.html')
            auth_login(request, user)
            # messages.success(request, f'ยินดีต้อนรับ {user.username}!')
            # Redirect ไปที่หน้าแรกหรือหน้าที่ต้องการ
            # ถ้ามี next parameter ให้ไปที่นั้น ถ้าไม่มีให้ไปที่ home ตาม LOGIN_REDIRECT_URL
            next_url = request.GET.get('next', None)
            if next_url:
                return redirect(next_url)
            else:
                return redirect('home')  # ใช้ชื่อ URL pattern แทน path
        else:
            messages.error(request, 'ชื่อผู้ใช้งานหรือรหัสผ่านไม่ถูกต้อง')
            return redirect('login')
        

    return render(request, 'myapp/authen/loginuser.html')


def my_login_view(request)  :
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        # Authenticate the user
        user = authenticate(request, username=username, password=password)
        if user is not None:
            # Log the user in
            login(request, user)
            # Redirect to a success page or the desired page after login
            return redirect('home')  # Replace 'home' with your desired URL name
        else:
            # Handle invalid login credentials
            # You might want to display an error message to the user
            return render(request, 'login.html', {'error_message': 'Invalid credentials'})
    else:
        # Render the login form for GET requests
        return render(request, 'login.html')

@login_required
def dog_all_list(request):
    context = {
        'total_dogs': Dog.objects.all().count(),
        'lost_dogs': Dog.objects.filter(is_lost=True).count(),
        'org_dogs': Dog.objects.filter(organization=True).count(),
        # 'vaccinated_dogs': Dog.objects.filter(vaccinated=True).count(),
        'dog_list': Dog.objects.all(), # ใช้ QuerySet จริงใน production
    }
    return render(request, 'myapp/dog/dog_all_list.html',context)
    
@login_required
def home(request):
    role = request.user.role
    if request.user.is_staff:
        return render(request, 'myapp/admin_backend/admin_home.html')
    elif role == 'org_admin':
        context = {
            'dogs_org': Dog.objects.filter(organization=True),
            'dogs_org_count': Dog.objects.filter(organization=True).count(),
            'dogs_lost_count': Dog.objects.filter(is_lost=True).count(),
            'dogs_org_lost_count': Dog.objects.filter(is_lost=True, organization=True).count(),
            'dogs_org_vaccinated_count': Dog.objects.filter(vaccination_history__isnull=False, organization=True).count(),
        }
        return render(request, 'myapp/admin_org/admin_org_home.html',context)
    else:
        recent_lost_dogs = Dog.objects.filter(is_lost=True).order_by('-id')[:5]
        context = {
            'recent_lost_dogs': recent_lost_dogs
        }
        return render(request, 'myapp/home.html', context)


@login_required
def delete_dog_page(request, dog_id):
    """
    View สำหรับลบสุนัข (UI version)
    """
    # ตรวจสอบสิทธิ์: ค้นหาสุนัขด้วย ID และต้องเป็นของเจ้าของปัจจุบันเท่านั้น
    dog = get_object_or_404(
        Dog, 
        pk=dog_id, 
        owner=request.user
    )
    
    if request.method == 'POST':
        # ยืนยันการลบ
        dog_name = dog.name
        dog.delete()
        # messages.success(request, f'ลบสุนัข "{dog_name}" ออกจากระบบสำเร็จแล้ว!')
        return redirect('dog_list')
    
    # ถ้าเป็น GET request ให้ redirect กลับไปหน้า detail (modal จะแสดงในหน้า detail)
    return redirect('dog_detail', dog_id=dog_id)


@login_required
def notification_list_view(request):
    user = request.user
    
    # 1. กรองข่าวสารทั่วไป (สำหรับทุกคน หรือ องค์กร)
    # 2. กรองข่าวสารเฉพาะสุนัขที่ผู้ใช้เป็นพ่อแม่บุญธรรม
    adopted_dogs_pks = AdoptionParent.objects.filter(user=user).values_list('dog__pk', flat=True)
    if user.role == 'org_admin':
        org_dog_pks = Dog.objects.filter(organization=True).values_list('pk', flat=True)
    else:
        org_dog_pks = []
    # 3. รวม QuerySets
    notifications = Notification.objects.filter(
        # เงื่อนไข 1: ACTIVITY หรือ LOST_DOG (ข่าวสารทั่วไป)
        models.Q(notification_type__in=['ACTIVITY', 'LOST_DOG']) |

        # เงื่อนไข 2: DOG_SPECIFIC ที่เกี่ยวกับสุนัขที่ผู้ใช้อุปการะ
        (models.Q(notification_type='DOG_SPECIFIC') & models.Q(dog__pk__in=adopted_dogs_pks)) |

        # เงื่อนไข 3: DOG_SPECIFIC ที่เกี่ยวกับสุนัขในองค์กรของผู้ใช้
        (models.Q(notification_type='DOG_SPECIFIC') & models.Q(dog__pk__in=org_dog_pks))
    ).order_by('-created_at')

    # 💡 [เงื่อนไขใหม่สำหรับ Admin] ข่าวสารเฉพาะสุนัข สำหรับ Admin องค์กร
        # ให้นำไปกรองจากสุนัขทั้งหมดในความดูแลของ Admin คนนั้น (org_dog_pks)
    
    # ... (ส่วนการจัดการสถานะอ่านแล้ว/ยังไม่อ่านถ้ามี) ...
    
    context = {
        'notifications': notifications,
        'total_count': notifications.count(),
        # 'unread_count': notifications.filter(is_read=False).count(),
    }
    
    return render(request, 'myapp/notifications/notification_list.html', context)

@login_required
def notification_detail_hx_view(request, notification_id):
    # 💡 ใช้ get_object_or_404 เพื่อจัดการถ้าไม่พบ
    notification = get_object_or_404(Notification, pk=notification_id)

    # 💡 [การจัดการสิทธิ์]: ตรวจสอบสิทธิ์แก้ไข/ลบ
    can_edit = False
    can_delete = False
    
    # ตรวจสอบว่าเป็นเจ้าของโพสหรือไม่ (organization = request.user)
    if notification.organization == request.user:
        can_edit = True
        can_delete = True
    # หรือถ้าเป็น super_admin ก็สามารถแก้ไข/ลบได้ทั้งหมด
    elif request.user.is_staff:
        can_edit = True
        can_delete = True
    
    context = {
        'notification': notification,
        'can_edit': can_edit,
        'can_delete': can_delete,
    }
    # 💡 สำคัญ: เรนเดอร์ template เฉพาะส่วน Pop-up
    return render(request, 'myapp/notifications/notification_modal.html', context)

@login_required
def create_notification_view(request):
    # ตรวจสอบสิทธิ์: อนุญาตเฉพาะ Org Admin หรือผู้ใช้ที่มีสิทธิ์ประกาศ
    if request.user.role not in ['org_admin', 'super_admin']: 
        messages.error(request, "คุณไม่มีสิทธิ์ในการสร้างประกาศข่าวสาร")
        return redirect('home') # หรือหน้าที่เหมาะสม

    if request.method == 'POST':
        # 💡 ส่ง request.user เข้าไปในฟอร์มเพื่อใช้ในการกรอง (ใน __init__)
        form = NotificationForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            notification = form.save(commit=False)
            
            # 💡 กำหนด Organization ผู้ประกาศ
            # สมมติว่าผู้ใช้ Admin มีฟิลด์ที่เชื่อมโยงกับ Organization
            if request.user.role == 'org_admin':
                # กำหนดให้องค์กรที่ประกาศคือ User Org Admin คนนั้น
                notification.organization = request.user 
            
            # ตรวจสอบว่าถ้าเลือกประเภท DOG_SPECIFIC แต่ไม่ได้เลือก Dog ให้เป็น Invalid
            if notification.notification_type == 'DOG_SPECIFIC' and not notification.dog:
                messages.error(request, "ประกาศเฉพาะสุนัข ต้องระบุสุนัขที่เกี่ยวข้อง")
                return render(request, 'myapp/notifications/notification_form.html', {'form': form})
            
            notification.save()
            # messages.success(request, f"ประกาศ '{notification.title}' ถูกสร้างเรียบร้อยแล้ว!")
            return redirect('notification_list') # Redirect ไปหน้ารายการข่าวสาร
    else:
        # 💡 ส่ง request.user เข้าไปในฟอร์ม
        form = NotificationForm(user=request.user)

    context = {
        'form': form,
        'is_edit_mode': False,
        'title': "สร้างประกาศข่าวสารใหม่",
        'submit_text': "เผยแพร่ประกาศ",
    }
    return render(request, 'myapp/notifications/notification_form.html', context)

@login_required
def edit_notification_view(request, notification_id):
    # ตรวจสอบสิทธิ์: ต้องเป็นเจ้าของโพสหรือ super_admin
    notification = get_object_or_404(Notification, pk=notification_id)
    
    # ตรวจสอบสิทธิ์
    if notification.organization != request.user and not request.user.is_staff:
        messages.error(request, "คุณไม่มีสิทธิ์ในการแก้ไขประกาศนี้")
        return redirect('notification_list')
    
    if request.method == 'POST':
        form = NotificationForm(request.POST, request.FILES, instance=notification, user=request.user)
        if form.is_valid():
            notification = form.save(commit=False)
            
            # ตรวจสอบว่าถ้าเลือกประเภท DOG_SPECIFIC แต่ไม่ได้เลือก Dog ให้เป็น Invalid
            if notification.notification_type == 'DOG_SPECIFIC' and not notification.dog:
                messages.error(request, "ประกาศเฉพาะสุนัข ต้องระบุสุนัขที่เกี่ยวข้อง")
                context = {
                    'form': form,
                    'is_edit_mode': True,
                    'title': "แก้ไขประกาศข่าวสาร",
                    'submit_text': "บันทึกการแก้ไข",
                }
                return render(request, 'myapp/notifications/notification_form.html', context)
            
            notification.save()
            # messages.success(request, f"แก้ไขประกาศ '{notification.title}' สำเร็จแล้ว!")
            return redirect('notification_list')
    else:
        form = NotificationForm(instance=notification, user=request.user)
    
    context = {
        'form': form,
        'is_edit_mode': True,
        'title': "แก้ไขประกาศข่าวสาร",
        'submit_text': "บันทึกการแก้ไข",
    }
    return render(request, 'myapp/notifications/notification_form.html', context)

@login_required
def delete_notification_view(request, notification_id):
    # ตรวจสอบสิทธิ์: ต้องเป็นเจ้าของโพสหรือ super_admin
    notification = get_object_or_404(Notification, pk=notification_id)
    
    # ตรวจสอบสิทธิ์
    if notification.organization != request.user and not request.user.is_staff:
        messages.error(request, "คุณไม่มีสิทธิ์ในการลบประกาศนี้")
        return redirect('notification_list')
    
    if request.method == 'POST':
        notification_title = notification.title
        notification.delete()
        # messages.success(request, f"ลบประกาศ '{notification_title}' สำเร็จแล้ว!")
        return redirect('notification_list')
    
    # ถ้าเป็น GET request ให้ redirect กลับไปหน้า list
    return redirect('notification_list')

@login_required
def user_profile_view(request):
    # ข้อมูลผู้ใช้ที่เข้าสู่ระบบจะอยู่ใน request.user
    user = request.user
    
    # ถ้าคุณมี choices/mapping สำหรับ role
    # เช่น ROLE_CHOICES = [('standard', 'ผู้ใช้ทั่วไป'), ('org_admin', 'ผู้ดูแลองค์กร')]
    # คุณอาจต้องสร้างฟังก์ชันใน Custom User Model เพื่อดึง Role Display 
    # user.get_role_display() 
    
    context = {
        'user': user,
        # สามารถเพิ่มข้อมูลอื่นๆ ที่ต้องการแสดงได้ที่นี่
        'profile_title': "ข้อมูลส่วนตัวของฉัน",
    }
    return render(request, 'myapp/user/profile.html', context)

@login_required # หรือไม่ใส่ก็ได้ ขึ้นอยู่กับว่าคุณต้องการให้ใครเห็นแผนที่บ้าง
def lost_dogs_map_view(request):

    context = {
        'map_title': "แผนที่ค้นหาสุนัขสูญหาย",
    }
    return render(request, 'myapp/map/map.html', context)

@login_required
def report_lost_dog_view(request, dog_id):
    dog = get_object_or_404(Dog, pk=dog_id)
    
    # 💡 [ตรวจสอบสิทธิ์]: อนุญาตเฉพาะเจ้าของสุนัขหรือ Org Admin ที่ดูแลเท่านั้น
    if dog.owner != request.user and dog.organization != request.user:
        messages.error(request, "คุณไม่มีสิทธิ์ในการแจ้งสูญหายสุนัขตัวนี้")
        return redirect('dog_detail', dog_id=dog_id)

    if request.method == 'POST':
        # ใช้ instance เพื่ออัปเดต Dog object เดิม
        form = ReportLostForm(request.POST, instance=dog)
        if form.is_valid():
            lost_dog = form.save(commit=False)
            
            # กำหนดสถานะ is_lost เป็น True
            lost_dog.is_lost = True 
            
            lost_dog.save()
            
            messages.success(request, f"แจ้งสูญหายสุนัข {dog.name} เรียบร้อยแล้ว! ตำแหน่งถูกบันทึกในแผนที่.")
            return redirect('dog_detail', dog_id=dog_id)
    else:
        # 💡 ส่งค่า initial จาก Dog object เดิม (ถ้าเคยมีพิกัดอยู่แล้ว)
        form = ReportLostForm(instance=dog) 

    context = {
        'dog': dog,
        'form': form,
        'title': f"ปักหมุดแจ้งสูญหาย: {dog.name}",
    }
    return render(request, 'myapp/map/report_lost_map.html', context)


def lost_dogs_map_data(request):
    
    # 1. ดึงข้อมูลสุนัขที่สูญหายและมีพิกัด
    # ใช้ prefetch_related('images') เพื่อโหลดรูปภาพ DogImage เข้ามาพร้อมกัน
    lost_dogs_queryset = Dog.objects.filter(
        is_lost=True, 
        lost_latitude__isnull=False, 
        lost_longitude__isnull=False
    ).prefetch_related('images') # 💡 (สมมติ: related_name คือ 'images')

    data = []
    
    for dog in lost_dogs_queryset:
        image_url = None
        
        # 2. เข้าถึงรูปภาพแรก
        # เทียบเท่ากับการใช้ dog.images.first() ใน Template
        first_image = dog.images.first() 
        
        if first_image and first_image.image:
            # 3. สร้าง URL รูปภาพที่สมบูรณ์จาก ImageField
            # (สมมติ: ฟิลด์รูปภาพใน DogImage คือ 'image')
            # request.build_absolute_uri จำเป็นสำหรับ URL รูปภาพที่ถูกต้อง
            image_url = request.build_absolute_uri(first_image.image.url)
        
        # 4. ประกอบข้อมูล JSON
        data.append({
            'id': dog.id,
            'name': dog.name,
            # แปลง DecimalField เป็น float
            'lat': float(dog.lost_latitude),
            'lng': float(dog.lost_longitude),
            'image_url': image_url or '', # ถ้าไม่มีรูปภาพ ให้ส่งสตริงว่างไป
            'detail_url': f'/dogs/{dog.id}' # URL สำหรับหน้าดูรายละเอียดสุนัข
        })
        
    return JsonResponse({'dogs': data})

@login_required
def matchdog(request):
    if request.method == 'POST':
        # รับไฟล์ภาพ (แม้จะยังไม่ได้เอาไปเข้า AI จริงๆ)
        image = request.FILES.get('image')
        
        # Mock: สุ่มสุนัขมา 5 ตัว
        # order_by('?') เป็นการ random จาก database (ช้าถ้าข้อมูลเยอะ แต่สำหรับ mock ok)
        search_results = list(Dog.objects.all().order_by('?')[:5])
        
        # Mock similarity score
        import random
        for dog in search_results:
            dog.similarity_score = random.randint(60, 99)
            
        # เรียงลำดับตามความเหมือน (mock)
        search_results.sort(key=lambda x: x.similarity_score, reverse=True)

        context = {
            'search_results': search_results,
            'is_result': True, # Flag เพื่อบอก Template ว่าแสดงผลลัพธ์
        }
        return render(request, 'myapp/matchdog/matchdog.html', context)
        
    return render(request, 'myapp/matchdog/matchdog.html')

#model managements  ------------------------------------------------------------------------


# @login_required
# def admin_page(request):
#     if not request.user.is_staff:
#         messages.error(request, 'คุณไม่มีสิทธิ์เข้าถึงหน้านี้')
#         return redirect('home')
#     return render(request, 'admin/index.html')
def admin_page(request):
    return render(request, 'admin/dashdoardAI/dashdoard.html')

from .serverFast import trainKNN

def page_testEMBmodel(request):
    return render(request, 'admin/Training/set_TestKNN.html')

def page_select_model(request):
    return render(request, 'admin/Training/select_model.html')

def select_model(request):
    pass

def TestEmbModel(request):
    pass

def set_auto_training(request):
    from datetime import datetime, time
    from django.utils import timezone
    import pytz
    
    config = TrainingConfig.objects.first()
    form = TrainingScheduleForm(instance=config)
    countdown_seconds = None
    next_training_time = None
    
    if config and config.scheduled_time:
        try:
            # แยกชั่วโมงและนาทีจาก scheduled_time
            hour, minute = map(int, config.scheduled_time.split(':'))
            
            # สร้างเวลาปัจจุบันและเป้าหมาย
            now = timezone.now()
            today = now.date()
            
            # สร้างเวลาเป้าหมายสำหรับวันนี้
            target_time_today = timezone.make_aware(
                datetime.combine(today, time(hour, minute))
            )
            
            # ถ้าเวลาปัจจุบันเลยเวลาเป้าหมายแล้ว ให้คำนวณเป็นวันถัดไป
            if now >= target_time_today:
                if config.frequency == 'daily':
                    target_time_today = target_time_today + timezone.timedelta(days=1)
                elif config.frequency == 'weekly':
                    target_time_today = target_time_today + timezone.timedelta(weeks=1)
                elif config.frequency == 'monthly':
                    # คำนวณเดือนถัดไป (แบบง่าย)
                    next_month = today.month + 1 if today.month < 12 else 1
                    next_year = today.year if today.month < 12 else today.year + 1
                    target_time_today = target_time_today.replace(year=next_year, month=next_month)
            
            next_training_time = target_time_today
            countdown_seconds = int((target_time_today - now).total_seconds())
            
        except (ValueError, AttributeError):
            pass
    
    # ตรวจสอบสถานะ cache
    cache_triggered = cache.get('training_triggered', False)
    
    context = {
        'config': config,
        'form': form,
        'countdown_seconds': countdown_seconds,
        'next_training_time': next_training_time,
        'cache_triggered': cache_triggered,
    }
    
    return render(request, 'admin/Training/SetautoTraining.html', context)
    
def set_time_auto_training(request):
    config = TrainingConfig.objects.first()

    if request.method == 'POST':
        form = TrainingScheduleForm(request.POST, instance=config)
        if form.is_valid():
            obj = form.save()

            cache.set("AUTO_TRAIN_TIME", obj.scheduled_time, None)
            cache.set("AUTO_TRAIN_FREQ", obj.frequency, None)
            cache.set("AUTO_TRAIN_ACTIVE", obj.is_active, None)

            update_scheduler()  # รีโหลด scheduler ใหม่ทันที
            
            messages.success(
                request,
                f"ตั้งเวลาสำเร็จ! ระบบจะเริ่มทำงานทุก {obj.get_frequency_display()} เวลา {obj.scheduled_time}"
            )
            return redirect('set_auto_training')
        else:
            form = TrainingScheduleForm(instance=config)

        return render(request, 'admin/Training/SetautoTraining.html', {'form': form})

@staff_member_required
def train_knn_view(request):
    # 1. ดึงข้อมูลที่มี Embedding
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
            {"status": "error", "message": "ไม่มี embedding ในระบบ"},
            status=400
        )

    try:
        # 2. ส่งข้อมูลไปยัง FastAPI
        # เพิ่ม timeout เผื่อกรณี t-SNE ใช้เวลาคำนวณนาน
        response = requests.post(
            "http://127.0.0.1:8001/test-knn/",
            json={"data": train_data},
            timeout=180 
        )
        
        result_data = response.json()

        if response.status_code == 200:
            # 3. ส่งรูปภาพทั้ง 2 ไปยัง Template
            # หมายเหตุ: 'knn_matrix' ต้องตรงกับที่ตั้งใน FastAPI
            return render(request, 'admin/Training/set_TestKNN.html', {
                'tsne_plot': result_data.get('tsne_plot'),
                'knn_matrix': result_data.get('knn_matrix'), # เปลี่ยนชื่อ key ให้ตรงกัน
                'status': result_data.get('status'),
                'message': result_data.get('message'),
                'count': len(train_data),
            })
        else:
            return JsonResponse({
                "status": "error", 
                "message": f"FastAPI Error: {result_data.get('detail', 'Unknown error')}"
            }, status=response.status_code)

    except requests.RequestException as e:
        return JsonResponse(
            {"status": "error", "message": f"ไม่สามารถเชื่อมต่อ FastAPI ได้: {str(e)}"},
            status=500
        )

