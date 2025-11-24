
from .forms import DogForm, DogImageFormSet
from django.shortcuts import render, redirect ,get_object_or_404
from django.contrib.auth import authenticate, login as auth_login
from django.contrib import messages
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.decorators import login_required

from .models import Dog, DogImage, User, Organization

# ---------- UI Render Views ----------
@login_required
def dog_list(request):
    # กรองเอาเฉพาะสุนัขที่ผู้ใช้ที่เข้าสู่ระบบเป็นเจ้าของเท่านั้น
    # (สมมติว่าคุณได้ตั้งค่า owner = models.ForeignKey(User, ...) ไว้แล้ว)
    my_dogs = Dog.objects.filter(owner=request.user).order_by('-id')

    context = {
        'dogs': my_dogs,
        'has_dogs': my_dogs.exists()
    }
    return render(request, 'myapp/dog_list.html', context)


@login_required
def dog_detail(request, dog_id):
    # 1. ตรวจสอบสิทธิ์: ค้นหาสุนัขด้วย ID และต้องเป็นของเจ้าของปัจจุบันเท่านั้น
    dog = get_object_or_404(
        Dog, 
        pk=dog_id, 
        owner=request.user
    )
    
    # ตรวจสอบว่าอยู่ในโหมดแก้ไขหรือไม่
    is_edit_mode = request.GET.get('edit', 'false').lower() == 'true'
    
    if request.method == 'POST':
        # --- สำหรับการบันทึกข้อมูล (Edit/Update) ---
        
        # ⚠️ การแก้ไข: ต้องส่ง instance=dog เพื่อให้ฟอร์มโหลดข้อมูลเดิมมาแก้ไข
        form = DogForm(request.POST, instance=dog)
        # ⚠️ สำหรับ FormSet: ต้องส่ง request.FILES และ instance=dog ด้วย
        formset = DogImageFormSet(request.POST, request.FILES, instance=dog) 

        if form.is_valid() and formset.is_valid():
            # 2. บันทึก Dog Model หลัก
            dog = form.save()
            
            # 3. บันทึกรูปภาพที่เกี่ยวข้อง (จัดการการลบ/แก้ไข/เพิ่มรูปภาพ)
            # formset.save() จะลบ objects ที่ถูก mark ให้ลบ และ signal จะลบไฟล์ให้อัตโนมัติ
            formset.save() 
            
            # 4. แสดงข้อความสำเร็จและ Redirect กลับไปหน้าแสดงผล
            messages.success(request, f'แก้ไขข้อมูลสุนัข "{dog.name}" สำเร็จแล้ว!')
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
        form = DogForm(instance=dog) 
        
        # 6. โหลดรูปภาพที่มีอยู่เดิมเข้าสู่ FormSet
        formset = DogImageFormSet(instance=dog) 

    # ดึงรูปภาพทั้งหมดของสุนัขตัวนี้สำหรับแสดงผล (ทั้งใน FormSet และส่วนแสดงรายละเอียด)
    dog_images = dog.images.all() 

    context = {
        'dog': dog,
        'form': form, # ส่งฟอร์มสำหรับแสดงผล
        'formset': formset, # ส่ง FormSet สำหรับแสดงผล
        'dog_images': dog_images, 
        'gender_display': dog.get_gender_display(),
        'size_display': dog.get_size_display(),
        'is_edit_mode': is_edit_mode, # ส่งสถานะโหมดแก้ไข
    }
    return render(request, 'myapp/dog_detail.html', context)

@login_required # บังคับให้ผู้ใช้ต้องเข้าสู่ระบบก่อน
def register_dog_page(request):
    if request.method == 'POST':
        form = DogForm(request.POST)
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
            messages.success(request, f'ลงทะเบียนสุนัข "{dog.name}" สำเร็จแล้ว!')
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
        form = DogForm()
        formset = DogImageFormSet(queryset=DogImage.objects.none()) # ฟอร์มเซ็ตเปล่า

    context = {
        'form': form,
        'formset': formset,
    }
    return render(request, 'myapp/registerdog.html', context)

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
            messages.success(request, 'สมัครสมาชิกสำเร็จ! กรุณาเข้าสู่ระบบ')
            return redirect('login')
        except Exception as e:
            messages.error(request, f'เกิดข้อผิดพลาด: {str(e)}')
            return render(request, 'myapp/registeruser.html')
    
    return render(request, 'myapp/registeruser.html')

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
        
        if user.is_active == False:
            messages.error(request, 'บัญชีผู้ใช้งานนี้ถูกระงับการใช้งาน')
            return render(request, 'myapp/loginuser.html')
        
        if user.is_staff:
            return redirect('admin_page')
            # return render(request, 'admin/index.html')

        if user is not None:
            auth_login(request, user)
            return redirect('home')
        else:
            messages.error(request, 'ชื่อผู้ใช้งานหรือรหัสผ่านไม่ถูกต้อง')
            return render(request, 'myapp/loginuser.html')
    return render(request, 'myapp/loginuser.html')

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
def home(request):
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
        messages.success(request, f'ลบสุนัข "{dog_name}" ออกจากระบบสำเร็จแล้ว!')
        return redirect('dog_list')
    
    # ถ้าเป็น GET request ให้ redirect กลับไปหน้า detail (modal จะแสดงในหน้า detail)
    return redirect('dog_detail', dog_id=dog_id)    