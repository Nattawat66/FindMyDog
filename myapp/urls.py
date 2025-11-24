# urls.py
from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views

urlpatterns = [
    path("home/", views.home, name="home"),
    path("register/", views.register, name="register"),
    path('logout/', LogoutView.as_view(), name='logout'),
    path("login/", views.login, name="login"),
    path('admin_page/', views.admin_page, name='admin_page'),

    path('dog/register/', views.register_dog_page, name='register_dog_page'),
    path('dogs/', views.dog_list, name='dog_list'),
    path('dogs/<int:dog_id>/', views.dog_detail, name='dog_detail'),
    path('dogs/<int:dog_id>/delete/', views.delete_dog_page, name='delete_dog_page'),
]
