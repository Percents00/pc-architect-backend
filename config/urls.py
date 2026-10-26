from django.urls import path
from core import views, auth_views, build_views

urlpatterns = [
    path("api/auth/csrf/", auth_views.csrf),
    path("api/auth/register/", auth_views.register),
    path("api/auth/login/", auth_views.login),
    path("api/auth/refresh/", auth_views.refresh),
    path("api/auth/logout/", auth_views.logout),
    path("api/auth/me/", auth_views.me),
    path("api/builds/", build_views.builds),
    path("api/builds/<str:build_id>/", build_views.build_detail),
    path("", views.index),
    path("index.html", views.index),
    path("api/categories/", views.categories),
    path("api/components/", views.components),
    path("api/components/<str:component_id>/", views.component_detail),
]
urlpatterns += [path(name, views.asset, {"name": name}) for name in views.ASSETS]
