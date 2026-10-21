from django.urls import include, path

urlpatterns = [path("api/v1/", include("routing.api.urls"))]

handler404 = "routing.api.views.not_found"
