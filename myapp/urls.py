# urls.py
from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views
# from .views import debug_cache

urlpatterns = [
    path("", views.home, name="home"),
    path("home/", views.home, name="home"),
    path("register/", views.register, name="register"),
    path('logout/', LogoutView.as_view(), name='logout'),
    path("login/", views.login, name="login"),
    path('admin_page/', views.admin_page, name='admin_page'),
    
    path('dog/register/', views.register_dog_page, name='register_dog_page'),
    path('dogs/', views.dog_list, name='dog_list'),
    path('dogsall/', views.dog_all_list, name='dog_all_list'),
    path('dogs/<int:dog_id>/', views.dog_detail, name='dog_detail'),
    path('notifications/', views.notification_list_view, name='notification_list'),
    path('notifications/create/', views.create_notification_view, name='create_notification'),
    path('notifications/<int:notification_id>/detail_hx/', views.notification_detail_hx_view, name='notification_detail_hx'),
    path('notifications/<int:notification_id>/edit/', views.edit_notification_view, name='edit_notification'),
    path('notifications/<int:notification_id>/delete/', views.delete_notification_view, name='delete_notification'),
    path('dogs/<int:dog_id>/delete/', views.delete_dog_page, name='delete_dog_page'),
    path('profile/',views.user_profile_view,name='user_profile'),
    path('SetautoTraining/', views.set_auto_training, name='set_auto_training'),

    #URL สำหรับ JSON Map Data (Backend API)
    path('api/lost_dogs/map_data/', views.lost_dogs_map_data, name='lost_dogs_map_data_api'),
    
    #URL สำหรับหน้าแผนที่
    path(
        'lost_dogs/map/', 
        views.lost_dogs_map_view, 
        name='lost_dogs_map_view'
    ),
    
    
    path(
        'dog/<int:dog_id>/report_lost/map/', 
        views.report_lost_dog_view, 
        name='report_lost_dog'
    ),
    
    path(
        'api/lost_dogs/map_data/', 
        views.lost_dogs_map_data, 
        name='lost_dogs_map_data_api'
    ),
    path('matchdog/', views.matchdog, name='matchdog'),


    # URL สำหรับเกี่ยวกับจัดการ model
    path('model/retrain/', views.set_time_auto_training, name='retrain_model'),
    # path("debug/cache/", debug_cache),
    path('train-knn/', views.train_knn_view, name='train_knn')
    ]

