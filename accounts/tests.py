from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

PROTECTED = [
    "core:dashboard", "core:progress", "tools:explain", "tools:debug", "tools:tutor", "tools:quiz", "tools:docs",
]


class AuthTests(TestCase):
    def test_registration_creates_user_and_logs_in(self):
        r = self.client.post(reverse("accounts:register"), {
            "username": "newdev", "email": "new@example.com", "password1": "Str0ng-pass-99", "password2": "Str0ng-pass-99",
        }, follow=True)
        self.assertTrue(User.objects.filter(username="newdev").exists())
        self.assertRedirects(r, reverse("core:dashboard"))
        self.assertContains(r, "newdev")

    def test_registration_rejects_weak_password_and_duplicate_email(self):
        User.objects.create_user("x", "dup@example.com", "pass12345!x")
        r = self.client.post(reverse("accounts:register"), {
            "username": "y", "email": "DUP@example.com", "password1": "12345678", "password2": "12345678",
        })
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(username="y").exists())
        self.assertContains(r, "already exists")

    def test_login_and_logout(self):
        User.objects.create_user("alice", "a@example.com", "pass12345!x")
        r = self.client.post(reverse("accounts:login"), {"username": "alice", "password": "pass12345!x"}, follow=True)
        self.assertRedirects(r, reverse("core:dashboard"))
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)  # POST only
        self.client.post(reverse("accounts:logout"))
        self.assertEqual(self.client.get(reverse("core:dashboard")).status_code, 302)

    def test_bad_login(self):
        r = self.client.post(reverse("accounts:login"), {"username": "nobody", "password": "nope"})
        self.assertContains(r, "Please enter a correct")

    def test_protected_pages_redirect_to_login(self):
        for name in PROTECTED:
            r = self.client.get(reverse(name))
            self.assertEqual(r.status_code, 302, name)
            self.assertIn(reverse("accounts:login"), r["Location"])

    def test_csrf_enforced(self):
        from django.test import Client
        c = Client(enforce_csrf_checks=True)
        r = c.post(reverse("accounts:login"), {"username": "a", "password": "b"})
        self.assertEqual(r.status_code, 403)

    def test_landing_is_public(self):
        r = self.client.get(reverse("core:landing"))
        self.assertContains(r, "Understand Code.")
