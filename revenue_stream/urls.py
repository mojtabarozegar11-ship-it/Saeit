from django.urls import path
from . import views
urlpatterns=[path('',views.landing),path('assets/<str:name>/',views.asset),path('checkout/',views.checkout),path('access/',views.access),path('logout/',views.logout),path('callback/',views.callback),path('terms/',views.terms),path('owner/',views.owner),path('order/<str:oid>/',views.order_page),path('order/<str:oid>/pay/',views.pay),path('order/<str:oid>/recheck/',views.recheck),path('order/<str:oid>/download/',views.download),path('order/<str:oid>/ticket/',views.ticket)]
