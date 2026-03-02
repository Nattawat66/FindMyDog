
from logging import config
from .forms import DogForm, DogImageFormSet,OrgAdminDogForm,VACCINE_CHOICES,NotificationForm,ReportLostForm,TrainingScheduleForm,UserRegisterForm,LoginForm
from django.shortcuts import render, redirect ,get_object_or_404
from django.http import Http404
from django.contrib.auth import authenticate, login as auth_login
from django.contrib import messages
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.decorators import login_required
from .models import Dog, DogImage, User,Notification, AdoptionParent, AdoptionRequest
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
from datetime import datetime, time
import psutil
import json
apiurl = "https://02fa-2403-6200-8822-70aa-bd24-139e-f954-bd8a.ngrok-free.app/"
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
                url = apiurl+"embedding-image/"

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
            url = apiurl+"embedding-image/"

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

                # สร้าง map เพื่อให้หาภาพได้เร็วขึ้น
                image_map = {
                    os.path.basename(img.image.name): img
                    for img in dog_images
                }

                for item in results:
                    # **จุดที่ต้องแก้: Key ต้องตรงกับ API**
                    file_name = item.get('filename') 
                    emb_str = item.get('embedding_base64')

                    if not emb_str or file_name not in image_map:
                        print(f"⚠️ Skip: {file_name} not found or no embedding")
                        continue

                    # แปลง Base64 String กลับเป็น Binary
                    embedding_binary = base64.b64decode(emb_str)

                    # บันทึกลง database
                    dog_image = image_map[file_name]
                    dog_image.embedding_binary = embedding_binary
                    dog_image.save()

                    print(f"✅ Saved embedding for: {file_name}")
            
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
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')
    else:
        form = UserRegisterForm()

    return render(request, 'myapp/authen/registeruser.html', {'form': form})

# @csrf_protect
# def register(request):
#     if request.method == 'POST':
#         username = request.POST.get('username')
#         email = request.POST.get('email')
#         password = request.POST.get('password')
#         password_confirm = request.POST.get('password_confirm')
#         phone = request.POST.get('phone')
#         line_id = request.POST.get('line_id')

#         # ตรวจสอบว่ารหัสผ่านตรงกันหรือไม่
#         if password != password_confirm:
#             messages.error(request, 'รหัสผ่านไม่ตรงกัน')
#             return render(request, 'myapp/authen/registeruser.html')
        
#         # ตรวจสอบว่ามี username หรือ email ซ้ำหรือไม่
#         if User.objects.filter(username=username).exists():
#             messages.error(request, 'ชื่อผู้ใช้งานนี้มีอยู่ในระบบแล้ว')
#             return render(request, 'myapp/authen/registeruser.html')
        
#         if email and User.objects.filter(email=email).exists():
#             messages.error(request, 'อีเมลนี้มีอยู่ในระบบแล้ว')
#             return render(request, 'myapp/authen/registeruser.html')
        
#         # สร้างผู้ใช้ใหม่
#         try:
#             user = User.objects.create_user(
#                 username=username,
#                 email=email if email else '',
#                 password=password
#             )
#             user.phone = phone
#             user.line_id = line_id
#             user.save()
#             # messages.success(request, 'สมัครสมาชิกสำเร็จ! กรุณาเข้าสู่ระบบ')
#             return redirect('login')
#         except Exception as e:
#             messages.error(request, f'เกิดข้อผิดพลาด: {str(e)}')
#             return render(request, 'myapp/registeruser.html')
    
#     return render(request, 'myapp/authen/registeruser.html')

# from django.contrib.admin.views.decorators import staff_member_required

# @staff_member_required
# def admin_page(request):
#     return render(request, 'admin_page.html')





@csrf_protect
def login(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)

        if form.is_valid():
            user = form.get_user()

            if user.is_staff:
                return redirect('admin_page')

            auth_login(request, user)

            next_url = request.GET.get('next')
            return redirect(next_url if next_url else 'home')

    else:
        form = LoginForm()

    return render(request, 'myapp/authen/loginuser.html', {'form': form})
    
# @csrf_protect 
# def login(request):
#     if request.method == 'POST':
#         username = request.POST.get('username')
#         password = request.POST.get('password')

#         user = authenticate(request, username=username, password=password)
            
#         if not username or not password:
#             messages.error(request, 'กรุณากรอกชื่อผู้ใช้งานและรหัสผ่าน')
#             return render(request, 'myapp/loginuser.html')
        
#         if user is not None:
#             if user.is_staff:
#                 return redirect('admin_page')
#             if user.is_active == False:
#                 messages.error(request, 'บัญชีผู้ใช้งานนี้ถูกระงับการใช้งาน')
#                 return render(request, 'myapp/loginuser.html')
#             auth_login(request, user)
#             # messages.success(request, f'ยินดีต้อนรับ {user.username}!')
#             # Redirect ไปที่หน้าแรกหรือหน้าที่ต้องการ
#             # ถ้ามี next parameter ให้ไปที่นั้น ถ้าไม่มีให้ไปที่ home ตาม LOGIN_REDIRECT_URL
#             next_url = request.GET.get('next', None)
#             if next_url:
#                 return redirect(next_url)
#             else:
#                 return redirect('home')  # ใช้ชื่อ URL pattern แทน path
#         else:
#             messages.error(request, 'ชื่อผู้ใช้งานหรือรหัสผ่านไม่ถูกต้อง')
#             return redirect('login')
        

#     return render(request, 'myapp/authen/loginuser.html')


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
    print(request.user.is_staff,role)
    # if request.user.is_staff:
    #     print("admin")
    #     return render(request, 'myapp/admin_backend/admin_home.html')
    if role == 'org_admin':
        print("org_admin")
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
    
    # ตรวจสอบโหมดแก้ไข
    is_edit_mode = request.GET.get('edit', 'false').lower() == 'true'

    if request.method == 'POST' and is_edit_mode:
        phone = request.POST.get('phone')
        line_id = request.POST.get('line_id')
        
        # อัปเดตข้อมูล
        user.phone = phone
        user.line_id = line_id
        user.save()
        
        messages.success(request, 'บันทึกข้อมูลส่วนตัวเรียบร้อยแล้ว')
        return redirect('user_profile')

    
    # ถ้าคุณมี choices/mapping สำหรับ role
    # เช่น ROLE_CHOICES = [('standard', 'ผู้ใช้ทั่วไป'), ('org_admin', 'ผู้ดูแลองค์กร')]
    # คุณอาจต้องสร้างฟังก์ชันใน Custom User Model เพื่อดึง Role Display 
    # user.get_role_display() 
    
    context = {
        'user': user,
        # สามารถเพิ่มข้อมูลอื่นๆ ที่ต้องการแสดงได้ที่นี่
        'profile_title': "ข้อมูลส่วนตัวของฉัน",
        'is_edit_mode': is_edit_mode,
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
    # Toggle Exam Mode here (True = Testing with random dogs, False = Real API)ณ
    IS_EXAM_MODE = False  

    if request.method == 'POST' and request.FILES.get('image'):
        image_file = request.FILES.get('image')
        search_results = []
        
        if IS_EXAM_MODE:
            # --- Exam Mode: Random 5 dogs ---
            # ดึงสุนัขแบบสุ่มมา 5 ตัว
            random_dogs = list(Dog.objects.order_by('?')[:5])
            
            # กำหนดคะแนนสมมติ (เรียงจากมากไปน้อย)
            dummy_scores = [98, 95, 92, 88, 85]
            
            for i, dog in enumerate(random_dogs):
                # ป้องกันกรณีสุนัขไม่พอ 5 ตัว
                if i < len(dummy_scores):
                    dog.similarity_score = dummy_scores[i]
                else:
                    dog.similarity_score = 80 # default ถ้าเกิน
                search_results.append(dog)
                
            print("⚠️ Running in EXAM MODE: Returned 5 random dogs.")
            
        else:
            # --- Real Mode: Call API ---
            # 1. ส่งรูปไปยัง API
            api_url = apiurl+"SEARCH-DOG02/"
            
            try:
                files = {'file': (image_file.name, image_file.read(), image_file.content_type)}
                response = requests.post(api_url, files=files, timeout=30) # เพิ่ม timeout เพราะ AI อาจใช้เวลา
                response.raise_for_status()
                
                # 2. รับผลลัพธ์ {"results": [{"rank": 1, "dog_id": "...", "distance": ...}, ...]}
                api_response = response.json()
                api_results = api_response.get('results', [])
                print(api_results)
                
                for item in api_results:
                    filename_from_api = item['dog_id'] # ในกรณีนี้คือเลข 27
                    
                    try:
                        # เปลี่ยนมาใช้ id=filename_from_api แทน
                        dog = Dog.objects.filter(id=filename_from_api).first()
                        
                        if dog:
                            dog.distance = round(item['distance'], 4)
                            # คำนวณ Score จาก Distance (ถ้า distance น้อย score จะสูง)
                            dog.similarity_score = max(0, 100 - int(item['distance'] * 10)) 
                            
                            search_results.append(dog)
                        else:
                            print(f"Dog ID {filename_from_api} not found in database.")

                    except Exception as e:
                        print(f"Error fetching dog {filename_from_api}: {e}")
                        continue

            except requests.exceptions.RequestException as e:
                print(f"API Connection Error: {e}")
                
        context = {
            'search_results': search_results,
            'is_result': True,
        }
        print(context)
        return render(request, 'myapp/matchdog/matchdog.html', context)
        
    return render(request, 'myapp/matchdog/matchdog.html')
#model managements  ------------------------------------------------------------------------

@login_required
@staff_member_required
@csrf_exempt
def get_cpu_stats(request):
    """API endpoint เพื่อดึงข้อมูล CPU และ System Stats"""
    try:
        # ดึงข้อมูล CPU per core
        cpu_percent_per_core = psutil.cpu_percent(interval=1.10, percpu=True)
        cpu_percent_overall = psutil.cpu_percent(interval=1.10)
        
        # ดึงข้อมูล Memory
        memory_info = psutil.virtual_memory()
        
        # ดึงข้อมูล Disk
        disk_info = psutil.disk_usage('/')
        
        # ดึงข้อมูล Process count
        process_count = len(psutil.pids())
        
        data = {
            'cpu': {
                'overall': cpu_percent_overall,
                'per_core': cpu_percent_per_core,
                'count': psutil.cpu_count(logical=True),
            },
            'memory': {
                'total': memory_info.total,
                'available': memory_info.available,
                'percent': memory_info.percent,
                'used': memory_info.used,
            },
            'disk': {
                'total': disk_info.total,
                'used': disk_info.used,
                'free': disk_info.free,
                'percent': disk_info.percent,
            },
            'processes': process_count,
            'timestamp': datetime.now().isoformat(),
        }
        
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({
            'error': str(e)
        }, status=500)


# @login_required
# def admin_page(request):
#     if not request.user.is_staff:
#         messages.error(request, 'คุณไม่มีสิทธิ์เข้าถึงหน้านี้')
#         return redirect('home')
#     return render(request, 'admin/index.html')
# def admin_page(request):
#     # ดึงผลการทดสอบล่าสุด
#     latest_result = KNNTrainingResult.objects.order_by('-created_at').first()
    
#     # ดึงประวัติการทดสอบทั้งหมด (เรียงตามเวลาล่าสุดก่อน)
#     test_history = KNNTrainingResult.objects.order_by('-created_at')[:20]
    
#     context = {
#         'latest_result': latest_result,
#         'test_history': test_history,
#     }
#     return render(request, 'admin/dashdoardAI/dashdoard.html', context)
# @staff_member_required
def admin_page(request):
    
    # 1. AI & Training Data
    latest_result = KNNTrainingResult.objects.order_by('-created_at').first()
    test_history = KNNTrainingResult.objects.order_by('-created_at')[:20]
    
    # 2. CRUD Data
    users = User.objects.all().order_by('-date_joined')
    dogs = Dog.objects.all().order_by('-id')
    notifications = Notification.objects.all().order_by('-created_at')

    context = {
        'latest_result': latest_result,
        'test_history': test_history,
        'users': users,
        'dogs': dogs,
        'notifications': notifications,
        'role_choices': User.ROLE_CHOICES, # For role editing
    }
    return render(request, 'admin/dashdoardAI/dashdoard.html', context)

def admin_update_user_role(request, user_id):
    
    if request.method == 'POST':
        user_to_edit = get_object_or_404(User, pk=user_id)
        new_role = request.POST.get('role')
        
        # Prevent changing own role or superuser role casually
        if user_to_edit == request.user:
             messages.error(request, "ไม่สามารถเปลี่ยนสิทธิ์ของตัวเองได้")
        elif new_role in dict(User.ROLE_CHOICES):
            user_to_edit.role = new_role
            user_to_edit.save()
            messages.success(request, f"อัปเดตสิทธิ์ของ {user_to_edit.username} เป็น {user_to_edit.get_role_display()} เรียบร้อย")
        else:
             messages.error(request, "บทบาทไม่ถูกต้อง")
             
    return redirect('admin_page')

def admin_delete_user(request, user_id):
        
    if request.method == 'POST':
        user_to_delete = get_object_or_404(User, pk=user_id)
        
        if user_to_delete == request.user:
             messages.error(request, "ไม่สามารถลบบัญชีตัวเองได้")
        elif user_to_delete.is_superuser:
             messages.error(request, "ไม่สามารถลบ Superuser ได้")
        else:
            username = user_to_delete.username
            user_to_delete.delete()
            messages.success(request, f"ลบผู้ใช้ {username} เรียบร้อยแล้ว")
            
    return redirect('admin_page')

def admin_delete_dog(request, dog_id):
        
    if request.method == 'POST':
        dog = get_object_or_404(Dog, pk=dog_id)
        dog_name = dog.name
        dog.delete()
        messages.success(request, f"ลบสุนัข {dog_name} เรียบร้อยแล้ว")
            
    return redirect('admin_page')

from .serverFast import trainKNN

def page_testEMBmodel(request):
    # ดึงผลการทดสอบล่าสุด
    latest_result = KNNTrainingResult.objects.order_by('-created_at').first()
    
    context = {
        'result': latest_result,
    }
    return render(request, 'admin/Training/set_TestKNN.html', context)

def page_select_model(request):
    return render(request, 'admin/Training/select_model.html')

def select_model(request):
    pass

def TestEmbModel(request):
    pass

def set_auto_training(request):
    from datetime import datetime, time, timedelta
    from django.utils import timezone
    from dateutil.relativedelta import relativedelta
    
    config = TrainingConfig.objects.first()
    form = TrainingScheduleForm(instance=config)
    next_training_time = None
    countdown_seconds = None

    if config and config.scheduled_time:
        try:
            hour, minute = map(int, config.scheduled_time.split(':'))
            now = timezone.now()
            
            # เริ่มต้นจากเวลาที่ตั้งไว้ของ "วันนี้"
            target = timezone.make_aware(datetime.combine(now.date(), time(hour, minute)))

            # Logic การบวกเวลาตามที่คุณต้องการ
            if config.frequency == 'daily':
                # บวกไป 1 วันเสมอจากวันนี้
                next_training_time = target + relativedelta(days=1)
            
            elif config.frequency == 'weekly':
                # บวกไป 1 สัปดาห์ (7 วัน) เสมอจากวันนี้
                next_training_time = target + relativedelta(weeks=1)
            
            elif config.frequency == 'monthly':
                # เป็นวันที่เดียวกัน แต่เป็นเดือนถัดไปเสมอ
                next_training_time = target + relativedelta(months=1)

            # คำนวณวินาทีสำหรับ Countdown
            if next_training_time:
                countdown_seconds = int((next_training_time - now).total_seconds())
            
        except Exception as e:
            print(f"Error: {e}")

    context = {
        'config': config,
        'form': form,
        'countdown_seconds': countdown_seconds,
        'next_training_time': next_training_time,
        'cache_triggered': cache.get('training_triggered', False),
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
    
import base64
from django.core.files.base import ContentFile
from .models import KNNTrainingResult

def base64_to_image(base64_str, filename, default_ext="png"):
    """
    รองรับทั้ง:
    - data:image/png;base64,...
    - base64 ล้วน ๆ
    """
    if ';base64,' in base64_str:
        header, imgstr = base64_str.split(';base64,')
        ext = header.split('/')[-1]
    else:
        imgstr = base64_str
        ext = default_ext

    return ContentFile(
        base64.b64decode(imgstr),
        name=f"{filename}.{ext}"
    )

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
        print(train_data)
        response = requests.post(
            apiurl+"test-knn/",
            json={"data": train_data},
            timeout=180 
        )
        result_data = response.json()

        if response.status_code == 200:
            tsne_b64 = result_data.get("tsne_plot")
            knn_b64 = result_data.get("knn_matrix")
            model_name = result_data.get("model_name", "unknown")

            result = KNNTrainingResult.objects.create(
                count=len(train_data),
                tsne_image=base64_to_image(tsne_b64, "tsne_plot"),
                knn_matrix_image=base64_to_image(knn_b64, "knn_matrix"),
                accuracy=result_data.get("accuracy", 0.0),
                model_name=model_name
            )
            return render(request, 'admin/Training/set_TestKNN.html', {
                'result': result
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
def knn_test_history_view(request):
    # จัดการการลบข้อมูล
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'delete_all':
            # ลบทั้งหมด
            KNNTrainingResult.objects.all().delete()
            messages.success(request, "ลบประวัติการทดสอบทั้งหมดเรียบร้อยแล้ว")
            return redirect('history_knn')
        
        elif action == 'delete_single':
            # ลบรายการเดียว
            result_id = request.POST.get('result_id')
            try:
                result = KNNTrainingResult.objects.get(pk=result_id)
                result.delete()
                messages.success(request, f"ลบประวัติการทดสอบ (ID: {result_id}) เรียบร้อยแล้ว")
            except KNNTrainingResult.DoesNotExist:
                messages.error(request, "ไม่พบประวัติการทดสอบนี้")
            return redirect('history_knn')
    
    results = KNNTrainingResult.objects.order_by('-created_at')
    context = {
        'results': results,
        'title': "ประวัติการทดสอบ KNN Model",
        'test_history': results,  # ส่ง test_history เพื่อให้ template ใช้งานได้
    }
    return render(request, 'admin/Training/history_Knn.html', context)

@login_required
@staff_member_required
def get_knn_result_api(request, result_id):
    """API endpoint เพื่อดึงข้อมูล KNN result เป็น JSON"""
    try:
        result = KNNTrainingResult.objects.get(pk=result_id)
        
        data = {
            'id': result.id,
            'count': result.count,
            'accuracy': result.accuracy,
            'model_name': result.model_name,
            'created_at': result.created_at.isoformat(),
            'tsne_image': result.tsne_image.url if result.tsne_image else None,
            'knn_matrix_image': result.knn_matrix_image.url if result.knn_matrix_image else None,
        }
        return JsonResponse(data)
    except KNNTrainingResult.DoesNotExist:
        return JsonResponse(
            {"status": "error", "message": "ไม่พบผลการทดสอบนี้"},
            status=404
        )

@login_required
def request_adoption_view(request, dog_id):
    dog = get_object_or_404(Dog, pk=dog_id)
    
    # Check if request already exists
    existing_request = AdoptionRequest.objects.filter(user=request.user, dog=dog, status='PENDING').exists()
    
    if existing_request:
        messages.warning(request, "คุณได้ส่งคำขออุปการะสุนัขตัวนี้ไปแล้ว กรุณารอการตรวจสอบ")
        return redirect('dog_detail', dog_id=dog_id)
        
    if request.method == 'POST':
        reason = request.POST.get('reason', '')
        
        AdoptionRequest.objects.create(
            user=request.user,
            dog=dog,
            request_reason=reason
        )
        
        messages.success(request, "ส่งคำขออุปการะสำเร็จ! เจ้าหน้าที่กำลังตรวจสอบข้อมูลของคุณ")
        return redirect('dog_detail', dog_id=dog_id)
    
    return redirect('dog_detail', dog_id=dog_id)


@login_required
def adoption_request_list_view(request):
    # Only Org Admin or Staff
    if request.user.role != 'org_admin' and not request.user.is_staff:
        messages.error(request, "คุณไม่มีสิทธิ์เข้าถึงหน้านี้")
        return redirect('home')
        
    # Filter requests for organization dogs
    if request.user.role == 'org_admin':
        # Assuming org_admin manages all dogs with organization=True
        # Or if there is a link between org_admin and organization, filter by that.
        # Based on existing code, org_admin sees all organization=True dogs.
        dogs = Dog.objects.filter(organization=True)
        requests_list = AdoptionRequest.objects.filter(dog__in=dogs, status='PENDING').order_by('-created_at')
    else:
        # Staff sees all
        requests_list = AdoptionRequest.objects.filter(status='PENDING').order_by('-created_at')
        
    context = {
        'requests': requests_list,
        'title': "รายการคำขออุปการะ"
    }
    return render(request, 'myapp/admin_org/adoption_request_list.html', context)


@login_required
def handle_adoption_request_view(request, request_id, action):
    # action: 'approve' or 'reject'
    adoption_req = get_object_or_404(AdoptionRequest, pk=request_id)
    
    # Permission check
    if request.user.role != 'org_admin' and not request.user.is_staff:
        messages.error(request, "คุณไม่มีสิทธิ์ดำเนินการ")
        return redirect('home')
        
    if action == 'approve':
        adoption_req.status = 'APPROVED'
        adoption_req.save()
        
        # Create AdoptionParent relation
        AdoptionParent.objects.get_or_create(
            user=adoption_req.user,
            dog=adoption_req.dog
        )
        
        # Create Notification for the user
        Notification.objects.create(
            title=f"ยินดีด้วย! คำขออุปการะ {adoption_req.dog.name} ได้รับการอนุมัติ",
            content=f"ทางองค์กรได้อนุมัติคำขอของคุณแล้ว คุณสามารถมารับน้อง {adoption_req.dog.name} ได้ที่ศูนย์ หรือติดต่อเจ้าหน้าที่.",
            notification_type='DOG_SPECIFIC',
            dog=adoption_req.dog,
            organization=request.user, # The admin who approved
        )
        
        messages.success(request, f"อนุมัติคำขอของ {adoption_req.user.username} เรียบร้อยแล้ว")
        
    elif action == 'reject':
        adoption_req.status = 'REJECTED'
        adoption_req.save()
        messages.info(request, f"ปฏิเสธคำขอของ {adoption_req.user.username} แล้ว")
        
    return redirect('adoption_request_list')

