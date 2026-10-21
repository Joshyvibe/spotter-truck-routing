from django.urls import path

from . import views

urlpatterns = [
    path("health", views.HealthView.as_view(), name="health"),
    path("plans", views.PlanListCreateView.as_view(), name="plans"),
    path("plans/<str:plan_id>", views.PlanDetailView.as_view(), name="plan-detail"),
    path("plans/<str:plan_id>/heatmap", views.PlanHeatmapView.as_view(), name="plan-heatmap"),
    path("geocode", views.GeocodeView.as_view(), name="geocode"),
]
