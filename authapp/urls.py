from django.urls import path

from .views import login_page, student_login

urlpatterns = [
    path('', login_page, name='login-page'),
    path('api/auth/student-login/', student_login, name='student-login'),
]