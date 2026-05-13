from django.urls import path
from .views import TaskListCreateView, TaskDetailView, AssignTaskView

urlpatterns = [
    path("",           TaskListCreateView.as_view(), name="task-list-create"),
    path("<uuid:pk>/", TaskDetailView.as_view(),     name="task-detail"),
    path("<uuid:pk>/assign/", AssignTaskView.as_view(), name="task-assign"),
]