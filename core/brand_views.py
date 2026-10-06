from django.http import Http404
from django.shortcuts import render
from .brand import brand_for_request
from .services_views import services

PAGES = {
 "games": {"title":"Games","kicker":"PLAY / DISCOVER","headline":"Games built around meaningful choices.","body":"Explore original MojPlayWin projects, playable experiments and worlds in development.","cards":[("First Realm","Strategy · World Building","In development. An original strategy world focused on expansion, decisions and a living economy."),("Next World","Original IP","Reserved for the next independently designed MojPlayWin title."),("Experiments","Playable R&D","Small prototypes used to validate mechanics before they become full games.")]},
 "worlds":{"title":"Worlds","kicker":"LORE / SYSTEMS","headline":"Worlds designed to evolve.","body":"Every MojPlayWin universe starts with its own rules, identity and reason to exist.","cards":[("Systems First","Design","World rules react to player decisions."),("Living Economies","Simulation","Progression and resources are designed as coherent systems."),("Original Identity","IP","Distinct mechanics and visual direction for every world.")]},
 "news":{"title":"News","kicker":"STUDIO / SIGNAL","headline":"Development, without invented milestones.","body":"Verified development notes and release updates will appear here as projects advance.","cards":[("Development","Updates","Production milestones and build notes."),("Design Notes","Inside the systems","How mechanics move from hypothesis to tested gameplay."),("Release Notes","When available","Changes tied to real released builds.")]},
 "community":{"title":"Community","kicker":"PLAYERS / FEEDBACK","headline":"Players help decide what grows.","body":"Testing and feedback channels will open when playable builds are ready.","cards":[("Playtests","Coming when ready","Structured testing for eligible builds."),("Feedback","Player signal","Actionable feedback feeds product decisions."),("Community Safety","Baseline","Respectful participation and clear moderation rules.")]},
 "support":{"title":"Support","kicker":"HELP / ACCESS","headline":"Support that starts with the actual problem.","body":"Game and account support will expand alongside released products.","cards":[("General Help","support@mojplaywin.com","Contact the support mailbox for general questions."),("Game Issues","Release-linked","Game-specific help opens with each public build."),("Account Help","Planned","Account recovery and profile support will be connected when accounts launch.")]},
 "about":{"title":"About","kicker":"MOJPLAYWIN / STUDIO","headline":"Original games. Measured evolution.","body":"MojPlayWin is being built as a global gaming brand for original digital games and interactive worlds.","cards":[("Original by Default","Principle","No reskins or invented release claims."),("Player First","Principle","Gameplay and player signal guide iteration."),("Global by Design","Principle","Architecture is prepared for multiple markets and languages.")]},
 "contact":{"title":"Contact","kicker":"CONTACT / MOJPLAYWIN","headline":"Talk to MojPlayWin.","body":"Use the appropriate channel so your message reaches the right workflow.","cards":[("Support","support@mojplaywin.com","Player and game support."),("Business","Coming soon","Business contact will be published only after the mailbox is operational."),("Press","Coming soon","Press resources will be added with verified public releases.")]},
 "privacy":{"title":"Privacy","kicker":"LEGAL / PRIVACY","headline":"Privacy information.","body":"This page is a publication-ready placeholder, not a substitute for jurisdiction-specific legal review.","cards":[("Data minimization","Policy direction","Collect only data required to operate the service."),("Security","Policy direction","Protect access and retain auditable operational controls."),("Rights","Before launch","Final rights, retention and contact terms must match actual deployed services.")]},
 "terms":{"title":"Terms","kicker":"LEGAL / TERMS","headline":"Terms of service.","body":"Final binding terms will be published before accounts, payments or public game services are activated.","cards":[("Fair use","Baseline","Services must not be abused or used unlawfully."),("Digital services","Before launch","Product-specific rules will match the actual released service."),("Changes","Transparent","Material terms should be versioned and communicated.")]},
 "cookies":{"title":"Cookies","kicker":"LEGAL / COOKIES","headline":"Cookie information.","body":"Cookie disclosures will reflect the trackers actually deployed; unnecessary tracking is not assumed.","cards":[("Essential","Operational","Required security/session technologies may be used."),("Analytics","Consent-aware","Analytics should only be enabled under the applicable consent policy."),("Advertising","Not assumed","No advertising tracker is claimed until one is actually configured.")]},
}
def branded_home(request):
    brand=brand_for_request(request)
    if brand:return render(request,brand.template,{"brand":brand})
    return services(request)
def branded_page(request, page):
    brand=brand_for_request(request)
    if not brand or brand.code!="mojplaywin": raise Http404
    data=PAGES.get(page)
    if not data: raise Http404
    return render(request,"brands/mojplaywin/page.html",{"brand":brand,"page":data,"page_key":page})
def branded_game(request, slug):
    brand=brand_for_request(request)
    if not brand or brand.code!="mojplaywin" or slug!="first-realm": raise Http404
    return render(request,"brands/mojplaywin/game.html",{"brand":brand})
