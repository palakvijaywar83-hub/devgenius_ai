from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from tools.models import BugReport, CodeExplanation, LearningSession, Quiz, QuizAttempt


class DashboardTests(TestCase):
    def setUp(self):
        self.u = User.objects.create_user("alice", "a@example.com", "pass12345!x")
        self.other = User.objects.create_user("bob", "b@example.com", "pass12345!x")
        self.client.login(username="alice", password="pass12345!x")

    def test_empty_state_has_no_fabricated_stats(self):
        r = self.client.get(reverse("core:dashboard"))
        self.assertContains(r, "No activity yet")
        self.assertEqual([c for _, c in r.context["stats"]], [0, 0, 0, 0, 0])

    def test_stats_come_from_database_for_current_user_only(self):
        CodeExplanation.objects.create(user=self.u, language="Python", level="beginner", code="x", result={}, is_saved=True)
        CodeExplanation.objects.create(user=self.other, language="Python", level="beginner", code="y", result={})
        BugReport.objects.create(user=self.u, language="Python", code="x", error_message="E", result={})
        quiz = Quiz.objects.create(user=self.u, language="Python", topic="loops", difficulty="beginner")
        QuizAttempt.objects.create(user=self.u, quiz=quiz, score=2, total=4, answers=[])
        r = self.client.get(reverse("core:dashboard"))
        stats = dict(r.context["stats"])
        self.assertEqual(stats["Code explanations"], 1)
        self.assertEqual(stats["Bugs analysed"], 1)
        self.assertEqual(stats["Quizzes completed"], 1)
        self.assertEqual(len(r.context["saved"]), 1)
        self.assertEqual(len(r.context["activity"]), 3)


class ProgressTests(TestCase):
    def setUp(self):
        self.u = User.objects.create_user("alice", "a@example.com", "pass12345!x")
        self.client.login(username="alice", password="pass12345!x")

    def test_empty_progress(self):
        r = self.client.get(reverse("core:progress"))
        self.assertIsNone(r.context["overall"])
        self.assertContains(r, "Nothing to show yet")

    def test_progress_calculations(self):
        quiz = Quiz.objects.create(user=self.u, language="Python", topic="Loops", difficulty="beginner")
        QuizAttempt.objects.create(user=self.u, quiz=quiz, score=3, total=4, answers=[])
        QuizAttempt.objects.create(user=self.u, quiz=quiz, score=1, total=4, answers=[])
        LearningSession.objects.create(user=self.u, subject="Python", topic="loops", level="beginner", style="s", result={})
        r = self.client.get(reverse("core:progress"))
        self.assertEqual(r.context["completed"], 2)
        self.assertEqual(r.context["overall"], 50)
        self.assertEqual(r.context["best"], 75)
        row = r.context["topic_rows"][0]  # "Loops" quizzes + "loops" session merge case-insensitively
        self.assertEqual((row["quizzes"], row["sessions"], row["percent"]), (2, 1, 50))
