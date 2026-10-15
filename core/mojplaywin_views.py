from django.shortcuts import render

FEATURES = [
 {"title":"Research & Innovation","text":"Evidence-led research, practical analysis, and ideas shaped into useful digital work.","image":"site/heroes/research.webp","url":"/research/"},
 {"title":"Games & Creative Studio","text":"Original game concepts, playful experiences, and digital entertainment projects.","image":"site/heroes/game-studio.webp","url":"/studio/"},
 {"title":"Learning & Education","text":"Clear learning paths connecting modern technology with practical skills.","image":"site/heroes/education-detail.webp","url":"/amozeshgah/"},
 {"title":"Digital Store","text":"Books, learning resources, games, and practical digital tools in one catalog.","image":"site/heroes/store.webp","url":"/store/"},
 {"title":"Artificial Intelligence","text":"Thoughtful AI tools and explainers for research, creativity, and everyday work.","image":"site/heroes/ai.webp","url":"/agents/"},
 {"title":"Knowledge Library","text":"Guides and reference material organized to make complex topics easier to explore.","image":"site/heroes/knowledge.webp","url":"/knowledge/"},
]
PRODUCTS = [
 {"title":"The Science and Practice of Chess Improvement","text":"A structured chess study resource with lessons, analysis, and exercises.","image":"site/heroes/education-detail.webp","category":"BOOK · LEARNING","url":"/store/"},
 {"title":"Taniya and the Little Baker Worms","text":"A rhythmic illustrated story created for young readers and families.","image":"site/heroes/game-studio.webp","category":"CHILDREN'S BOOK","url":"/taniya/"},
 {"title":"Farm Enterprise Economics Toolkit","text":"A practical digital toolkit for farm planning and enterprise economics.","image":"site/heroes/agriculture.webp","category":"AGRICULTURE · TOOLKIT","url":"/market/"},
 {"title":"Applied AI Learning Path","text":"A step-by-step route from foundational AI ideas to practical applications.","image":"site/heroes/ai.webp","category":"COURSE · TECHNOLOGY","url":"/amozeshgah/"},
 {"title":"Original Browser Games","text":"A growing collection of playful digital game experiences.","image":"site/heroes/game-studio.webp","category":"GAMES · DIGITAL","url":"/studio/"},
 {"title":"Research & Digital Project Services","text":"Research planning, digital product development, and professional web projects.","image":"site/heroes/research.webp","category":"SERVICES","url":"/company/"},
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

def home(request):
 return render(request,"mojplaywin/home.html",{"features":FEATURES})

def store(request):
 return render(request,"mojplaywin/store.html",{"products":PRODUCTS})

def platform_section(request, section):
 data=SECTIONS.get(section)
 if data is None:
  data=("Explore MojPlayWin","Explore research, learning, games, and useful digital projects.","site/heroes/platform-home.webp",[("Discover","Explore the work and ideas behind MojPlayWin."),("Learn","Find practical learning resources and guides."),("Get in touch","Discuss a research or digital project.")])
 title,lead,image,cards=data
 return render(request,"mojplaywin/section.html",{"section_title":title,"section_lead":lead,"section_image":image,"cards":cards})
