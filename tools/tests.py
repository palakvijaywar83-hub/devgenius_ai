import json
from unittest import mock

import requests
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from tools import ai_service
from tools.ai_service import (
    AIInvalidResponse, AINotConfigured, AIProviderError, AIRateLimited, AITimeout,
)
from tools.models import (
    BugReport, CodeExplanation, Documentation, LearningSession, Quiz, QuizAttempt, QuizQuestion,
)

AI_ON = dict(AI_PROVIDER="anthropic", AI_API_KEY="test-key", AI_MODEL="test-model", AI_RATE_LIMIT_PER_MINUTE=100)

EXPLAIN_OK = {"summary": "Adds numbers.", "steps": ["Define add", "Return a+b"], "key_elements": [{"name": "add", "description": "adds"}],
              "example": {"input": "1,2", "output": "3"}, "complexity": {"time": "O(1)", "space": "O(1)", "notes": ""},
              "mistakes": ["None"], "edge_cases": ["Overflow"]}
DEBUG_OK = {"likely_cause": "Division by zero", "location": "line 2", "suggested_fix": "Guard empty list",
            "corrected_code": "def mean(n):\n    return sum(n)/len(n) if n else 0", "fix_explanation": "Avoids /0",
            "test_cases": [{"description": "empty", "input": "[]", "expected": "0"}]}
TUTOR_OK = {"overview": "Loops repeat.", "explanation": "A loop repeats code.", "steps": [{"title": "for", "detail": "iterate", "code": "for i in x: pass"}],
            "real_world": ["Batch jobs"], "mistakes": ["Off by one"], "practice": [{"question": "Sum 1..10", "hint": "use range"}],
            "follow_ups": ["What is while?"]}
QUIZ_OK = {"questions": [
    {"question": f"Q{i}?", "options": [f"a{i}", f"b{i}", f"c{i}", f"d{i}"], "correct_index": i % 4, "explanation": f"because {i}"}
    for i in range(5)]}
DOCS_OK = {"title": "Calc", "markdown": "# Calc\n\nOverview"}


def provider_ok(payload):
    r = mock.Mock(status_code=200)
    r.json.return_value = {"content": [{"type": "text", "text": json.dumps(payload)}]}
    return r


def provider_status(code):
    return mock.Mock(status_code=code, json=mock.Mock(return_value={}))


@override_settings(**AI_ON)
class AIServiceTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_missing_credentials(self):
        with override_settings(AI_API_KEY=""), mock.patch("tools.ai_service.requests.post") as post:
            with self.assertRaises(AINotConfigured):
                ai_service.run("explain", {"language": "Python", "level": "beginner", "code": "x"})
            post.assert_not_called()

    def test_unknown_provider_not_configured(self):
        with override_settings(AI_PROVIDER="bogus"):
            self.assertFalse(ai_service.is_configured())

    def test_timeout(self):
        with mock.patch("tools.ai_service.requests.post", side_effect=requests.Timeout):
            with self.assertRaises(AITimeout):
                ai_service.run("docs", {"source_type": "code", "content": "x"})

    def test_connection_error(self):
        with mock.patch("tools.ai_service.requests.post", side_effect=requests.ConnectionError):
            with self.assertRaises(AIProviderError):
                ai_service.run("docs", {"source_type": "code", "content": "x"})

    def test_provider_rate_limit(self):
        with mock.patch("tools.ai_service.requests.post", return_value=provider_status(429)):
            with self.assertRaises(AIRateLimited):
                ai_service.run("docs", {"source_type": "code", "content": "x"})

    def test_bad_key_message(self):
        with mock.patch("tools.ai_service.requests.post", return_value=provider_status(401)):
            with self.assertRaises(AIProviderError) as cm:
                ai_service.run("docs", {"source_type": "code", "content": "x"})
            self.assertIn("API key", cm.exception.user_message)

    def test_server_error(self):
        with mock.patch("tools.ai_service.requests.post", return_value=provider_status(503)):
            with self.assertRaises(AIProviderError):
                ai_service.run("docs", {"source_type": "code", "content": "x"})

    def test_non_json_response(self):
        bad = mock.Mock(status_code=200, json=mock.Mock(return_value={"content": [{"type": "text", "text": "Sorry, no."}]}))
        with mock.patch("tools.ai_service.requests.post", return_value=bad):
            with self.assertRaises(AIInvalidResponse):
                ai_service.run("docs", {"source_type": "code", "content": "x"})

    def test_missing_required_fields(self):
        with mock.patch("tools.ai_service.requests.post", return_value=provider_ok({"summary": "only"})):
            with self.assertRaises(AIInvalidResponse):
                ai_service.run("explain", {"language": "Python", "level": "beginner", "code": "x"})

    def test_fenced_json_is_parsed(self):
        r = mock.Mock(status_code=200, json=mock.Mock(return_value={"content": [{"type": "text", "text": "```json\n" + json.dumps(DOCS_OK) + "\n```"}]}))
        with mock.patch("tools.ai_service.requests.post", return_value=r):
            self.assertEqual(ai_service.run("docs", {"source_type": "code", "content": "x"})["title"], "Calc")

    def test_openai_provider_shape(self):
        r = mock.Mock(status_code=200, json=mock.Mock(return_value={"choices": [{"message": {"content": json.dumps(DOCS_OK)}}]}))
        with override_settings(AI_PROVIDER="openai"), mock.patch("tools.ai_service.requests.post", return_value=r) as post:
            self.assertEqual(ai_service.run("docs", {"source_type": "code", "content": "x"})["markdown"], DOCS_OK["markdown"])
            self.assertIn("chat/completions", post.call_args.args[0])

    def test_api_key_sent_only_in_header(self):
        with mock.patch("tools.ai_service.requests.post", return_value=provider_ok(DOCS_OK)) as post:
            ai_service.run("docs", {"source_type": "code", "content": "x"})
            self.assertEqual(post.call_args.kwargs["headers"]["x-api-key"], "test-key")
            self.assertNotIn("test-key", json.dumps(post.call_args.kwargs["json"]))

    def test_local_rate_limit(self):
        with override_settings(AI_RATE_LIMIT_PER_MINUTE=2), mock.patch("tools.ai_service.requests.post", return_value=provider_ok(DOCS_OK)):
            for _ in range(2):
                ai_service.run("docs", {"source_type": "code", "content": "x"}, user_key=1)
            with self.assertRaises(AIRateLimited):
                ai_service.run("docs", {"source_type": "code", "content": "x"}, user_key=1)

    def test_quiz_drops_malformed_and_trims(self):
        payload = {"questions": QUIZ_OK["questions"] + [{"question": "bad", "options": ["a", "a", "b", "c"], "correct_index": 0}]}
        with mock.patch("tools.ai_service.requests.post", return_value=provider_ok(payload)):
            out = ai_service.run("quiz", {"language": "Python", "topic": "t", "difficulty": "beginner", "num_questions": 3})
        self.assertEqual(len(out["questions"]), 3)

    def test_quiz_all_invalid(self):
        with mock.patch("tools.ai_service.requests.post", return_value=provider_ok({"questions": [{"question": "x"}]})):
            with self.assertRaises(AIInvalidResponse):
                ai_service.run("quiz", {"language": "Python", "topic": "t", "difficulty": "beginner", "num_questions": 3})


class BaseCase(TestCase):
    def setUp(self):
        cache.clear()
        self.alice = User.objects.create_user("alice", "a@example.com", "pass12345!x")
        self.bob = User.objects.create_user("bob", "b@example.com", "pass12345!x")
        self.client.login(username="alice", password="pass12345!x")

    def make_quiz(self, user):
        quiz = Quiz.objects.create(user=user, language="Python", topic="loops", difficulty="beginner")
        for i in range(3):
            QuizQuestion.objects.create(quiz=quiz, order=i + 1, text=f"Q{i}", options=["a", "b", "c", "d"],
                                        correct_index=1, explanation="SECRET-EXPLANATION")
        return quiz


class ValidationTests(BaseCase):
    def test_explain_requires_code(self):
        r = self.client.post(reverse("tools:explain"), {"language": "Python", "level": "beginner", "code": "  "})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "This field is required")
        self.assertEqual(CodeExplanation.objects.count(), 0)

    @override_settings(MAX_CODE_CHARS=8000)
    def test_explain_rejects_oversized_code(self):
        r = self.client.post(reverse("tools:explain"), {"language": "Python", "level": "beginner", "code": "x" * 8001})
        self.assertContains(r, "at most 8000")

    def test_rejects_invalid_choice(self):
        r = self.client.post(reverse("tools:explain"), {"language": "Brainf", "level": "wizard", "code": "x"})
        self.assertContains(r, "valid choice")

    def test_null_bytes_rejected(self):
        r = self.client.post(reverse("tools:explain"), {"language": "Python", "level": "beginner", "code": "a\x00b"})
        self.assertContains(r, "characters are not allowed")

    def test_bug_needs_error_or_expected(self):
        r = self.client.post(reverse("tools:debug"), {"language": "Python", "code": "x = 1"})
        self.assertContains(r, "error message, the expected behavior")

    def test_quiz_question_count_bounds(self):
        for n in (2, 11):
            r = self.client.post(reverse("tools:quiz"), {"language": "Python", "topic": "x", "difficulty": "beginner", "num_questions": n})
            self.assertEqual(Quiz.objects.count(), 0)
            self.assertEqual(r.status_code, 200)


@override_settings(**AI_ON)
class WorkflowTests(BaseCase):
    def test_explain_flow_saves_and_renders(self):
        with mock.patch("tools.ai_service.run", return_value=EXPLAIN_OK) as run:
            r = self.client.post(reverse("tools:explain"), {"language": "Python", "level": "beginner", "code": "def add(a,b): return a+b"}, follow=True)
        run.assert_called_once()
        obj = CodeExplanation.objects.get()
        self.assertEqual(obj.user, self.alice)
        self.assertContains(r, "Adds numbers.")
        self.assertContains(r, "O(1)")

    def test_ai_failure_shows_message_and_saves_nothing(self):
        with mock.patch("tools.ai_service.run", side_effect=AITimeout()):
            r = self.client.post(reverse("tools:explain"), {"language": "Python", "level": "beginner", "code": "x = 1"})
        self.assertContains(r, "took too long")
        self.assertContains(r, "x = 1")  # user's input preserved
        self.assertEqual(CodeExplanation.objects.count(), 0)

    def test_save_toggle(self):
        obj = CodeExplanation.objects.create(user=self.alice, language="Python", level="beginner", code="x", result=EXPLAIN_OK)
        self.client.post(reverse("tools:explain_save", args=[obj.pk]))
        obj.refresh_from_db()
        self.assertTrue(obj.is_saved)

    def test_debug_flow(self):
        with mock.patch("tools.ai_service.run", return_value=DEBUG_OK):
            r = self.client.post(reverse("tools:debug"), {"language": "Python", "code": "print(1/0)", "error_message": "ZeroDivisionError", "expected_behavior": ""}, follow=True)
        self.assertEqual(BugReport.objects.count(), 1)
        self.assertContains(r, "not executed or verified")
        self.assertContains(r, "Division by zero")

    def test_tutor_flow_and_followup(self):
        with mock.patch("tools.ai_service.run", return_value=TUTOR_OK):
            self.client.post(reverse("tools:tutor"), {"subject": "Python", "topic": "loops", "level": "beginner", "style": "Hands-on code examples"})
        s = LearningSession.objects.get()
        with mock.patch("tools.ai_service.run", return_value={"answer": "A while loop repeats while true."}):
            r = self.client.post(reverse("tools:tutor_followup", args=[s.pk]), json.dumps({"question": "What is while?"}), content_type="application/json")
        self.assertEqual(r.status_code, 200)
        s.refresh_from_db()
        self.assertEqual(s.followups[0]["question"], "What is while?")

    def test_followup_validation_and_errors(self):
        s = LearningSession.objects.create(user=self.alice, subject="Python", topic="t", level="beginner", style="x", result=TUTOR_OK)
        url = reverse("tools:tutor_followup", args=[s.pk])
        self.assertEqual(self.client.post(url, json.dumps({"question": ""}), content_type="application/json").status_code, 400)
        self.assertEqual(self.client.post(url, "not json", content_type="application/json").status_code, 400)
        with mock.patch("tools.ai_service.run", side_effect=AIRateLimited()):
            self.assertEqual(self.client.post(url, json.dumps({"question": "hi"}), content_type="application/json").status_code, 429)

    def test_quiz_generation_flow(self):
        with mock.patch("tools.ai_service.run", return_value=QUIZ_OK):
            r = self.client.post(reverse("tools:quiz"), {"language": "Python", "topic": "loops", "difficulty": "beginner", "num_questions": 5}, follow=True)
        quiz = Quiz.objects.get()
        self.assertEqual(quiz.questions.count(), 5)
        self.assertEqual(r.redirect_chain[-1][0], reverse("tools:quiz_take", args=[quiz.pk]))

    def test_docs_flow(self):
        with mock.patch("tools.ai_service.run", return_value=DOCS_OK):
            r = self.client.post(reverse("tools:docs"), {"source_type": "code", "title": "", "content": "print('hi')"}, follow=True)
        self.assertEqual(Documentation.objects.get().title, "Calc")
        self.assertContains(r, "Copy to clipboard")

    def test_not_configured_shows_setup_instructions(self):
        with override_settings(AI_API_KEY=""):
            r = self.client.get(reverse("tools:explain"))
            self.assertContains(r, "AI isn")
            self.assertContains(r, ".env.example")
            r = self.client.post(reverse("tools:explain"), {"language": "Python", "level": "beginner", "code": "x"})
            self.assertContains(r, "not configured")
            self.assertEqual(CodeExplanation.objects.count(), 0)

    def test_html_in_ai_output_is_escaped(self):
        evil = dict(EXPLAIN_OK, summary="<script>alert(1)</script>")
        obj = CodeExplanation.objects.create(user=self.alice, language="Python", level="beginner", code="<b>x</b>", result=evil)
        r = self.client.get(obj.get_absolute_url())
        self.assertNotContains(r, "<script>alert(1)</script>")
        self.assertNotContains(r, "<b>x</b>")


class QuizScoringTests(BaseCase):
    def test_server_side_scoring(self):
        quiz = self.make_quiz(self.alice)
        qs = list(quiz.questions.all())
        data = {f"q_{qs[0].pk}": "1", f"q_{qs[1].pk}": "0"}  # correct, wrong, unanswered
        r = self.client.post(reverse("tools:quiz_submit", args=[quiz.pk]), data, follow=True)
        attempt = QuizAttempt.objects.get()
        self.assertEqual((attempt.score, attempt.total), (1, 3))
        self.assertEqual(attempt.answers, [1, 0, None])
        self.assertContains(r, "1/3")
        self.assertContains(r, "SECRET-EXPLANATION")

    def test_tampered_values_are_safe(self):
        quiz = self.make_quiz(self.alice)
        qs = list(quiz.questions.all())
        data = {f"q_{qs[0].pk}": "99", f"q_{qs[1].pk}": "-1", f"q_{qs[2].pk}": "abc"}
        self.client.post(reverse("tools:quiz_submit", args=[quiz.pk]), data)
        self.assertEqual(QuizAttempt.objects.get().score, 0)

    def test_take_page_does_not_leak_answers(self):
        quiz = self.make_quiz(self.alice)
        r = self.client.get(reverse("tools:quiz_take", args=[quiz.pk]))
        self.assertNotContains(r, "SECRET-EXPLANATION")
        self.assertNotContains(r, "correct")

    def test_perfect_score(self):
        quiz = self.make_quiz(self.alice)
        data = {f"q_{q.pk}": "1" for q in quiz.questions.all()}
        self.client.post(reverse("tools:quiz_submit", args=[quiz.pk]), data)
        self.assertEqual(QuizAttempt.objects.get().percent, 100)


class DataIsolationTests(BaseCase):
    def setUp(self):
        super().setUp()
        self.expl = CodeExplanation.objects.create(user=self.bob, language="Python", level="beginner", code="secret", result=EXPLAIN_OK)
        self.bug = BugReport.objects.create(user=self.bob, language="Python", code="secret", error_message="e", result=DEBUG_OK)
        self.sess = LearningSession.objects.create(user=self.bob, subject="Python", topic="t", level="beginner", style="s", result=TUTOR_OK)
        self.doc = Documentation.objects.create(user=self.bob, title="d", source_type="code", input_text="i", content="c")
        self.quiz = self.make_quiz(self.bob)
        self.attempt = QuizAttempt.objects.create(user=self.bob, quiz=self.quiz, score=1, total=3, answers=[1, 0, None])

    def test_other_users_records_are_404(self):
        urls = [
            reverse("tools:explain_detail", args=[self.expl.pk]), reverse("tools:debug_detail", args=[self.bug.pk]),
            reverse("tools:tutor_detail", args=[self.sess.pk]), reverse("tools:docs_detail", args=[self.doc.pk]),
            reverse("tools:quiz_take", args=[self.quiz.pk]), reverse("tools:quiz_result", args=[self.attempt.pk]),
        ]
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 404, url)

    def test_cannot_modify_or_delete_others_records(self):
        posts = [
            reverse("tools:explain_save", args=[self.expl.pk]), reverse("tools:explain_delete", args=[self.expl.pk]),
            reverse("tools:debug_delete", args=[self.bug.pk]), reverse("tools:tutor_delete", args=[self.sess.pk]),
            reverse("tools:docs_delete", args=[self.doc.pk]), reverse("tools:quiz_delete", args=[self.quiz.pk]),
            reverse("tools:quiz_submit", args=[self.quiz.pk]), reverse("tools:tutor_followup", args=[self.sess.pk]),
        ]
        for url in posts:
            self.assertEqual(self.client.post(url, "{}", content_type="application/json").status_code, 404, url)
        self.assertEqual(CodeExplanation.objects.count(), 1)
        self.assertEqual(Quiz.objects.count(), 1)
        self.assertEqual(QuizAttempt.objects.count(), 1)

    def test_lists_only_show_own_records(self):
        mine = CodeExplanation.objects.create(user=self.alice, language="Go", level="beginner", code="mine_code", result=EXPLAIN_OK)
        r = self.client.get(reverse("tools:explain"))
        self.assertContains(r, "mine_code")
        self.assertNotContains(r, "secret")
        self.assertEqual(list(r.context["history"]), [mine])

    def test_owner_can_delete(self):
        self.client.logout()
        self.client.login(username="bob", password="pass12345!x")
        self.client.post(reverse("tools:explain_delete", args=[self.expl.pk]))
        self.assertEqual(CodeExplanation.objects.count(), 0)

    def test_delete_requires_post(self):
        self.client.logout()
        self.client.login(username="bob", password="pass12345!x")
        self.assertEqual(self.client.get(reverse("tools:explain_delete", args=[self.expl.pk])).status_code, 405)
