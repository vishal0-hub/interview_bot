from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('upload/', views.upload_resume, name='upload_resume'),
    path('interview/<int:session_id>/', views.interview_question, name='interview_question'),
    path('interview/<int:session_id>/question/', views.get_current_question, name='get_current_question'),
    path('interview/<int:session_id>/answer/', views.submit_answer, name='submit_answer'),
    path('interview/<int:session_id>/report/', views.interview_report, name='interview_report'),
]
