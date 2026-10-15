"""PICM movie bridge route bundle; mount only on the verified MojPlayWin host.

Do not append these routes to the Zomorod Melal website or factory runtime.
No production route is changed merely by adding this module to GitHub.
"""
from django.urls import path

from .picm_video_bridge import (
    video_worker_next, video_worker_metadata, video_worker_reference,
    video_worker_progress, video_worker_chunk, video_worker_finish,
    video_owner_status, video_owner_download,
)

urlpatterns = [
    path("picm/video/worker/next/", video_worker_next, name="picm_video_worker_next"),
    path("picm/video/worker/metadata/<str:ident>/", video_worker_metadata,
         name="picm_video_worker_metadata"),
    path("picm/video/worker/reference/<str:ident>/", video_worker_reference,
         name="picm_video_worker_reference"),
    path("picm/video/worker/progress/<str:ident>/", video_worker_progress,
         name="picm_video_worker_progress"),
    path("picm/video/worker/chunk/<str:ident>/", video_worker_chunk,
         name="picm_video_worker_chunk"),
    path("picm/video/worker/finish/<str:ident>/", video_worker_finish,
         name="picm_video_worker_finish"),
    path("picm/video/status/<str:ident>/", video_owner_status,
         name="picm_video_owner_status"),
    path("picm/video/download/<str:ident>/", video_owner_download,
         name="picm_video_owner_download"),
]
