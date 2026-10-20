from django.urls import path

from . import views

app_name = "locker"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("register/", views.register_view, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("documents/upload/", views.upload, name="upload"),
    path(
        "documents/<uuid:document_id>/download/",
        views.download,
        name="download",
    ),
    path(
        "documents/<uuid:document_id>/rename/",
        views.rename,
        name="rename",
    ),
    path(
        "documents/<uuid:document_id>/delete/",
        views.delete_confirm,
        name="delete",
    ),
    path("ai/", views.ai, name="ai"),
]
