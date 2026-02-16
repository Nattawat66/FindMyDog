
from logging import config
from .forms import DogForm, DogImageFormSet,OrgAdminDogForm,VACCINE_CHOICES,NotificationForm,ReportLostForm,TrainingScheduleForm
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
apiurl = "http://127.0.0.1:8001/"
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

