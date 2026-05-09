from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.views import REDIRECT_FIELD_NAME
from django.shortcuts import redirect, render, resolve_url
from django.views import View

from .forms import RegisterForm


class RegisterView(View):
    def get(self, request):
        return render(request, "accounts/register.html", {"form": RegisterForm()})

    def post(self, request):
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            next_url = request.POST.get(REDIRECT_FIELD_NAME) or request.GET.get(REDIRECT_FIELD_NAME)
            return redirect(next_url or resolve_url(settings.LOGIN_REDIRECT_URL))
        return render(request, "accounts/register.html", {"form": form})
