from django import forms
from django.conf import settings

from core.forms import BootstrapFormMixin

LANGUAGES = [
    "Python", "JavaScript", "TypeScript", "Java", "C", "C++", "C#", "Go", "Rust",
    "PHP", "Ruby", "Kotlin", "Swift", "SQL", "HTML/CSS", "Other",
]
LANGUAGE_CHOICES = [(x, x) for x in LANGUAGES]
SUBJECT_CHOICES = LANGUAGE_CHOICES[:-1] + [
    ("Data Structures & Algorithms", "Data Structures & Algorithms"),
    ("Machine Learning", "Machine Learning"),
    ("Web Development", "Web Development"),
    ("Databases", "Databases"),
    ("Git & DevOps", "Git & DevOps"),
]
LEVEL_CHOICES = [("beginner", "Beginner"), ("intermediate", "Intermediate"), ("advanced", "Advanced")]
STYLE_CHOICES = [
    ("Real-world analogies", "Real-world analogies"),
    ("Hands-on code examples", "Hands-on code examples"),
    ("Step-by-step theory", "Step-by-step theory"),
    ("Question-and-answer", "Question-and-answer"),
]


def _text(label, max_len=None, rows=3, required=True, placeholder=""):
    return forms.CharField(
        label=label,
        required=required,
        max_length=max_len or settings.MAX_TEXT_CHARS,
        widget=forms.Textarea(attrs={"rows": rows, "placeholder": placeholder, "spellcheck": "false"}),
    )


class CodeCleanMixin:
    def _clean_text(self, name):
        value = self.cleaned_data.get(name, "")
        if "\x00" in value:
            raise forms.ValidationError("Input contains invalid characters.")
        return value.strip()


class ExplainForm(BootstrapFormMixin, CodeCleanMixin, forms.Form):
    language = forms.ChoiceField(choices=LANGUAGE_CHOICES)
    level = forms.ChoiceField(label="Explanation level", choices=LEVEL_CHOICES, initial="beginner")
    code = _text("Source code", max_len=settings.MAX_CODE_CHARS, rows=14, placeholder="Paste your code here…")

    def clean_code(self):
        return self._clean_text("code")


class BugForm(BootstrapFormMixin, CodeCleanMixin, forms.Form):
    language = forms.ChoiceField(choices=LANGUAGE_CHOICES)
    code = _text("Source code", max_len=settings.MAX_CODE_CHARS, rows=12, placeholder="Paste the code that fails…")
    error_message = _text("Error message", rows=3, required=False, placeholder="Paste the traceback or error…")
    expected_behavior = _text("Expected behavior", rows=3, required=False, placeholder="What should the code do?")

    def clean_code(self):
        return self._clean_text("code")

    def clean_error_message(self):
        return self._clean_text("error_message")

    def clean_expected_behavior(self):
        return self._clean_text("expected_behavior")

    def clean(self):
        data = super().clean()
        if not data.get("error_message") and not data.get("expected_behavior") and not self.errors:
            raise forms.ValidationError("Provide an error message, the expected behavior, or both.")
        return data


class TutorForm(BootstrapFormMixin, CodeCleanMixin, forms.Form):
    subject = forms.ChoiceField(label="Language or subject", choices=SUBJECT_CHOICES)
    topic = forms.CharField(max_length=120, widget=forms.TextInput(attrs={"placeholder": "e.g. recursion, list comprehensions"}))
    level = forms.ChoiceField(label="Your skill level", choices=LEVEL_CHOICES, initial="beginner")
    style = forms.ChoiceField(label="Preferred learning style", choices=STYLE_CHOICES)

    def clean_topic(self):
        return self._clean_text("topic")


class QuizForm(BootstrapFormMixin, CodeCleanMixin, forms.Form):
    language = forms.ChoiceField(choices=SUBJECT_CHOICES)
    topic = forms.CharField(max_length=120, widget=forms.TextInput(attrs={"placeholder": "e.g. loops, pointers, joins"}))
    difficulty = forms.ChoiceField(choices=LEVEL_CHOICES, initial="beginner")
    num_questions = forms.IntegerField(label="Number of questions", min_value=3, max_value=10, initial=5)

    def clean_topic(self):
        return self._clean_text("topic")


class DocForm(BootstrapFormMixin, CodeCleanMixin, forms.Form):
    SOURCE_CHOICES = [("code", "Source code"), ("description", "Project description")]
    source_type = forms.ChoiceField(label="Input type", choices=SOURCE_CHOICES)
    title = forms.CharField(label="Project title (optional)", max_length=160, required=False)
    content = _text("Code or project description", max_len=settings.MAX_CODE_CHARS, rows=14,
                    placeholder="Paste code or describe your project…")

    def clean_title(self):
        return self._clean_text("title")

    def clean_content(self):
        return self._clean_text("content")
