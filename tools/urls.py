from django.urls import path

from . import views

app_name = "tools"

urlpatterns = [
    path("explain/", views.explain, name="explain"),
    path("explain/<int:pk>/", views.explain_detail, name="explain_detail"),
    path("explain/<int:pk>/save/", views.explain_save, name="explain_save"),
    path("explain/<int:pk>/delete/", views.explain_delete, name="explain_delete"),

    path("debug/", views.debug, name="debug"),
    path("debug/<int:pk>/", views.debug_detail, name="debug_detail"),
    path("debug/<int:pk>/delete/", views.debug_delete, name="debug_delete"),

    path("tutor/", views.tutor, name="tutor"),
    path("tutor/<int:pk>/", views.tutor_detail, name="tutor_detail"),
    path("tutor/<int:pk>/followup/", views.tutor_followup, name="tutor_followup"),
    path("tutor/<int:pk>/delete/", views.tutor_delete, name="tutor_delete"),

    path("quiz/", views.quiz, name="quiz"),
    path("quiz/<int:pk>/", views.quiz_take, name="quiz_take"),
    path("quiz/<int:pk>/submit/", views.quiz_submit, name="quiz_submit"),
    path("quiz/<int:pk>/delete/", views.quiz_delete, name="quiz_delete"),
    path("quiz/attempt/<int:pk>/", views.quiz_result, name="quiz_result"),

    path("docs/", views.docs, name="docs"),
    path("docs/<int:pk>/", views.docs_detail, name="docs_detail"),
    path("docs/<int:pk>/delete/", views.docs_delete, name="docs_delete"),
]
