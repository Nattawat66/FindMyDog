
from .forms import DogForm, DogImageFormSet,OrgAdminDogForm,VACCINE_CHOICES,NotificationForm
from django.shortcuts import render, redirect ,get_object_or_404
from django.http import Http404
from django.contrib.auth import authenticate, login as auth_login
from django.contrib import messages
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.decorators import login_required
from .models import Dog, DogImage, User,Notification, AdoptionParent
from django.db.models import Q
from django.db import models



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
            # 2. บันทึก Dog Model หลัก
            dog = form.save()
            
            # 3. บันทึกรูปภาพที่เกี่ยวข้อง (จัดการการลบ/แก้ไข/เพิ่มรูปภาพ)
            # formset.save() จะลบ objects ที่ถูก mark ให้ลบ และ signal จะลบไฟล์ให้อัตโนมัติ
            formset.save() 
            
            # 4. แสดงข้อความสำเร็จและ Redirect กลับไปหน้าแสดงผล
            # messages.success(request, f'แก้ไขข้อมูลสุนัข "{dog.name}" สำเร็จแล้ว!')
            return redirect('dog_detail', dog_id=dog.id) 
        else:
            # ถ้ามี error ให้อยู่ในโหมดแก้ไข
            is_edit_mode = True
            if not form.is_valid():
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f'{field}: {error}')
            if not formset.is_valid():
                for form_error in formset.errors:
                    for field, errors in form_error.items():
                        for error in errors:
                            messages.error(request, f'รูปภาพ: {error}')
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
            formset.save()  # Django FormSet จะจัดการ empty forms ให้เอง
            
            # 3. แสดงข้อความสำเร็จและ Redirect
            # messages.success(request, f'ลงทะเบียนสุนัข "{dog.name}" สำเร็จแล้ว!')
            return redirect('dog_list')
        else:
            # แสดง error messages ถ้ามี
            if not form.is_valid():
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f'{field}: {error}')
            if not formset.is_valid():
                for form_error in formset.errors:
                    for field, errors in form_error.items():
                        for error in errors:
                            messages.error(request, f'รูปภาพ: {error}') 
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

# @login_required
# def admin_page(request):
#     if not request.user.is_staff:
#         messages.error(request, 'คุณไม่มีสิทธิ์เข้าถึงหน้านี้')
#         return redirect('home')
#     return render(request, 'admin/index.html')
def admin_page(request):
    return render(request, 'admin/dashdoardAI/dashdoard.html')

def set_auto_training(request):
    return render(request, 'admin/Training/SetautoTraining.html')

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
        }
        return render(request, 'myapp/admin_org/admin_org_home.html',context)
    else:
        return render(request, 'myapp/home.html')


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
