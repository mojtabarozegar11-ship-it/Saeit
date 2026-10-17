"""Fact-conscious, read-only editorial content for main MojPlayWin pages only.

Every content block is keyed by an existing MojPlayWin route. No status,
sales, partnership, inventory or operating-agent claim is invented here.
Existing Django admin, other hosts and the payment systems are untouched.
"""
EDITORIAL = {
  "section:agriculture": {
    "headline": "From the farm decision to the market",
    "overview": [
      "Strong agricultural planning starts with an explicit production unit: a crop, greenhouse, herd or farm enterprise in a defined season and location. Record land, water, labor, inputs, cost assumptions and access to buyers before evaluating any investment.",
      "Resilience is more than higher yield. Compare the effects of water limitations, price uncertainty, soil constraints and post-harvest losses. A useful decision framework shows which assumptions change the preferred option and which actions can be tested at small scale."
    ],
    "steps": [
      {
        "title": "Map resources",
        "detail": "Document land area, irrigation source, soil information, growing calendar, workforce and constraints. Flag missing measurements rather than inventing precision."
      },
      {
        "title": "Build scenarios",
        "detail": "Compare expected, downside and improvement cases using consistent units for yields, costs, water consumption and farm-gate prices."
      },
      {
        "title": "Assess the value chain",
        "detail": "Follow storage, grading, packaging, transport, buyer requirements and waste. Calculate margins after realistic variable costs."
      },
      {
        "title": "Pilot and review",
        "detail": "Validate assumptions with a limited trial, track actual inputs and outputs, and revise recommendations before scaling."
      }
    ],
    "deliverables": [
      "An enterprise budget with traceable assumptions and scenario sensitivity.",
      "A crop or production calendar with measurable water and input needs.",
      "A value-chain map connecting production, processing and market readiness."
    ],
    "images": [
      {
        "path": "site/heroes/agriculture.webp",
        "alt": "Editorial concept illustration — crop and field planning",
        "caption": "crop and field planning"
      },
      {
        "path": "site/heroes/smart-agriculture.webp",
        "alt": "Editorial concept illustration — precision agriculture decision support",
        "caption": "precision agriculture decision support"
      },
      {
        "path": "site/heroes/genetics.webp",
        "alt": "Editorial concept illustration — crop variety and biological research",
        "caption": "crop variety and biological research"
      }
    ],
    "note": "Educational and planning content; not a claim of land ownership, a licensed agronomy service or guaranteed yield.",
    "link": "/company/"
  },
  "section:industry": {
    "headline": "Engineering products that can be documented and delivered",
    "overview": [
      "An industrial product succeeds when its purpose, requirements and test conditions are understood before production begins. Create a requirements baseline, identify failure modes and distinguish an attractive prototype from a manufacturable specification.",
      "Cost and quality belong in the same decision. Process capacity, scrap, traceability, sourcing, packaging and maintenance can dominate the final economics. A transparent feasibility study makes operational limits visible before a purchase or manufacturing commitment."
    ],
    "steps": [
      {
        "title": "Define the product",
        "detail": "Write user requirements, functional boundaries, interfaces and measurable acceptance criteria, including regulatory and safety dependencies."
      },
      {
        "title": "Prototype responsibly",
        "detail": "Select a smallest useful prototype and document revisions, materials, supplier assumptions, test methods and outstanding defects."
      },
      {
        "title": "Review production",
        "detail": "Map equipment, cycle time, capacity bottlenecks, quality checkpoints, waste and preventive maintenance."
      },
      {
        "title": "Plan market readiness",
        "detail": "Prepare specifications, documentation, customer onboarding and support responsibilities without representing proposals as stocked goods."
      }
    ],
    "deliverables": [
      "A product requirement and verification checklist.",
      "A process and cost model with explicit throughput and scrap assumptions.",
      "A staged readiness plan from prototype to tested deliverable."
    ],
    "images": [
      {
        "path": "site/heroes/industry.webp",
        "alt": "Editorial concept illustration — industrial product engineering",
        "caption": "industrial product engineering"
      },
      {
        "path": "site/heroes/laboratory.webp",
        "alt": "Editorial concept illustration — prototype testing and laboratory methods",
        "caption": "prototype testing and laboratory methods"
      },
      {
        "path": "site/heroes/services.webp",
        "alt": "Editorial concept illustration — professional project execution",
        "caption": "professional project execution"
      }
    ],
    "note": "Design and feasibility material only; manufacturing capacity and certification must be verified for each actual project.",
    "link": "/company/"
  },
  "section:research": {
    "headline": "Questions, evidence, analysis and reproducible decisions",
    "overview": [
      "Reliable research begins with a narrow question, a declared method and a clear separation between observed data, assumptions and interpretation. Good findings should be intelligible to a decision-maker and traceable to their sources.",
      "Scientific and commercial investigations share essential disciplines: sampling, comparison, uncertainty, review and version control. An evidence register helps teams revisit a conclusion when new measurements or market conditions become available."
    ],
    "steps": [
      {
        "title": "Form the question",
        "detail": "Specify the population, outcome, time horizon, success criteria and reasons the result will matter."
      },
      {
        "title": "Build an evidence register",
        "detail": "Capture source provenance, publication date, relevance, quality concerns and conflicts. Mark claims that remain unverified."
      },
      {
        "title": "Analyze alternatives",
        "detail": "Compare baseline and competing hypotheses; describe assumptions, method limits and sensitivity instead of forcing certainty."
      },
      {
        "title": "Publish a usable report",
        "detail": "Present findings, uncertainty, references, decisions and next tests in a versioned, reviewable structure."
      }
    ],
    "deliverables": [
      "A research brief with questions, methods and limitations.",
      "A referenced evidence table and structured comparison.",
      "A decision-ready report with uncertainty and next experiments."
    ],
    "images": [
      {
        "path": "site/heroes/research.webp",
        "alt": "Editorial concept illustration — scientific inquiry and evidence",
        "caption": "scientific inquiry and evidence"
      },
      {
        "path": "site/heroes/laboratory.webp",
        "alt": "Editorial concept illustration — experimental research methods",
        "caption": "experimental research methods"
      },
      {
        "path": "site/heroes/knowledge.webp",
        "alt": "Editorial concept illustration — organized scientific reference",
        "caption": "organized scientific reference"
      }
    ],
    "note": "No unverified academic affiliation, publication, laboratory capacity or experimental result is implied.",
    "link": "/company/"
  },
  "section:knowledge": {
    "headline": "Turn technical material into knowledge that can be used",
    "overview": [
      "A reference library becomes valuable when readers can find a specific explanation, evaluate its source and continue to a worked example. Strong topic pages define terms consistently and connect introductory explanations with advanced material.",
      "Editorial maintenance is essential: procedures change, software versions advance and practical assumptions expire. Each guide should have a scope, reviewed references and a clear distinction between instruction and opinion."
    ],
    "steps": [
      {
        "title": "Structure the subject",
        "detail": "Create a concise definition, prerequisite concepts, a typical application and relevant cross-references."
      },
      {
        "title": "Explain with examples",
        "detail": "Use worked cases, glossary entries and visuals to bridge the gap between an abstract definition and a practical action."
      },
      {
        "title": "Verify the source",
        "detail": "Record authorship, evidence strength, date, version and known limits; separate illustrative figures from reported measurements."
      },
      {
        "title": "Maintain the library",
        "detail": "Track reader questions, broken links, corrections and updates so useful articles do not become stale."
      }
    ],
    "deliverables": [
      "A topic outline and glossary for self-study.",
      "A practical learning guide with worked examples and references.",
      "A maintenance checklist for updates, corrections and version changes."
    ],
    "images": [
      {
        "path": "site/heroes/knowledge.webp",
        "alt": "Editorial concept illustration — curated reference library",
        "caption": "curated reference library"
      },
      {
        "path": "site/heroes/education-detail.webp",
        "alt": "Editorial concept illustration — guided digital learning",
        "caption": "guided digital learning"
      },
      {
        "path": "site/heroes/research.webp",
        "alt": "Editorial concept illustration — evidence and sources",
        "caption": "evidence and sources"
      }
    ],
    "note": "Knowledge articles are educational and not substitutes for qualified professional advice when regulated decisions are involved.",
    "link": "/company/"
  },
  "section:economy": {
    "headline": "Economic decisions under measurable uncertainty",
    "overview": [
      "Markets reflect changing prices, costs, incentives and expectations. An applied economic brief should describe what was observed, the date and geography of the observation, and why it matters to a particular business decision.",
      "Forecasting is scenario work, not certainty. Combining unit economics with sensitivity analysis often provides more actionable insight than a single market headline. Revenue, contribution margin, fixed costs and cash flow must remain separate."
    ],
    "steps": [
      {
        "title": "Define an indicator",
        "detail": "Select the relevant price, cost, output, productivity or market measure and document units, period and source."
      },
      {
        "title": "Compare scenarios",
        "detail": "Model baseline, adverse and favorable changes in sales volume, exchange exposure, direct costs and financing."
      },
      {
        "title": "Study constraints",
        "detail": "Include production capacity, seasonal demand, buyer concentration, applicable regulation, financing costs and realistic working-capital needs before comparing options."
      },
      {
        "title": "Turn analysis into action",
        "detail": "Record what would justify proceeding, revising the project or stopping, and which data must be refreshed."
      }
    ],
    "deliverables": [
      "A transparent unit-economics calculation.",
      "An economic sensitivity table with clear assumptions.",
      "A market brief identifying risks, triggers and follow-up evidence."
    ],
    "images": [
      {
        "path": "site/heroes/economy.webp",
        "alt": "Editorial concept illustration — market and economic scenario analysis",
        "caption": "market and economic scenario analysis"
      },
      {
        "path": "site/heroes/marketplace.webp",
        "alt": "Editorial concept illustration — digital and physical trade",
        "caption": "digital and physical trade"
      },
      {
        "path": "site/heroes/industry.webp",
        "alt": "Editorial concept illustration — production cost planning",
        "caption": "production cost planning"
      }
    ],
    "note": "Examples are not live price quotations, investment advice or guaranteed financial outcomes.",
    "link": "/company/"
  },
  "section:studio": {
    "headline": "From playable idea to original digital experience",
    "overview": [
      "Successful game projects begin with a coherent interaction loop: what a player does, what feedback they receive and why the next decision matters. A short playable vertical slice is more revealing than a large library of concept screens.",
      "Original intellectual property, accessibility, performance and repeatable quality checks are core to sustainable production. The aim is to make the experience testable and understandable before scaling levels, modes and digital goods."
    ],
    "steps": [
      {
        "title": "Design the core loop",
        "detail": "Define mechanics, control input, win and loss conditions, difficulty and five-minute test criteria."
      },
      {
        "title": "Create a playable slice",
        "detail": "Build a small complete sequence with original visuals, sound choices and meaningful player feedback."
      },
      {
        "title": "Test accessibility",
        "detail": "Review keyboard/touch interactions, readable contrast, subtitles, reduced-motion support and performance on modest devices."
      },
      {
        "title": "Prepare the release",
        "detail": "Document compatibility, known bugs, licensing, build versions, instructions and a truthful public demonstration."
      }
    ],
    "deliverables": [
      "A concise game design document and testable gameplay loop.",
      "A prototype evaluation matrix with accessibility findings.",
      "A release checklist for performance, content rights and player support."
    ],
    "images": [
      {
        "path": "site/heroes/game-studio.webp",
        "alt": "Editorial concept illustration — creative game design",
        "caption": "creative game design"
      },
      {
        "path": "site/heroes/ai.webp",
        "alt": "Editorial concept illustration — AI-assisted creative production concepts",
        "caption": "AI-assisted creative production concepts"
      },
      {
        "path": "site/heroes/education-detail.webp",
        "alt": "Editorial concept illustration — interactive learning experiences",
        "caption": "interactive learning experiences"
      }
    ],
    "note": "Game concepts and development methods must not be presented as downloadable finished games until a tested build exists.",
    "link": "/company/"
  },
  "section:market": {
    "headline": "A digital catalog should explain exactly what the buyer receives",
    "overview": [
      "Digital products are not just attractive thumbnails. Every item needs a truthful description of its format, version, supported devices, intended audience, usage rights and post-purchase access. A clear catalog reduces customer confusion and preventable support requests.",
      "A reliable sales journey separates browsing from a verified checkout. If an actual purchase route has not been tested, the item should remain a preview rather than collecting money through an unverified path."
    ],
    "steps": [
      {
        "title": "Prepare the listing",
        "detail": "Define the real deliverable, scope, included files, language, compatibility, license, price and limitations."
      },
      {
        "title": "Verify quality",
        "detail": "Test downloads, opening files, sample inputs, formatting and accessibility on intended devices."
      },
      {
        "title": "Check fulfillment",
        "detail": "Confirm invoice creation, verified payment, entitlement issuance and re-download only in an authorized test environment."
      },
      {
        "title": "Improve service",
        "detail": "Record support questions, update notices and documented remediation when a published item has defects."
      }
    ],
    "deliverables": [
      "A complete product specification template.",
      "A delivery and compatibility acceptance checklist.",
      "A supported purchase-to-entitlement test scenario for eligible products."
    ],
    "images": [
      {
        "path": "site/heroes/store.webp",
        "alt": "Editorial concept illustration — digital storefront and product library",
        "caption": "digital storefront and product library"
      },
      {
        "path": "site/heroes/marketplace.webp",
        "alt": "Editorial concept illustration — online marketplace browsing",
        "caption": "online marketplace browsing"
      },
      {
        "path": "site/heroes/services.webp",
        "alt": "Editorial concept illustration — professional services catalog",
        "caption": "professional services catalog"
      }
    ],
    "note": "No unverified inventory, discount, purchase button or successful payment claim is added here.",
    "link": "/company/"
  },
  "section:agents": {
    "headline": "Design AI agents as supervised, observable workflows",
    "overview": [
      "An agent is operational only when it has a defined task, assigned permissions, a runnable execution path and verifiable results. A menu label or active database flag does not prove that scheduled jobs are running. Observability must include heartbeat, queue size, recent outcomes and error history.",
      "Sensitive actions need explicit boundaries. A content assistant may generate drafts, but publishing, changing production systems and handling payments require independent safeguards and evidence. Domain ownership must be established before enabling any shared worker."
    ],
    "steps": [
      {
        "title": "Inventory and isolate",
        "detail": "Identify registered agent codes, capabilities, owner domain and runtime. Reject any workflow without a proven MojPlayWin-only scope."
      },
      {
        "title": "Verify read-only health",
        "detail": "Inspect active flags, scheduler status, last successful run, queued tasks, failures and available execution logs."
      },
      {
        "title": "Exercise a safe task",
        "detail": "Use an isolated test task with no payment, publishing, shared database mutation or external side effects; verify the output and audit trail."
      },
      {
        "title": "Enable with controls",
        "detail": "Only after isolation, configure supervised scheduling, bounded retries, manual stop capability and staff-only diagnostics."
      }
    ],
    "deliverables": [
      "An agent capability and ownership inventory.",
      "A runbook for health checks, queue inspection and recovery.",
      "A controlled agent activation checklist with explicit no-go criteria."
    ],
    "images": [
      {
        "path": "site/mojplaywin-atelier/ai-workflow.svg",
        "alt": "Editorial concept illustration — responsible AI automation",
        "caption": "responsible AI automation"
      },
      {
        "path": "site/heroes/research.webp",
        "alt": "Editorial concept illustration — evidence-backed agent research",
        "caption": "evidence-backed agent research"
      },
      {
        "path": "site/heroes/laboratory.webp",
        "alt": "Editorial concept illustration — isolated testing and verification",
        "caption": "isolated testing and verification"
      }
    ],
    "note": "This section is a technical guide. It does not state that any specific MojPlayWin agent is currently running.",
    "link": "/company/"
  },
  "section:company": {
    "headline": "A research-led digital business with a practical project approach",
    "overview": [
      "MojPlayWin brings together a proposed digital-first focus on research, software, interactive games, education, e-commerce and responsible Web3 work. Complementary specialist knowledge extends into agriculture, industrial projects, hospitality, crafts and web development.",
      "Partnerships are best evaluated through bounded pilot projects. A prospective customer should understand the problem being addressed, the expected result, relevant intellectual-property terms, the review process and the circumstances under which a pilot becomes a larger engagement."
    ],
    "steps": [
      {
        "title": "Discover the need",
        "detail": "Document the visitor's industry, main problem, users, current process and expected measurable improvement."
      },
      {
        "title": "Propose a bounded pilot",
        "detail": "Specify approved inputs, representative sample data, technical dependencies, delivery milestones, acceptance tests and documented ownership of results."
      },
      {
        "title": "Protect information",
        "detail": "Clarify confidentiality, data retention, asset licensing and approvals before processing client material."
      },
      {
        "title": "Review value delivered",
        "detail": "Demonstrate usable outputs, share known limitations and agree on support or further development if appropriate."
      }
    ],
    "deliverables": [
      "A partnership discovery questionnaire.",
      "A pilot project charter with acceptance criteria.",
      "A responsibility and quality checklist for delivery."
    ],
    "images": [
      {
        "path": "site/heroes/platform-home.webp",
        "alt": "Editorial concept illustration — digital company and projects",
        "caption": "digital company and projects"
      },
      {
        "path": "site/heroes/services.webp",
        "alt": "Editorial concept illustration — professional project collaboration",
        "caption": "professional project collaboration"
      },
      {
        "path": "site/heroes/research.webp",
        "alt": "Editorial concept illustration — scientific research activities",
        "caption": "scientific research activities"
      }
    ],
    "note": "Company descriptions and cooperation examples do not claim unverified contracts, operating locations or revenue.",
    "link": "/company/"
  },
  "venture:agriculture": {
    "headline": "A practical agricultural venture roadmap",
    "overview": [
      "An agricultural service concept may combine farm budgeting, production planning and market preparation. The first task is to make the target enterprise explicit: an open-field crop, greenhouse, livestock operation or post-harvest service. Each has different constraints.",
      "A useful project starts with measured resources and feasibility rather than photographs of an ideal facility. Yield assumptions, input costs and sales channels should be checked against local conditions and uncertainty."
    ],
    "steps": [
      {
        "title": "Select enterprise",
        "detail": "Define species or crop, area or capacity, location, season, water and material inputs."
      },
      {
        "title": "Plan resources",
        "detail": "Estimate labor, working capital, utilities, biosecurity protocols, seasonal constraints and local regulatory requirements for the selected enterprise."
      },
      {
        "title": "Evaluate economics",
        "detail": "Model gross output, unsold waste, variable costs, capital needs, cash timing and plausible downside production conditions."
      },
      {
        "title": "Prepare pilot",
        "detail": "Specify a limited demonstration, measurement schedule and criteria for a go/no-go decision."
      }
    ],
    "deliverables": [
      "A venture feasibility worksheet.",
      "An input, production and value-chain checklist.",
      "A risk-aware pilot project brief."
    ],
    "images": [
      {
        "path": "site/heroes/smart-agriculture.webp",
        "alt": "Editorial concept illustration — farm decision dashboards",
        "caption": "farm decision dashboards"
      },
      {
        "path": "site/heroes/agriculture.webp",
        "alt": "Editorial concept illustration — farm systems and crop planning",
        "caption": "farm systems and crop planning"
      },
      {
        "path": "site/heroes/genetics.webp",
        "alt": "Editorial concept illustration — production and genetics research",
        "caption": "production and genetics research"
      }
    ],
    "note": "No active farm, livestock facility or product stock is represented without verification.",
    "link": "/company/"
  },
  "venture:cafe-restaurant": {
    "headline": "Restaurant and cafe operations start with service design",
    "overview": [
      "Hospitality projects need a consistent guest promise supported by repeatable kitchen and service processes. An appealing menu is sustainable only when recipes, portions, allergen information, labor, waste and supplier reliability can be managed.",
      "Digital services can help with menus, reservation inquiries, staff workflows and order visibility. Actual online ordering should be offered only when staffing, legal disclosures, payment and fulfillment have been tested."
    ],
    "steps": [
      {
        "title": "Define the concept",
        "detail": "Identify audience, cuisine or beverage position, service model, operating hours and price expectations."
      },
      {
        "title": "Engineer the menu",
        "detail": "Calculate recipe yield, ingredient cost, allergens, preparation time and expected waste for representative items."
      },
      {
        "title": "Map guest operations",
        "detail": "Describe guest arrival, ordering, kitchen hand-off, payment confirmation, service recovery, staff responsibility and quality monitoring at each step."
      },
      {
        "title": "Test the experience",
        "detail": "Trial a small menu and service flow; use real demand and feedback before investing in a broad expansion."
      }
    ],
    "deliverables": [
      "A standardized menu and portion-costing worksheet.",
      "A guest-journey and operations map.",
      "A launch-readiness checklist for food safety and service."
    ],
    "images": [
      {
        "path": "site/heroes/marketplace.webp",
        "alt": "Editorial concept illustration — cafe retail and menu concepts",
        "caption": "cafe retail and menu concepts"
      },
      {
        "path": "site/heroes/services.webp",
        "alt": "Editorial concept illustration — restaurant service workflow design",
        "caption": "restaurant service workflow design"
      },
      {
        "path": "site/heroes/store.webp",
        "alt": "Editorial concept illustration — online product catalog design",
        "caption": "online product catalog design"
      }
    ],
    "note": "Examples are concepts, not claims of an operating restaurant, online reservation service or certified kitchen.",
    "link": "/company/"
  },
  "venture:fuel-station": {
    "headline": "Fuel and mobility projects require safety-first feasibility",
    "overview": [
      "Fuel stations and mobility services are location-sensitive, highly regulated operations. Before describing an opportunity as buildable, confirm land use, traffic demand, environmental controls, fire safety, utilities, access points and operating licenses with qualified local specialists.",
      "A responsible digital portfolio can support feasibility studies and customer-service software, but it must distinguish conceptual planning from owning or operating a licensed station."
    ],
    "steps": [
      {
        "title": "Map the site",
        "detail": "Record access, traffic patterns, utilities, zoning and nearby demand drivers without assuming permits."
      },
      {
        "title": "Assess compliance",
        "detail": "Identify environmental protection, hazardous materials, safety distances, fire-code reviews and qualified engineering needs."
      },
      {
        "title": "Build scenarios",
        "detail": "Compare expected traffic, product mix, capital expense, working capital and sensitivity to utilization."
      },
      {
        "title": "Plan digital services",
        "detail": "Outline customer information, maintenance reporting and operational dashboards subject to verified business permissions."
      }
    ],
    "deliverables": [
      "A regulatory and site diligence checklist.",
      "A feasibility assumptions and scenario workbook.",
      "A digital service concept with safety and operational limitations."
    ],
    "images": [
      {
        "path": "site/heroes/industry.webp",
        "alt": "Editorial concept illustration — industrial infrastructure planning",
        "caption": "industrial infrastructure planning"
      },
      {
        "path": "site/heroes/economy.webp",
        "alt": "Editorial concept illustration — fuel and mobility demand economics",
        "caption": "fuel and mobility demand economics"
      },
      {
        "path": "site/heroes/services.webp",
        "alt": "Editorial concept illustration — engineering and project-management processes",
        "caption": "engineering and project-management processes"
      }
    ],
    "note": "No fuel retail, fuel price, station location or licensed operation is advertised.",
    "link": "/company/"
  },
  "venture:jewelry-gold": {
    "headline": "Precious materials need provenance and careful product specifications",
    "overview": [
      "A jewelry catalog should communicate metal type, fineness, measured dimensions, weight, gemstone identification and pricing terms accurately. Photography, design storytelling and craft heritage help customers explore a piece, but they do not replace independent verification.",
      "For a custom-design service, the production brief should distinguish sketches, renderings and finished goods. Customers need clear timelines, revision limits and disclosure of appraisals, hallmarking and return rules."
    ],
    "steps": [
      {
        "title": "Document materials",
        "detail": "Record metal purity, weight units, treatment disclosure, gemstone identity and provenance evidence where available."
      },
      {
        "title": "Prepare design visuals",
        "detail": "Create accurate multiple-view images or drawings, stating whether the piece exists or is only a concept."
      },
      {
        "title": "Set commercial terms",
        "detail": "Clarify quoted price scope, taxes, fabrication, certification, shipping insurance and applicable consumer rights."
      },
      {
        "title": "Verify delivery",
        "detail": "Check final dimensions, material identity, quality documentation and secure fulfillment before labeling as available."
      }
    ],
    "deliverables": [
      "A transparent product specification and authenticity checklist.",
      "A custom jewelry design brief and revision plan.",
      "A customer disclosure and verified-delivery workflow."
    ],
    "images": [
      {
        "path": "site/heroes/laboratory.webp",
        "alt": "Editorial concept illustration — material assessment and verification concepts",
        "caption": "material assessment and verification concepts"
      },
      {
        "path": "site/heroes/marketplace.webp",
        "alt": "Editorial concept illustration — retail catalog presentation",
        "caption": "retail catalog presentation"
      },
      {
        "path": "site/heroes/economy.webp",
        "alt": "Editorial concept illustration — precious metals business economics",
        "caption": "precious metals business economics"
      }
    ],
    "note": "No unverified inventory, gemstone certificate, gold price or investment return is claimed.",
    "link": "/company/"
  },
  "venture:carpets": {
    "headline": "Connect carpet craftsmanship with trustworthy online presentation",
    "overview": [
      "Handwoven textiles vary in technique, region, fiber composition, knot structure, age and condition. A credible listing explains these attributes and separates confirmed provenance from a seller's tradition or estimate.",
      "Large textiles need careful visual documentation: full view, reverse side, border and close-up texture. Online sales must also account for measurements, color differences, cleaning condition and delivery requirements."
    ],
    "steps": [
      {
        "title": "Identify construction",
        "detail": "Describe weave, materials, dimensions, design characteristics and any documented origin or maker."
      },
      {
        "title": "Photograph accurately",
        "detail": "Capture full front, reverse, edge and texture under consistent lighting, with a scale reference."
      },
      {
        "title": "Assess condition",
        "detail": "Record repairs, fading, wear, pile variation and care restrictions without concealing defects."
      },
      {
        "title": "Prepare selling terms",
        "detail": "Clarify provenance and originality evidence, transport method, returns, safe handling, shipping insurance and realistic customer expectations before listing."
      }
    ],
    "deliverables": [
      "A detailed handwoven carpet listing checklist.",
      "A photography and condition-report guide.",
      "A transparent packaging and delivery specification."
    ],
    "images": [
      {
        "path": "site/heroes/knowledge.webp",
        "alt": "Editorial concept illustration — craft heritage and reference",
        "caption": "craft heritage and reference"
      },
      {
        "path": "site/heroes/marketplace.webp",
        "alt": "Editorial concept illustration — artisan retail catalog",
        "caption": "artisan retail catalog"
      },
      {
        "path": "site/heroes/services.webp",
        "alt": "Editorial concept illustration — digital presentation and trade support",
        "caption": "digital presentation and trade support"
      }
    ],
    "note": "No carpet ownership, authenticity guarantee or available stock is implied.",
    "link": "/company/"
  },
  "venture:currency-crypto": {
    "headline": "Blockchain education and technical services with clear risk boundaries",
    "overview": [
      "Digital assets involve operational, smart-contract and custody risks. An educational or software-service page should distinguish blockchain concepts, network fees, wallet security and asset volatility from regulated exchange, custody or investment services.",
      "Technical projects benefit from test networks, independently reviewed contracts and reconciliation evidence. A visible crypto-payment logo alone does not prove that an invoice can be paid, verified and fulfilled safely."
    ],
    "steps": [
      {
        "title": "Clarify the use case",
        "detail": "Identify whether the goal is learning, analytics, payment integration or a Web3 software workflow."
      },
      {
        "title": "Evaluate security",
        "detail": "Document custody boundaries, key management, transaction confirmations, malicious signature risk and network assumptions."
      },
      {
        "title": "Test integration",
        "detail": "Exercise invoice lifecycle, webhook authenticity, duplicate events, idempotency and reconciliation in a non-production environment."
      },
      {
        "title": "Publish limitations",
        "detail": "Describe supported networks, gas costs, transaction finality, refund procedures, user custody responsibilities and applicable regulatory dependencies accurately."
      }
    ],
    "deliverables": [
      "A blockchain technology primer with security checklist.",
      "A sandbox payment-integration test plan.",
      "A consumer disclosure guide separating software from financial services."
    ],
    "images": [
      {
        "path": "site/mojplaywin-atelier/blockchain-network.svg",
        "alt": "Editorial concept illustration — technical digital systems and automation",
        "caption": "technical digital systems and automation"
      },
      {
        "path": "site/heroes/economy.webp",
        "alt": "Editorial concept illustration — digital markets and economic uncertainty",
        "caption": "digital markets and economic uncertainty"
      },
      {
        "path": "site/heroes/laboratory.webp",
        "alt": "Editorial concept illustration — security review and isolated testing",
        "caption": "security review and isolated testing"
      }
    ],
    "note": "No cryptocurrency exchange, investment signal, custody product or trading execution is represented as active.",
    "link": "/company/"
  },
  "venture:ecommerce": {
    "headline": "Build an e-commerce journey that completes the job",
    "overview": [
      "A useful online store connects discovery, accurate product detail, cart, payment, fulfillment and support. Visitors should be able to tell which items are purchasable now, which are preorders and which are concepts.",
      "Operational performance matters as much as visual design. Missing stock synchronization, broken confirmation messages and inaccessible checkout frequently produce costly failures after the storefront looks complete."
    ],
    "steps": [
      {
        "title": "Define catalog truth",
        "detail": "Maintain real product identifiers, availability, shipping or download format, taxes, policies and supported destinations."
      },
      {
        "title": "Design the journey",
        "detail": "Test product discovery, search, compare, cart and checkout with assistive technology and small screens."
      },
      {
        "title": "Verify payment and delivery",
        "detail": "Confirm reconciled transactions, entitlement or shipping updates and safe behavior on cancellation or retry."
      },
      {
        "title": "Measure and support",
        "detail": "Track real fulfillment, returns, failed payments and requests for help without misleading revenue claims."
      }
    ],
    "deliverables": [
      "A storefront acceptance-test matrix.",
      "A product-data quality and fulfillment checklist.",
      "An accessible purchase-to-support journey map."
    ],
    "images": [
      {
        "path": "site/heroes/store.webp",
        "alt": "Editorial concept illustration — digital e-commerce product delivery",
        "caption": "digital e-commerce product delivery"
      },
      {
        "path": "site/heroes/marketplace.webp",
        "alt": "Editorial concept illustration — multi-category catalog and product presentation",
        "caption": "multi-category catalog and product presentation"
      },
      {
        "path": "site/heroes/services.webp",
        "alt": "Editorial concept illustration — software and digital operations",
        "caption": "software and digital operations"
      }
    ],
    "note": "No seller account, order flow or commission model is labeled active unless it has passed an end-to-end test.",
    "link": "/company/"
  },
  "venture:hospitality": {
    "headline": "Create repeatable, guest-centered hospitality services",
    "overview": [
      "Hospitality depends on reliable service, clear booking information and coordination between guest contact, housekeeping, suppliers and incident handling. Digital tools can improve the experience only when they reflect actual operational capacity.",
      "An early project should focus on a real workflow: booking inquiries, guest messaging, service tickets or a quality review process. A polished dashboard is useful only when responsibilities and response times are defined."
    ],
    "steps": [
      {
        "title": "Map the guest journey",
        "detail": "Describe discovery, inquiry, arrival, service requests, issue resolution and departure with owner roles."
      },
      {
        "title": "Define service standards",
        "detail": "Establish response expectations, escalation paths, accessibility needs, privacy-safe information collection, staff ownership and a consistent method for confirming completion."
      },
      {
        "title": "Plan digital tools",
        "detail": "Prototype an inquiry tracker, staff dashboard or guest information guide using representative test cases."
      },
      {
        "title": "Validate handoffs",
        "detail": "Test how a request moves between reception, operations and management and how completion is recorded."
      }
    ],
    "deliverables": [
      "A service blueprint and guest communication template.",
      "A support and escalation workflow.",
      "A privacy-conscious guest operations pilot brief."
    ],
    "images": [
      {
        "path": "site/heroes/platform-home.webp",
        "alt": "Editorial concept illustration — guest experience and business overview",
        "caption": "guest experience and business overview"
      },
      {
        "path": "site/heroes/contact.webp",
        "alt": "Editorial concept illustration — customer communication and contact planning",
        "caption": "customer communication and contact planning"
      },
      {
        "path": "site/heroes/services.webp",
        "alt": "Editorial concept illustration — service operations design",
        "caption": "service operations design"
      }
    ],
    "note": "No hotel, room inventory, reservation availability or active hospitality location is claimed.",
    "link": "/company/"
  }
}

def editorial_for(family, key):
    """Return a read-only presentation copy with original and mobile photo paths.

    EDITORIAL originals (text, ordering, alt text, captions and photos) are
    immutable source content. Every smaller WebP is a derived copy under the
    main MojPlayWin asset namespace. No product or database data is involved.
    """
    item = EDITORIAL.get(f"{family}:{key}")
    if item is None:
        return None
    image_specifications = []
    for image in item["images"]:
        presentation = dict(image)
        path = image["path"]
        if path.startswith("site/heroes/") and path.endswith(".webp"):
            presentation["mobile_path"] = (
                "site/mojplaywin-atelier/mobile-heroes/" + path[len("site/heroes/"):]
            )
        image_specifications.append(presentation)
    return {**item, "images": image_specifications}
