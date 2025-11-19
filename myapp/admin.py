from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import User, Organization, Dog, DogImage, LostDogReport, FoundDogReport, FoundDogImage


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("username", "email", "role", "location_lat", "location_lng")
    list_filter = ("role",)
    search_fields = ("username", "email", "phone", "line_id")


@admin.register(Dog)
class DogAdmin(admin.ModelAdmin):
    list_display = ("name", "age", "owner", "organization")
    search_fields = ("name", "owner__username", "organization__name")


admin.site.register(Organization)
admin.site.register(DogImage)
admin.site.register(LostDogReport)
admin.site.register(FoundDogReport)
admin.site.register(FoundDogImage)
