from django.contrib import admin
from .models import InterviewSession, Question, Answer

admin.site.register(InterviewSession)
admin.site.register(Question)
admin.site.register(Answer)
