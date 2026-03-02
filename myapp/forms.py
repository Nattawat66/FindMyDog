# users/forms.py

from django import forms
from django.db.models import Q
from .models import Dog, DogImage,Notification,User
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError


class UserRegisterForm(forms.Form):
    username = forms.CharField(max_length=150)
    email = forms.EmailField(required=False)
    password = forms.CharField(widget=forms.PasswordInput)
    password_confirm = forms.CharField(widget=forms.PasswordInput)
    phone = forms.CharField(required=False)
    line_id = forms.CharField(required=False)

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise ValidationError("ชื่อผู้ใช้งานนี้มีอยู่ในระบบแล้ว")
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email=email).exists():
            raise ValidationError("อีเมลนี้มีอยู่ในระบบแล้ว")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")

        if password and password_confirm and password != password_confirm:
            raise ValidationError("รหัสผ่านไม่ตรงกัน")

        return cleaned_data

    def save(self):
        user = User.objects.create_user(
            username=self.cleaned_data['username'],
            email=self.cleaned_data.get('email', ''),
            password=self.cleaned_data['password']
        )
        user.phone = self.cleaned_data.get('phone')
        user.line_id = self.cleaned_data.get('line_id')
        user.save()
        return user



class LoginForm(forms.Form):
    username = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput)

    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get("username")
        password = cleaned_data.get("password")

        if not username or not password:
            raise ValidationError("กรุณากรอกชื่อผู้ใช้งานและรหัสผ่าน")

        user = authenticate(username=username, password=password)

        if user is None:
            raise ValidationError("ชื่อผู้ใช้งานหรือรหัสผ่านไม่ถูกต้อง")

        if not user.is_active:
            raise ValidationError("บัญชีผู้ใช้งานนี้ถูกระงับการใช้งาน")

        self.user = user
        return cleaned_data

    def get_user(self):
        return self.user
    
# --- 1. Form สำหรับข้อมูลสุนัข ---

class DogForm(forms.ModelForm):
        
    ISLOST_CHOICES = [
        (True, "สูญหาย"),
        (False, "ปกติ"),
    ]

    # override ฟิลด์จาก Model เพื่อใช้ radio + label
    is_lost = forms.TypedChoiceField(
        choices=ISLOST_CHOICES,
        coerce=lambda x: x == 'True',  # แปลงค่าจาก form ให้เป็น Boolean จริง
        widget=forms.RadioSelect,
        label="สถานะ",
    )
    
    class Meta:
        model = Dog
        # ไม่ต้องรวม 'owner' และ 'organization' เพราะเราจะกำหนดค่าเหล่านี้ใน View
        fields = [
            'name', 'gender', 'age', 'is_lost',
            'primary_color', 'secondary_color', 'size','distinguishing_marks', 
            'personality', 'favorite_food', 'allergies'
        ]
        
        widgets = {
            # ใช้ Textarea สำหรับฟิลด์ข้อความหลายบรรทัด
            'name': forms.TextInput(attrs={'placeholder': 'บัดดี้'}),
            'age': forms.NumberInput(attrs={'placeholder': '2(หน่วยเป็นปี)'}),
            'gender': forms.Select(attrs={'placeholder': 'เลือกเพศ'}),
            'personality': forms.Textarea(attrs={'rows': 3, 'placeholder': 'ใจดี เป็นมิตร'}),
            'favorite_food': forms.Textarea(attrs={'rows': 3, 'placeholder': 'ชอบกินโครงไก่'}),
            'allergies': forms.Textarea(attrs={'rows': 3, 'placeholder': 'กินนมวัวไม่ได้'}),
            'distinguishing_marks': forms.Textarea(attrs={'rows': 3, 'placeholder': 'หูตั้งตา2สี'}),
            'primary_color': forms.TextInput(attrs={'placeholder': 'ดำ'}),
            'secondary_color': forms.TextInput(attrs={'placeholder': 'น้ำตาล'}),
            # 'size': forms.Select(attrs={'placeholder': 'เลือกขนาด'}),
        }
        

    # เพื่อเพิ่มคลาส Tailwind/DaisyUI ให้กับ Input Fields ทั้งหมด
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            # สำหรับ CharField, TextField, IntegerField, DecimalField
            if isinstance(field.widget, (forms.TextInput, forms.Textarea, forms.NumberInput)):
                field.widget.attrs.update({
                    'class': 'input input-bordered w-full'
                })
            # สำหรับ Select/Choices (Gender, Size)
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.update({
                    'class': 'select select-bordered w-full'
                })
            # สำหรับ Checkbox (is_lost)
            elif isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({
                    'class': 'checkbox checkbox-primary'
                })
                
# --- 2. Form สำหรับรูปภาพสุนัข ---
class DogImageForm(forms.ModelForm):
    class Meta:
        model = DogImage
        fields = ['image']


VACCINE_CHOICES = [
    ('DHPPL', 'วัคซีนรวม (DHPPL/7โรค)'),
    ('Rabies', 'วัคซีนพิษสุนัขบ้า'),
    ('Kennel_Cough', 'วัคซีนป้องกันไอ (Kennel Cough)'),
]

class OrgAdminDogForm(DogForm): # 💡 สืบทอดจาก DogForm เพื่อนำฟิลด์พื้นฐานมาทั้งหมด
    
    # 2.1. Form Field สำหรับวัคซีน (ใช้ Multiple Checkbox)
    vaccine_selection = forms.MultipleChoiceField(
        choices=VACCINE_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'checkbox-list space-y-2'}),
        label="วัคซีนที่ฉีดแล้ว"
    )
    
    class Meta(DogForm.Meta):
        # 💡 เพิ่มฟิลด์ที่ Admin ต้องการลงใน Meta.fields
        fields = DogForm.Meta.fields + [
            'vaccination_history', 
            'sterilization_status', 
            'sterilization_date'
        ]
        widgets = {
             # กำหนด widget สำหรับฟิลด์ Date
            'sterilization_date': forms.DateInput(attrs={'class': 'input input-bordered w-full', 'type': 'date'}),
             # กำหนด widget สำหรับฟิลด์ Select
            'sterilization_status': forms.Select(attrs={'class': 'select select-bordered w-full'}),
            # vaccination_history จะถูกซ่อน (hidden) และจัดการผ่าน vaccine_selection
            'vaccination_history': forms.HiddenInput(),
                        'name': forms.TextInput(attrs={'placeholder': 'บัดดี้'}),
            'age': forms.NumberInput(attrs={'placeholder': '2(หน่วยเป็นปี)'}),
            'gender': forms.Select(attrs={'placeholder': 'เลือกเพศ'}),
            'personality': forms.Textarea(attrs={'rows': 3, 'placeholder': 'ใจดี เป็นมิตร'}),
            'favorite_food': forms.Textarea(attrs={'rows': 3, 'placeholder': 'ชอบกินโครงไก่'}),
            'allergies': forms.Textarea(attrs={'rows': 3, 'placeholder': 'กินนมวัวไม่ได้'}),
            'distinguishing_marks': forms.Textarea(attrs={'rows': 3, 'placeholder': 'หูตั้งตา2สี'}),
            'primary_color': forms.TextInput(attrs={'placeholder': 'ดำ'}),
            'secondary_color': forms.TextInput(attrs={'placeholder': 'น้ำตาล'}),
            
        }


    # 2.2. Override __init__ เพื่อโหลดค่าวัคซีนจาก Model (String -> List)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 1. โหลดค่าวัคซีน (Logic เดิม)
        if self.instance and self.instance.vaccination_history:
            initial_vaccines = [v.strip() for v in self.instance.vaccination_history.split(',') if v.strip()]
            self.fields['vaccine_selection'].initial = initial_vaccines

        # 💡 2. [การแก้ไข]: กำหนด CSS Class ให้ฟิลด์ที่เพิ่มเข้ามาใหม่
        # บังคับอัปเดต Widget Attribute อีกครั้งเพื่อให้แน่ใจว่าได้ class DaisyUI
        
        # ฟิลด์ sterilization_status (Select)
        self.fields['sterilization_status'].widget.attrs.update({
            'class': 'select select-bordered w-full'
        })
        
        # ฟิลด์ sterilization_date (Date Input)
        self.fields['sterilization_date'].widget.attrs.update({
            'class': 'input input-bordered w-full',
            'type': 'date' # ย้ำ type='date'
        })

    # 2.3. Override save() เพื่อบันทึกค่าวัคซีนกลับสู่ Model (List -> String)
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # แปลง List ของวัคซีนที่เลือก ให้เป็น String คั่นด้วยคอมมา
        vaccine_list = self.cleaned_data.get('vaccine_selection', [])
        instance.vaccination_history = ', '.join(vaccine_list)
        if hasattr(instance, 'organization'):
            instance.organization = True
        # ค่า sterilization_status และ date จะถูกบันทึกโดย super().save()
        
        if commit:
            instance.save()
        return instance
    
# --- 3. FormSet สำหรับจัดการหลายรูปภาพใน View ---
DogImageFormSet = forms.inlineformset_factory(
    Dog, 
    DogImage, 
    form=DogImageForm, 
    extra=1,          # แสดงฟิลด์อัปโหลดรูปภาพใหม่ 1 ช่อง
    max_num=5,        
    can_delete=True # ⚠️ สำคัญมาก: อนุญาตให้ลบรายการที่มีอยู่ได้
)

class NotificationForm(forms.ModelForm):
    
    class Meta:
        model = Notification
        fields = [
            'title', 
            'content', 
            'notification_type', 
            'image', 
            'is_important', 
            'dog'
        ]
        
        widgets = {
            'title': forms.TextInput(attrs={'class': 'input input-bordered w-full input-lg', 'placeholder': 'หัวข้อข่าวสาร...'}),
            'content': forms.Textarea(attrs={'class': 'textarea textarea-bordered w-full h-48', 'placeholder': 'รายละเอียดข่าวสาร...'}),
            'notification_type': forms.Select(attrs={'class': 'select select-bordered w-full select-lg'}),
            'is_important': forms.CheckboxInput(attrs={'class': 'checkbox checkbox-primary'}),
            # 💡 'dog' (สุนัขที่เกี่ยวข้อง) จะถูกซ่อนหรือกรองใน View/Template ขึ้นอยู่กับประเภท
            'dog': forms.Select(attrs={'class': 'select select-bordered w-full select-lg'}),
        }
        labels = {
            'title': "หัวข้อ",
            'content': "รายละเอียด",
            'notification_type': "ประเภทข่าวสาร",
            'image': "รูปภาพประกอบ (ถ้ามี)",
            'is_important': "ทำเครื่องหมายว่า 'สำคัญมาก' ",
            'dog': "สุนัขที่เกี่ยวข้อง (เฉพาะประเภท 'ประกาศเฉพาะสุนัข')"
        }

    # 1.2 Override __init__ เพื่อให้ Admin องค์กรเห็นเฉพาะสุนัขในความดูแล
    def __init__(self, *args, **kwargs):
        # รับ user เข้ามาเพื่อกรองสุนัขในฟิลด์ 'dog'
        self.user = kwargs.pop('user', None) 
        super().__init__(*args, **kwargs)
        
        # กรองตัวเลือกในฟิลด์ 'dog' ให้เหลือแต่สุนัขที่สังกัดองค์กรของ Admin คนนี้
        if self.user and self.user.role == 'org_admin':
            # กรองสุนัขที่อยู่ในการดูแลของโฮงเกลือหมา (organization=True) 
            # หรือสุนัขที่ org_admin คนนี้เป็นเจ้าของ (owner=self.user)
            self.fields['dog'].queryset = Dog.objects.filter(
                Q(organization=True) | Q(owner=self.user)
            )
        else:
            # ถ้าไม่ใช่ Admin องค์กร อาจจะซ่อนฟิลด์ dog ไปเลย
            self.fields['dog'].widget = forms.HiddenInput()
            self.fields['dog'].required = False
            
            
class ReportLostForm(forms.ModelForm):
    # 💡 เราจะแสดงฟิลด์เหล่านี้เป็น Input ที่ซ่อนไว้ (Hidden Input) 
    # เพื่อให้ JavaScript ทำการบันทึกค่าพิกัดลงไป
    lost_latitude = forms.DecimalField(
        required=True, 
        widget=forms.HiddenInput(), 
        max_digits=9, 
        decimal_places=6
    )
    lost_longitude = forms.DecimalField(
        required=True, 
        widget=forms.HiddenInput(), 
        max_digits=9, 
        decimal_places=6
    )
    
    # ฟิลด์ที่ผู้ใช้เห็นและกรอก
    lost_location_description = forms.CharField(
        required=False, 
        widget=forms.Textarea(attrs={'class': 'textarea textarea-bordered w-full h-20', 'placeholder': 'อธิบายสถานที่สูญหายโดยสังเขป...'}),
        label="รายละเอียดสถานที่สูญหายเพิ่มเติม"
    )
    
    class Meta:
        model = Dog
        fields = [
            'lost_latitude', 
            'lost_longitude', 
            'lost_location_description', 
            # ไม่ต้องใส่ 'is_lost' เพราะเราจะกำหนดเป็น True ใน View
        ]


# forms.py
# forms.py
from django import forms
from .models import TrainingConfig
import re

# forms.py
from django import forms
from .models import TrainingConfig
import re

class TrainingScheduleForm(forms.ModelForm):
    class Meta:
        model = TrainingConfig
        fields = ['scheduled_time', 'frequency', 'is_active']

        widgets = {
            'scheduled_time': forms.TimeInput(attrs={'class': 'input input-bordered w-full', 'type': 'time'}),
            'frequency': forms.Select(attrs={'class': 'select select-bordered w-full'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'checkbox checkbox-primary'}),
        }

    def clean_scheduled_time(self):
        v = self.cleaned_data['scheduled_time']
        if not re.match(r'^\d{2}:\d{2}$', v):
            raise forms.ValidationError("ใช้รูปแบบ HH:MM")
        return v

