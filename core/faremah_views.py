from django.http import HttpResponseRedirect


def faremah_home(request):
    return HttpResponseRedirect("/faremah/index.html")
