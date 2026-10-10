from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render

from .forms import LoginForm, RegistrationForm


class DevLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


def register(request):
    if request.user.is_authenticated:
        return redirect("core:dashboard")
    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, f"Welcome to DevGenius AI, {user.username}!")
        return redirect("core:dashboard")
    return render(request, "accounts/register.html", {"form": form})
