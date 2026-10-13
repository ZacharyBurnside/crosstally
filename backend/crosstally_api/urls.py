from django.urls import path
from game import views

urlpatterns = [
    path("api/health", views.health),
    path("api/daily/index", views.daily_index),
    path("api/daily/<str:day>", views.daily),
    path("api/auth/apple", views.auth_apple),
    path("api/me", views.me),                        # GET profile + stats, PATCH display name, DELETE account
    path("api/completions", views.completions),      # GET (sync) / POST (record)
    path("api/leaderboard/<str:day>/<int:level>", views.leaderboard),
]
