from django.shortcuts import render
from .brand import brand_for_request
from .services_views import services

def branded_home(request):
    brand = brand_for_request(request)
    if brand:
        return render(request, brand.template, {"brand": brand})
    return services(request)
