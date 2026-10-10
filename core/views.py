from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from tools.models import (
    BugReport, CodeExplanation, Documentation, LearningSession, QuizAttempt,
)

FEED_PER_MODEL = 8


def landing(request):
    return render(request, "landing.html")


@login_required
def dashboard(request):
    u = request.user
    explanations = CodeExplanation.objects.filter(user=u)
    bugs = BugReport.objects.filter(user=u)
    sessions = LearningSession.objects.filter(user=u)
    attempts = QuizAttempt.objects.filter(user=u).select_related("quiz")
    docs = Documentation.objects.filter(user=u)

    stats = [
        ("Code explanations", explanations.count()),
        ("Bugs analysed", bugs.count()),
        ("Learning sessions", sessions.count()),
        ("Quizzes completed", attempts.count()),
        ("Docs generated", docs.count()),
    ]
    feed = [
        o
        for qs in (explanations, bugs, sessions, attempts, docs)
        for o in qs[:FEED_PER_MODEL]
    ]
    feed.sort(key=lambda o: o.created_at, reverse=True)

    return render(request, "dashboard.html", {
        "stats": stats,
        "activity": feed[:8],
        "saved": explanations.filter(is_saved=True)[:5],
        "recent_bugs": bugs[:5],
        "recent_attempts": attempts[:5],
        "recent_sessions": sessions[:5],
        "has_activity": any(c for _, c in stats),
    })


@login_required
def progress(request):
    u = request.user
    attempts = list(QuizAttempt.objects.filter(user=u).select_related("quiz"))
    sessions = list(LearningSession.objects.filter(user=u))

    total_correct = sum(a.score for a in attempts)
    total_questions = sum(a.total for a in attempts)
    overall = round(100 * total_correct / total_questions) if total_questions else None

    topics = {}
    for a in attempts:
        t = topics.setdefault(a.quiz.topic.strip().lower(), {"label": a.quiz.topic.strip(), "quizzes": 0, "sessions": 0, "c": 0, "q": 0})
        t["quizzes"] += 1
        t["c"] += a.score
        t["q"] += a.total
    for s in sessions:
        t = topics.setdefault(s.topic.strip().lower(), {"label": s.topic.strip(), "quizzes": 0, "sessions": 0, "c": 0, "q": 0})
        t["sessions"] += 1
    topic_rows = sorted(topics.values(), key=lambda t: t["quizzes"] + t["sessions"], reverse=True)
    for t in topic_rows:
        t["percent"] = round(100 * t["c"] / t["q"]) if t["q"] else None

    return render(request, "progress.html", {
        "completed": len(attempts),
        "overall": overall,
        "best": max((a.percent for a in attempts), default=None),
        "topic_rows": topic_rows,
        "recent_attempts": attempts[:8],
        "recent_sessions": sessions[:8],
    })
