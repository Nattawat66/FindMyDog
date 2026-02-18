# urls.py
from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views
from . import views_admin
# from .views import debug_cache

urlpatterns = [
    path("", views.home, name="home"),
    path("home/", views.home, name="home"),
    path("register/", views.register, name="register"),
    path('logout/', LogoutView.as_view(), name='logout'),
    path("login/", views.login, name="login"),
    path('admin_page/user/<int:user_id>/update_role/', views_admin.admin_update_user_role, name='admin_update_user_role'),
    path('admin_page/user/<int:user_id>/delete/', views_admin.admin_delete_user, name='admin_delete_user'),
    path('admin_page/dog/<int:dog_id>/delete/', views_admin.admin_delete_dog, name='admin_delete_dog'),
    
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

    # URL สำหรับเกี่ยวกับจัดการ model-----------------------------------------------------------
    path('admin_page/', views_admin.admin_page, name='admin_page'),
    path('SetautoTraining/', views_admin.set_auto_training, name='set_auto_training'),
    path('model/retrain/', views_admin.set_time_auto_training, name='retrain_model'),
    path('dogs/<int:dog_id>/request_adoption/', views_admin.request_adoption_view, name='request_adoption'),
    path('adoption_requests/', views_admin.adoption_request_list_view, name='adoption_request_list'),
    path('adoption_requests/<int:request_id>/<str:action>/', views_admin.handle_adoption_request_view, name='handle_adoption_request'),
    path('page/testEMBmodel/', views_admin.page_testEMBmodel, name='testEMBmodel'),
    path('train-knn/', views_admin.train_knn_view, name='train_knn'),
    path('history-knn/', views_admin.knn_test_history_view, name='history_knn'),

    path('page/select-model/', views_admin.page_select_model, name='page_select_model'),
    
    path('page_testEMBmodel/', views_admin.page_testEMBmodel, name='page_testEMBmodel'),
    
    # API endpoint for getting KNN result data
    path('api/knn-result/<int:result_id>/', views_admin.get_knn_result_api, name='get_knn_result_api'),
    # API endpoint for CPU stats
    path('api/cpu-stats/', views_admin.get_cpu_stats, name='get_cpu_stats'),
    # path('trainKNN/', views.trigger_train_knn, name='trainKNN')
    path("api/server-time/", views.server_time),


]
