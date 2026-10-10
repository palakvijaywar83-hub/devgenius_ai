from django.conf import settings
from django.db import models
from django.urls import reverse


def _short(text, n=60):
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1] + "…"


class OwnedRecord(models.Model):
    """Base for every per-user record."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="%(class)s_set")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]


class CodeExplanation(OwnedRecord):
    language = models.CharField(max_length=40)
    level = models.CharField(max_length=20)
    code = models.TextField()
    result = models.JSONField()
    is_saved = models.BooleanField(default=False)

    kind = "Explanation"

    class Meta(OwnedRecord.Meta):
        pass

    @property
    def label(self):
        return f"{self.language}: {_short(self.code, 50)}"

    def get_absolute_url(self):
        return reverse("tools:explain_detail", args=[self.pk])


class BugReport(OwnedRecord):
    language = models.CharField(max_length=40)
    code = models.TextField()
    error_message = models.TextField(blank=True)
    expected_behavior = models.TextField(blank=True)
    result = models.JSONField()

    kind = "Debugging"

    class Meta(OwnedRecord.Meta):
        pass

    @property
    def label(self):
        return f"{self.language}: {_short(self.error_message or self.expected_behavior, 50)}"

    def get_absolute_url(self):
        return reverse("tools:debug_detail", args=[self.pk])


class LearningSession(OwnedRecord):
    subject = models.CharField(max_length=60)
    topic = models.CharField(max_length=120)
    level = models.CharField(max_length=20)
    style = models.CharField(max_length=40)
    result = models.JSONField()
    followups = models.JSONField(default=list, blank=True)  # [{"question":..., "answer":...}]

    kind = "Learning"

    class Meta(OwnedRecord.Meta):
        pass

    @property
    def label(self):
        return f"{self.subject}: {self.topic}"

    def get_absolute_url(self):
        return reverse("tools:tutor_detail", args=[self.pk])


class Quiz(OwnedRecord):
    language = models.CharField(max_length=40)
    topic = models.CharField(max_length=120)
    difficulty = models.CharField(max_length=20)

    class Meta(OwnedRecord.Meta):
        verbose_name_plural = "quizzes"

    def __str__(self):
        return f"{self.language} – {self.topic}"

    def get_absolute_url(self):
        return reverse("tools:quiz_take", args=[self.pk])


class QuizQuestion(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="questions")
    order = models.PositiveSmallIntegerField()
    text = models.TextField()
    options = models.JSONField()  # list of 4 strings
    correct_index = models.PositiveSmallIntegerField()
    explanation = models.TextField(blank=True)

    class Meta:
        ordering = ["order"]


class QuizAttempt(OwnedRecord):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="attempts")
    score = models.PositiveSmallIntegerField()
    total = models.PositiveSmallIntegerField()
    answers = models.JSONField(default=list)  # chosen option index per question, or null

    kind = "Quiz"

    class Meta(OwnedRecord.Meta):
        pass

    @property
    def percent(self):
        return round(100 * self.score / self.total) if self.total else 0

    @property
    def label(self):
        return f"{self.quiz.topic}: {self.score}/{self.total}"

    def get_absolute_url(self):
        return reverse("tools:quiz_result", args=[self.pk])


class Documentation(OwnedRecord):
    title = models.CharField(max_length=160)
    source_type = models.CharField(max_length=20)
    input_text = models.TextField()
    content = models.TextField()

    kind = "Documentation"

    class Meta(OwnedRecord.Meta):
        verbose_name_plural = "documentation"

    @property
    def label(self):
        return self.title

    def get_absolute_url(self):
        return reverse("tools:docs_detail", args=[self.pk])
