from dataclasses import dataclass

@dataclass(frozen=True)
class Brand:
    code: str
    name: str
    domain: str
    template: str
    language: str = "en"

BRANDS = {
    "mojplaywin.com": Brand("mojplaywin", "MojPlayWin", "mojplaywin.com", "brands/mojplaywin/home.html"),
    "www.mojplaywin.com": Brand("mojplaywin", "MojPlayWin", "mojplaywin.com", "brands/mojplaywin/home.html"),
}

def brand_for_request(request):
    host = request.get_host().split(":", 1)[0].lower()
    return BRANDS.get(host)
