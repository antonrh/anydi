from django.urls import include, path

from .views import get_configured_dependency, get_setting, get_setting_async

urlpatterns = [
    path("get-setting/", get_setting),
    path("get-setting-async/", get_setting_async),
    path("get-configured-dependency/", get_configured_dependency),
    path("api/", include("tests.ext.django.api.urls")),
]
