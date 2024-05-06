from django.urls import path
from ninja import NinjaAPI

from .router import router

api = NinjaAPI()
api.add_router("", router)

urlpatterns = [
    path("", api.urls),
]
