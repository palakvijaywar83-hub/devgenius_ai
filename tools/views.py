import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import ai_service
from .ai_service import AIInvalidResponse, AINotConfigured, AIRateLimited, AIServiceError
from .forms import BugForm, DocForm, ExplainForm, QuizForm, TutorForm
from .models import (
    BugReport, CodeExplanation, Documentation, LearningSession, Quiz, QuizAttempt, QuizQuestion,
)

logger = logging.getLogger(__name__)
HISTORY_LIMIT = 8
MAX_FOLLOWUPS = 20


def _owned(model, request, pk):
    """Fetch a record only if it belongs to the current user (404 otherwise)."""
    return get_object_or_404(model, pk=pk, user=request.user)


def _delete(request, model, pk, redirect_to):
    obj = _owned(model, request, pk)
    obj.delete()
    messages.success(request, "Deleted.")
    return redirect(redirect_to)


# ------------------------------------------------------------------ explain
@login_required
def explain(request):
    form = ExplainForm(request.POST or None)
    error = None
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        try:
            result = ai_service.run("explain", d, user_key=request.user.pk)
        except AIServiceError as exc:
            error = exc
        else:
            obj = CodeExplanation.objects.create(
                user=request.user, language=d["language"], level=d["level"], code=d["code"], result=result
            )
            return redirect(obj)
    history = CodeExplanation.objects.filter(user=request.user)[:HISTORY_LIMIT]
    return render(request, "tools/explain.html", {"form": form, "error": error, "history": history})


@login_required
def explain_detail(request, pk):
    return render(request, "tools/explain_detail.html", {"obj": _owned(CodeExplanation, request, pk)})


@login_required
@require_POST
def explain_save(request, pk):
    obj = _owned(CodeExplanation, request, pk)
    obj.is_saved = not obj.is_saved
    obj.save(update_fields=["is_saved"])
    messages.success(request, "Saved to your dashboard." if obj.is_saved else "Removed from saved.")
    return redirect(obj)


@login_required
@require_POST
def explain_delete(request, pk):
    return _delete(request, CodeExplanation, pk, "tools:explain")


# -------------------------------------------------------------------- debug
@login_required
def debug(request):
    form = BugForm(request.POST or None)
    error = None
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        try:
            result = ai_service.run("debug", d, user_key=request.user.pk)
        except AIServiceError as exc:
            error = exc
        else:
            obj = BugReport.objects.create(
                user=request.user, language=d["language"], code=d["code"],
                error_message=d["error_message"], expected_behavior=d["expected_behavior"], result=result,
            )
            return redirect(obj)
    history = BugReport.objects.filter(user=request.user)[:HISTORY_LIMIT]
    return render(request, "tools/debug.html", {"form": form, "error": error, "history": history})


@login_required
def debug_detail(request, pk):
    return render(request, "tools/debug_detail.html", {"obj": _owned(BugReport, request, pk)})


@login_required
@require_POST
def debug_delete(request, pk):
    return _delete(request, BugReport, pk, "tools:debug")


# -------------------------------------------------------------------- tutor
@login_required
def tutor(request):
    form = TutorForm(request.POST or None)
    error = None
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        try:
            result = ai_service.run("tutor", d, user_key=request.user.pk)
        except AIServiceError as exc:
            error = exc
        else:
            obj = LearningSession.objects.create(
                user=request.user, subject=d["subject"], topic=d["topic"],
                level=d["level"], style=d["style"], result=result,
            )
            return redirect(obj)
    history = LearningSession.objects.filter(user=request.user)[:HISTORY_LIMIT]
    return render(request, "tools/tutor.html", {"form": form, "error": error, "history": history})


@login_required
def tutor_detail(request, pk):
    return render(request, "tools/tutor_detail.html", {"obj": _owned(LearningSession, request, pk)})


@login_required
@require_POST
def tutor_followup(request, pk):
    session = _owned(LearningSession, request, pk)
    try:
        question = str(json.loads(request.body or b"{}").get("question", "")).strip()
    except (ValueError, AttributeError):
        question = ""
    if not question or len(question) > 500:
        return JsonResponse({"error": "Enter a question of up to 500 characters."}, status=400)
    if len(session.followups) >= MAX_FOLLOWUPS:
        return JsonResponse({"error": "This session reached its follow-up limit. Start a new session."}, status=400)

    data = {
        "subject": session.subject, "topic": session.topic, "level": session.level,
        "style": session.style, "question": question, "history": session.followups,
    }
    try:
        result = ai_service.run("tutor_followup", data, user_key=request.user.pk)
    except AINotConfigured as exc:
        return JsonResponse({"error": exc.user_message}, status=503)
    except AIRateLimited as exc:
        return JsonResponse({"error": exc.user_message}, status=429)
    except AIServiceError as exc:
        return JsonResponse({"error": exc.user_message}, status=502)

    session.followups = [*session.followups, {"question": question, "answer": result["answer"]}]
    session.save(update_fields=["followups"])
    return JsonResponse({"question": question, "answer": result["answer"]})


@login_required
@require_POST
def tutor_delete(request, pk):
    return _delete(request, LearningSession, pk, "tools:tutor")


# --------------------------------------------------------------------- quiz
@login_required
def quiz(request):
    form = QuizForm(request.POST or None)
    error = None
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        try:
            result = ai_service.run("quiz", d, user_key=request.user.pk)
        except AIServiceError as exc:
            error = exc
        else:
            with transaction.atomic():
                quiz_obj = Quiz.objects.create(
                    user=request.user, language=d["language"], topic=d["topic"], difficulty=d["difficulty"]
                )
                QuizQuestion.objects.bulk_create(
                    QuizQuestion(
                        quiz=quiz_obj, order=i, text=q["question"], options=q["options"],
                        correct_index=q["correct_index"], explanation=q["explanation"],
                    )
                    for i, q in enumerate(result["questions"], start=1)
                )
            return redirect(quiz_obj)
    quizzes = Quiz.objects.filter(user=request.user).prefetch_related("attempts", "questions")[:15]
    attempts = QuizAttempt.objects.filter(user=request.user).select_related("quiz")[:10]
    return render(request, "tools/quiz.html", {"form": form, "error": error, "quizzes": quizzes, "attempts": attempts})


@login_required
def quiz_take(request, pk):
    # Correct answers are never sent to the browser on this page.
    quiz_obj = _owned(Quiz, request, pk)
    return render(request, "tools/quiz_take.html", {"quiz": quiz_obj, "questions": quiz_obj.questions.all()})


@login_required
@require_POST
def quiz_submit(request, pk):
    quiz_obj = _owned(Quiz, request, pk)
    questions = list(quiz_obj.questions.all())
    answers, score = [], 0
    for q in questions:
        raw = request.POST.get(f"q_{q.pk}", "")
        choice = int(raw) if raw.isdecimal() and int(raw) < len(q.options) else None
        answers.append(choice)
        if choice == q.correct_index:
            score += 1
    attempt = QuizAttempt.objects.create(
        user=request.user, quiz=quiz_obj, score=score, total=len(questions), answers=answers
    )
    return redirect(attempt)


@login_required
def quiz_result(request, pk):
    attempt = get_object_or_404(QuizAttempt.objects.select_related("quiz"), pk=pk, user=request.user)
    rows = []
    for q, chosen in zip(attempt.quiz.questions.all(), attempt.answers):
        rows.append({
            "q": q, "chosen": chosen,
            "chosen_text": q.options[chosen] if chosen is not None and chosen < len(q.options) else None,
            "correct_text": q.options[q.correct_index],
            "is_correct": chosen == q.correct_index,
        })
    return render(request, "tools/quiz_result.html", {"attempt": attempt, "rows": rows})


@login_required
@require_POST
def quiz_delete(request, pk):
    return _delete(request, Quiz, pk, "tools:quiz")


# --------------------------------------------------------------------- docs
@login_required
def docs(request):
    form = DocForm(request.POST or None)
    error = None
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        try:
            result = ai_service.run("docs", d, user_key=request.user.pk)
        except AIServiceError as exc:
            error = exc
        else:
            obj = Documentation.objects.create(
                user=request.user, title=(d["title"] or result["title"] or "Untitled documentation")[:160],
                source_type=d["source_type"], input_text=d["content"], content=result["markdown"],
            )
            return redirect(obj)
    history = Documentation.objects.filter(user=request.user)[:HISTORY_LIMIT]
    return render(request, "tools/docs.html", {"form": form, "error": error, "history": history})


@login_required
def docs_detail(request, pk):
    return render(request, "tools/docs_detail.html", {"obj": _owned(Documentation, request, pk)})


@login_required
@require_POST
def docs_delete(request, pk):
    return _delete(request, Documentation, pk, "tools:docs")
