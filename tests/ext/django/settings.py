SECRET_KEY = "secret"
DEBUG = True

INSTALLED_APPS = ("anydi.ext.django",)

ROOT_URLCONF = "tests.ext.django.urls"

MIDDLEWARE = ("anydi.ext.django.middleware.request_scoped_middleware",)

# AnyDI settings
ANYDI = {
    "STRICT_MODE": False,
    "REGISTER_SETTINGS": True,
    "REGISTER_COMPONENTS": True,
    "MODULES": ["tests.ext.django.container.configure"],
    "PATCH_NINJA": True,
    "INJECT_URLCONF": ROOT_URLCONF,
    "SCAN_PACKAGES": ["tests.ext.django.scan"],
}

# Custom settings
HELLO_MESSAGE = "Hello, World!"
