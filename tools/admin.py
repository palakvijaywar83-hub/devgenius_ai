from django.contrib import admin

from .models import BugReport, CodeExplanation, Documentation, LearningSession, Quiz, QuizAttempt, QuizQuestion

for m in (CodeExplanation, BugReport, LearningSession, Quiz, QuizQuestion, QuizAttempt, Documentation):
    admin.site.register(m)
