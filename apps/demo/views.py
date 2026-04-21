from django.shortcuts import render


def index(request):
    return render(request, "demo/index.html")


def forum(request):
    return render(request, "demo/forum.html")


def members(request):
    return render(request, "demo/members.html")
