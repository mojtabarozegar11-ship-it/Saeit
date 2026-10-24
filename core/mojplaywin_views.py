from django.http import Http404
from django.shortcuts import render

FEATURES = [
 {"title":"Research & Innovation","text":"Evidence-led research, practical analysis, and ideas shaped into useful digital work.","image":"site/heroes/research.webp","url":"/research/"},
 {"title":"Games & Creative Studio","text":"Original game concepts, playful experiences, and digital entertainment projects.","image":"site/heroes/game-studio.webp","url":"/studio/"},
 {"title":"Learning & Education","text":"Clear learning paths connecting modern technology with practical skills.","image":"site/heroes/education-detail.webp","url":"/knowledge/"},
 {"title":"Digital Store","text":"Books, learning resources, games, and practical digital tools in one catalog.","image":"site/heroes/store.webp","url":"/store/"},
 {"title":"Artificial Intelligence","text":"Thoughtful AI tools and explainers for research, creativity, and everyday work.","image":"site/heroes/ai.webp","url":"/agents/"},
 {"title":"Knowledge Library","text":"Guides and reference material organized to make complex topics easier to explore.","image":"site/heroes/knowledge.webp","url":"/knowledge/"},
]
VENTURES = [
 {"slug":"agriculture","title":"Agriculture & Agri-Industry","text":"Farm planning, crop production, processing, and practical digital tools for agricultural value chains.","url":"/ventures/agriculture/","image":"site/heroes/agriculture.webp","lead":"Explore agriculture from farm economics and crop planning through processing, market access, and technology-enabled value chains.","cards":[("Farm planning & economics","Build clear production plans, cost models, and decision frameworks for agricultural enterprises."),("Crops, water & resilient production","Explore research-led approaches to crop systems, water use, and climate-aware operations."),("Processing & market access","Map practical paths from harvest to storage, packaging, processing, and market readiness.")],"note":"This page presents areas for research and project development. It does not claim a specific farm, facility, or current product inventory."},
 {"slug":"cafe-restaurant","title":"Cafes & Restaurants","text":"Hospitality concepts, menu experiences, service design, and digital tools for food businesses.","url":"/ventures/cafe-restaurant/","image":"site/heroes/marketplace.webp","lead":"A focused space for cafe and restaurant concepts, guest experience, menu planning, and technology-supported operations.","cards":[("Concept & guest experience","Shape a clear identity, customer journey, and welcoming service concept."),("Menu & operations","Organize menus, service workflows, inventory ideas, and practical operating information."),("Digital hospitality","Explore online menus, booking, loyalty, ordering, and customer communication tools.")],"note":"No specific restaurant location, opening hours, or menu is listed unless confirmed for that project."},
 {"slug":"fuel-station","title":"Fuel Stations & Mobility","text":"Service-station planning, customer services, and emerging mobility concepts.","url":"/ventures/fuel-station/","image":"site/heroes/industry.webp","lead":"Explore fuel-station and roadside-service concepts through operations, customer experience, and the changing mobility landscape.","cards":[("Service-station concepts","Consider site planning, service mix, customer flow, and operational requirements."),("Retail & customer services","Map convenience retail, refreshments, and useful roadside services."),("Mobility technology","Follow digital payments, connected services, and new energy and mobility ideas.")],"note":"This is an industry and planning overview; it does not represent a licensed operating station or fuel sales offer."},
 {"slug":"jewelry-gold","title":"Jewelry & Gold","text":"Jewelry design, craft, product storytelling, and digital retail experiences.","url":"/ventures/jewelry-gold/","image":"site/heroes/marketplace.webp","lead":"Discover the jewelry and gold sector through craftsmanship, design, product information, and responsible digital commerce.","cards":[("Design & craftsmanship","Showcase materials, techniques, design language, and the care behind each piece."),("Product stories","Present clear descriptions, sizing, care guidance, and provenance where documented."),("Digital jewelry retail","Explore elegant catalogs, product photography direction, and customer support journeys.")],"note":"No gold pricing, investment return, or product availability is asserted on this overview page."},
 {"slug":"carpets","title":"Carpets & Textiles","text":"Handwoven carpet heritage, textile craft, design, and online presentation.","url":"/ventures/carpets/","image":"site/heroes/knowledge.webp","lead":"A home for carpet and textile stories: weaving traditions, design details, craft knowledge, and thoughtful online presentation.","cards":[("Craft & heritage","Document weaving methods, regional influences, materials, and makers with care."),("Design & collection","Organize patterns, dimensions, colors, and product stories for easier discovery."),("Digital catalogues","Build clear online browsing experiences and useful care and shipping information.")],"note":"Specific makers, origins, and stock should be shown only when verified for each item."},
 {"slug":"currency-crypto","title":"Currency & Digital Assets","text":"Educational resources and research on currency markets, blockchain, and digital assets.","url":"/ventures/currency-crypto/","image":"site/heroes/economy.webp","lead":"Explore currency and digital assets through accessible education, market structure, technology, and careful research.","cards":[("Currency-market literacy","Explain terminology, market mechanisms, and the factors that influence currency exchange."),("Blockchain & digital assets","Introduce distributed ledgers, token systems, and the technology behind digital assets."),("Research & risk awareness","Compare sources, identify uncertainty, and understand that markets can change quickly.")],"note":"Educational information only. MojPlayWin does not offer exchange, brokerage, custody, trading, or investment advice through this page."},
 {"slug":"ecommerce","title":"E-commerce & Virtual Commerce","text":"Online storefronts, digital catalogues, virtual goods, and customer journeys.","url":"/ventures/ecommerce/","image":"site/heroes/store.webp","lead":"Explore digital commerce across physical goods, downloadable products, subscriptions, and virtual experiences.","cards":[("Storefront & catalogue","Plan product discovery, clear descriptions, accessible layouts, and searchable collections."),("Digital delivery","Design reliable delivery flows for downloads, learning content, and virtual products."),("Customer experience","Connect checkout, support, order information, and thoughtful post-purchase journeys.")],"note":"A purchase flow is displayed only when its product, price, fulfillment, and payment route are active and verified."},
 {"slug":"hospitality","title":"Hospitality & Services","text":"Guest services, experience design, and digital operations across hospitality.","url":"/ventures/hospitality/","image":"site/heroes/platform-home.webp","lead":"Connect hospitality experience with practical service design, useful information, and digital customer tools.","cards":[("Service design","Make services easier to understand, access, and deliver consistently."),("Guest communication","Organize useful information, inquiries, reservations, and follow-up."),("Digital operations","Explore tools that support teams, customer journeys, and service quality.")],"note":"Project details are published only when confirmed by the responsible business."},
]
PRODUCTS = [
 {"title":"The Science and Practice of Chess Improvement","text":"A structured chess study resource with lessons, analysis, and exercises.","image":"site/heroes/education-detail.webp","category":"BOOK · LEARNING","url":"/store/"},
 {"title":"Taniya and the Little Baker Worms","text":"A rhythmic illustrated story created for young readers and families.","image":"site/heroes/game-studio.webp","category":"CHILDREN'S BOOK","url":"/taniya/"},
 {"title":"Farm Enterprise Economics Toolkit","text":"A practical digital toolkit for farm planning and enterprise economics.","image":"site/heroes/agriculture.webp","category":"AGRICULTURE · TOOLKIT","url":"/ventures/agriculture/"},
 {"title":"Applied AI Learning Path","text":"A step-by-step route from foundational AI ideas to practical applications.","image":"site/heroes/ai.webp","category":"COURSE · TECHNOLOGY","url":"/knowledge/"},
 {"title":"Original Browser Games","text":"A growing collection of playful digital game experiences.","image":"site/heroes/game-studio.webp","category":"GAMES · DIGITAL","url":"/studio/"},
 {"title":"Research & Digital Project Services","text":"Research planning, digital product development, and professional web projects.","image":"site/heroes/research.webp","category":"SERVICES","url":"/company/"},
 {"title":"Atelier Interior — Client-Ready Website Kit","text":"An editable interior-studio website kit with original vector illustrations and a one-site license. See the product details for current availability and terms.","image_url":"https://mojplaywin.com/static/site/mojplaywin-products/atelier-interior-kit.webp","category":"WEBSITE KIT · INTERIOR DESIGN","url":"/store/product/879/"},
]
SECTIONS = {
 "agriculture":("Agriculture & Rural Services","From research and farm planning to production, processing, and market access.","site/heroes/agriculture.webp",[("Farm economics","Enterprise planning, cost analysis, and practical decision support."),("Smart production","Research-led approaches for crops, water, and resilient production."),("Value chains","Processing, packaging, market readiness, and rural services.")]),
 "industry":("Industry & Product Development","Turn a well-defined idea into a tested, documented, and market-ready product.","site/heroes/industry.webp",[("Product research","Scope, feasibility, and evidence before investment."),("Production systems","Process design, quality, and practical operations."),("Digital development","Tools and professional web projects for growing businesses.")]),
 "research":("Scientific Research & Innovation","Research, sources, evidence, and useful outputs in a clear and traceable workflow.","site/heroes/research.webp",[("Research planning","Define the question, objectives, and boundaries."),("Evidence review","Organize source material and compare findings."),("Practical reports","Translate research into clear next steps and useful resources.")]),
 "knowledge":("Knowledge Library","Explore accessible guides and reference material across science, technology, business, and creativity.","site/heroes/knowledge.webp",[("Research guides","Structured introductions and deeper reading paths."),("Digital learning","Practical explanations supported by examples."),("Curated library","Books, articles, and resources organized by topic.")]),
 "economy":("Economy & Market Intelligence","Clear, evidence-aware research on markets, production, trade, and value chains.","site/heroes/economy.webp",[("Market context","Understand key changes and the forces behind them."),("Scenario planning","Explore opportunities, uncertainty, and practical risks."),("Research reports","Readable analysis with sources and clear limitations.")]),
 "studio":("Games & Creative Studio","Original game concepts, digital play, and creative products built for curious audiences.","site/heroes/game-studio.webp",[("Original games","Small, approachable experiences designed around clear mechanics."),("Interactive stories","Creative narratives and playful learning experiences."),("Digital releases","A growing collection of games and creative products.")]),
 "market":("Digital Market & Products","Browse useful books, tools, learning resources, games, and professional services.","site/heroes/marketplace.webp",[("Learning products","Guides, books, and education resources."),("Digital tools","Practical calculators and focused utilities."),("Professional services","Research and digital project support.")]),
 "agents":("AI & Modern Technology","Explore responsible, practical uses of AI and digital tools for research, learning, and creative work.","site/heroes/ai.webp",[("AI learning","Understand core ideas through clear examples."),("Research support","Use tools to organize questions and explore evidence."),("Digital creativity","Build and test ideas with modern technology.")]),
 "company":("About MojPlayWin","A digital-first company bringing research, modern technology, games, and education into one growing destination.","site/heroes/platform-home.webp",[("Our focus","Most of our work is dedicated to research, technology, games, and education."),("Our experience","We also draw on agriculture, jewelry and gold, handwoven carpets, hospitality, scientific project management, and web development."),("Work with us","Explore projects, learning resources, and selected digital products.")]),
}

def _is_mojplaywin(request):
 return request.get_host().split(":")[0].lower() in {"mojplaywin.com", "www.mojplaywin.com"}

def home(request):
 return render(request,"mojplaywin/home.html",{"features":FEATURES,"ventures":VENTURES})

def branded_home_dispatch(request):
 if _is_mojplaywin(request):
  return home(request)
 from .brand_views import branded_home
 return branded_home(request)

def branded_store_dispatch(request):
 if _is_mojplaywin(request):
  return store(request)
 from .brand_views import branded_store
 return branded_store(request)

def store(request):
 return render(request,"mojplaywin/store.html",{"products":PRODUCTS})

def venture(request, slug):
 if not _is_mojplaywin(request):
  raise Http404
 item=next((entry for entry in VENTURES if entry["slug"] == slug), None)
 if item is None:
  raise Http404
 return render(request,"mojplaywin/section.html",{"section_title":item["title"],"section_lead":item["lead"],"section_image":item["image"],"cards":item["cards"],"section_note":item["note"],"ventures":VENTURES,"active_venture":slug,"related_url":"/research/","related_label":"Explore supporting research"})


# Route each section to a relevant real main-site destination, not the same store card.
RELATED_SECTION_LINKS = {
    "research": ("/knowledge/", "Read the knowledge library"),
    "knowledge": ("/research/", "Explore scientific research"),
    "company": ("/about/", "Read our company profile"),
    "industry": ("/services/", "Explore professional services"),
    "agents": ("/ai/", "Explore AI resources"),
    "market": ("/store/", "Browse the digital store"),
    "economy": ("/research/", "Explore research"),
    "studio": ("/games/", "Explore original games"),
    "agriculture": ("/ventures/agriculture/", "Explore agriculture"),
}

def platform_section(request, section):
 data=SECTIONS.get(section)
 if data is None:
  data=("Explore MojPlayWin","Explore research, learning, games, and useful digital projects.","site/heroes/platform-home.webp",[("Discover","Explore the work and ideas behind MojPlayWin."),("Learn","Find practical learning resources and guides."),("Get in touch","Discuss a research or digital project.")])
 title,lead,image,cards=data
 related_url, related_label = RELATED_SECTION_LINKS.get(section, ("/store/", "Browse related resources"))
 return render(request,"mojplaywin/section.html",{"section_title":title,"section_lead":lead,"section_image":image,"cards":cards,"ventures":VENTURES,"related_url":related_url,"related_label":related_label})
