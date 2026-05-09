from django.contrib.auth import login
from django.shortcuts import redirect, render
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
            return redirect("/")
        return render(request, "accounts/register.html", {"form": form})
