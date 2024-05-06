from __future__ import annotations

SECRET_KEY = "secret"
DEBUG = True

INSTALLED_APPS = ("anydi.ext.django",)

ROOT_URLCONF = "tests.ext.django.urls"

# AnyDI settings
ANYDI_STRICT_MODE = False
ANYDI_REGISTER_SETTINGS = True
ANYDI_REGISTER_COMPONENTS = True
ANYDI_MODULES: list[str] = ["tests.ext.django.container.configure"]
ANYDI_PATCH_NINJA = True
ANYDI_START_CONTAINER = True
ANYDI_AUTO_INJECT_URLCONF = ROOT_URLCONF

HELLO_MESSAGE = "Hello, World!"
