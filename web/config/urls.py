from django.templatetags.static import static
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path(
        "favicon.ico",
        RedirectView.as_view(url=static("document_lock_logo.ico"), permanent=True),
    ),
    path("", include("locker.urls")),
]
