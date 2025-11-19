# users/forms.py

from django import forms
from .models import Dog, DogImage

# --- 1. Form สำหรับข้อมูลสุนัข ---
class DogForm(forms.ModelForm):
    class Meta:
        model = Dog
        # ไม่ต้องรวม 'owner' และ 'organization' เพราะเราจะกำหนดค่าเหล่านี้ใน View
        fields = [
            'name', 'gender', 'age', 'breed', 
            'primary_color', 'secondary_color', 'size', 
            'weight', 'distinguishing_marks', 
            'personality', 'favorite_food', 'allergies', 
            'is_lost'
        ]
        widgets = {
            # ใช้ Textarea สำหรับฟิลด์ข้อความหลายบรรทัด
            'personality': forms.Textarea(attrs={'rows': 3}),
            'favorite_food': forms.Textarea(attrs={'rows': 3}),
            'allergies': forms.Textarea(attrs={'rows': 3}),
            'distinguishing_marks': forms.Textarea(attrs={'rows': 3}),
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

# --- 3. FormSet สำหรับจัดการหลายรูปภาพใน View ---
DogImageFormSet = forms.inlineformset_factory(
    Dog, 
    DogImage, 
    form=DogImageForm, 
    extra=1,          # แสดงฟิลด์อัปโหลดรูปภาพใหม่ 1 ช่อง
    max_num=5,        
    can_delete=True # ⚠️ สำคัญมาก: อนุญาตให้ลบรายการที่มีอยู่ได้
)