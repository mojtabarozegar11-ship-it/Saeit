"use strict";
(() => {
  const $ = (id) => document.getElementById(id);
  const storageKey = "mpw-arena-global-v1";
  const safeStorage = {
    get(key, fallback) { try { const v = localStorage.getItem(storageKey + ":" + key); return v === null ? fallback : JSON.parse(v); } catch { return fallback; } },
    put(key, value) { try { localStorage.setItem(storageKey + ":" + key, JSON.stringify(value)); return true; } catch { return false; } },
    remove(key) { try { localStorage.removeItem(storageKey + ":" + key); return true; } catch { return false; } }
  };
  const getBest = (name) => Number(safeStorage.get("best:" + name, 0)) || 0;
  const setBest = (name, value, lowerIsBetter = false) => {
    const old = getBest(name);
    if (!old || (lowerIsBetter ? value < old : value > old)) safeStorage.put("best:" + name, value);
    return getBest(name);
  };
  const experienceItems = [
    { icon:"⚡", name:"Skill Challenges", description:"Playable reaction, memory and knowledge sprints with local personal records.", category:"play", action:"Play now", href:"#play", color:"rgba(95,222,182,.22)" },
    { icon:"◈", name:"Free Forecast Studio", description:"Make probability forecasts and export your own research journal. Never a wager.", category:"play", action:"Forecast free", href:"#forecast", color:"rgba(139,120,240,.22)" },
    { icon:"♟", name:"Strategy Arena", description:"Explore thought-led competitive concepts and original strategy experiences.", category:"play", action:"Explore studio", href:"https://mojplaywin.com/studio/", color:"rgba(233,186,97,.20)" },
    { icon:"🧩", name:"Puzzle & Logic", description:"Short sessions for pattern recognition, reasoning and problem-solving.", category:"play", action:"Play skill lab", href:"#play", color:"rgba(111,147,233,.18)" },
    { icon:"🏆", name:"Community Leagues", description:"A planned home for free, transparent leagues and achievement-based events.", category:"social", action:"Learn the platform", href:"#partners", color:"rgba(233,168,97,.17)" },
    { icon:"🎙", name:"Entertainment Events", description:"Live quiz shows, creator events and sponsored experiences for future programming.", category:"social", action:"Partner opportunities", href:"#partners", color:"rgba(215,114,174,.18)" },
    { icon:"🌐", name:"Global Clubs", description:"An international vision for player clubs, friendly groups and team identity.", category:"social", action:"Explore vision", href:"#partners", color:"rgba(110,193,240,.17)" },
    { icon:"✦", name:"Creator Studio", description:"A proposed distribution channel for original games and audience experiences.", category:"social", action:"View opportunities", href:"#partners", color:"rgba(168,144,244,.20)" },
    { icon:"◉", name:"Brand Activations", description:"Bespoke quizzes, QR or product-code experiences and interactive campaigns.", category:"business", action:"For business", href:"#partners", color:"rgba(224,176,84,.23)" },
    { icon:"▧", name:"Digital Marketplace", description:"Connect with MojPlayWin digital products and relevant paid downloads.", category:"business", action:"Visit store", href:"https://mojplaywin.com/store/", color:"rgba(101,203,176,.18)" },
    { icon:"♜", name:"Event Infrastructure", description:"Organizers can explore fair-scoring challenges and white-label entertainment.", category:"business", action:"Partnerships", href:"#partners", color:"rgba(120,142,230,.20)" },
    { icon:"⚖", name:"Regulatory Gateway", description:"Real-money wagering stays locked unless separately licensed and approved.", category:"business", action:"Read status", href:"#compliance", color:"rgba(244,152,126,.17)" }
  ];
  const grid = $("experience-grid");
  for (const item of experienceItems) {
    const article = document.createElement("article");
    article.className = "experience-card";
    article.dataset.category = item.category;
    article.style.setProperty("--accent", item.color);
    const icon = document.createElement("span"); icon.className = "experience-icon"; icon.textContent = item.icon; icon.setAttribute("aria-hidden", "true");
    const title = document.createElement("h3"); title.textContent = item.name;
    const description = document.createElement("p"); description.textContent = item.description;
    const link = document.createElement("a"); link.className = "card-link"; link.href = item.href; link.textContent = item.action + " ↗"; link.setAttribute("aria-label", item.action + ": " + item.name);
    article.append(icon,title,description,link); grid.append(article);
  }
  document.querySelectorAll(".filter").forEach(button => button.addEventListener("click", () => {
    document.querySelectorAll(".filter").forEach(other => { const current = other === button; other.classList.toggle("active", current); other.setAttribute("aria-pressed", String(current)); });
    const value = button.dataset.filter;
    document.querySelectorAll(".experience-card").forEach(card => card.classList.toggle("is-hidden", value !== "all" && card.dataset.category !== value));
  }));

  const menu = $("main-nav"), menuToggle = $("menu-toggle");
  menuToggle.addEventListener("click", () => {
    const open = menu.classList.toggle("is-open");
    menuToggle.setAttribute("aria-expanded", String(open));
    menuToggle.textContent = open ? "✕" : "☰";
    menuToggle.setAttribute("aria-label", open ? "Close navigation" : "Open navigation");
  });
  menu.querySelectorAll("a").forEach(link => link.addEventListener("click", () => { menu.classList.remove("is-open"); menuToggle.setAttribute("aria-expanded","false"); menuToggle.textContent = "☰"; }));
  document.addEventListener("keydown", (event) => { if(event.key === "Escape") {menu.classList.remove("is-open");menuToggle.setAttribute("aria-expanded","false");menuToggle.textContent="☰";} });

  // Reaction: no financial value, no off-device leaderboard, no claim of network fairness.
  let reactionState = "idle", reactionTimer = null, reactionStart = 0;
  const reactionButton = $("reaction-button"), reactionStage = $("reaction-stage"), reactionPrompt = $("reaction-prompt"), reactionResult = $("reaction-result");
  const updateReactionBest = () => { const best = getBest("reaction"); $("reaction-best").textContent = best ? "Personal best: " + best + " ms" : "Personal best: not recorded"; };
  function finishReaction(message, result, state = "idle") {
    reactionState = state; reactionStage.className = "game-stage reaction-stage"; reactionPrompt.textContent = message; reactionResult.textContent = result;
    reactionButton.textContent = "Try another reaction"; clearTimeout(reactionTimer); reactionTimer = null;
  }
  function react() {
    if (reactionState === "waiting") { finishReaction("TOO EARLY", "FALSE START"); return; }
    if (reactionState === "go") {
      const duration = Math.max(1, Math.round(performance.now() - reactionStart));
      setBest("reaction", duration, true);
      finishReaction("YOUR RESPONSE TIME", duration + " ms"); updateReactionBest(); return;
    }
    reactionState = "waiting"; reactionStage.className = "game-stage reaction-stage waiting"; reactionPrompt.textContent = "WAIT FOR GREEN…"; reactionResult.textContent = "●"; reactionButton.textContent = "Tap when it turns green";
    reactionTimer = setTimeout(() => {
      reactionState = "go"; reactionStage.className = "game-stage reaction-stage go"; reactionPrompt.textContent = "GO! TAP NOW"; reactionResult.textContent = "⚡"; reactionStart = performance.now(); reactionButton.textContent = "TAP NOW!";
    }, 1400 + Math.floor(Math.random() * 2300));
  }
  reactionButton.addEventListener("click", react);
  reactionStage.addEventListener("click", () => { if (reactionState !== "idle") react(); });
  updateReactionBest();

  // Memory: randomized non-financial sequence challenge.
  let memoryLength = 4, memoryStreak = 0, memorySecret = "", memoryState = "idle", memoryTimer = null;
  const memoryStart = $("memory-start"), memoryCheck = $("memory-check"), memoryAnswer = $("memory-answer"), memorySequence = $("memory-sequence"), memoryStatus = $("memory-status");
  const updateMemoryBest = () => { $("memory-best").textContent = "Best streak: " + getBest("memory"); };
  function startMemory() {
    if (memoryState === "showing") return;
    clearTimeout(memoryTimer); memoryState = "showing"; memorySecret = Array.from({length:Math.min(memoryLength,12)}, () => Math.floor(Math.random() * 10)).join("");
    memorySequence.textContent = memorySecret; memoryStatus.textContent = "Memorize this sequence"; memoryAnswer.value = ""; memoryAnswer.disabled = true; memoryCheck.disabled = true; memoryStart.disabled = true;
    memoryTimer = setTimeout(() => { memoryState = "answering"; memorySequence.textContent = "● ".repeat(memorySecret.length).trim(); memoryStatus.textContent = "Enter all " + memorySecret.length + " digits"; memoryAnswer.disabled = false; memoryCheck.disabled = false; memoryStart.disabled = false; memoryStart.textContent = "Restart"; memoryAnswer.focus(); }, Math.min(4800, 1500 + memoryLength * 280));
  }
  function checkMemory() {
    if (memoryState !== "answering") return;
    const submitted = memoryAnswer.value.trim();
    memoryAnswer.disabled = true; memoryCheck.disabled = true;
    if (submitted === memorySecret) {
      memoryStreak++; memoryLength++; setBest("memory",memoryStreak);updateMemoryBest();
      memorySequence.textContent = "✓"; memoryStatus.textContent = "Correct! Streak " + memoryStreak + ". Next sequence loading…";
      memoryState = "showing"; memoryTimer = setTimeout(startMemory,950);
    } else {
      memorySequence.textContent = memorySecret; memoryStatus.textContent = "Incorrect. That was the sequence. Start again.";
      memoryState = "idle"; memoryLength = 4; memoryStreak = 0; memoryStart.textContent = "Try again"; memoryStart.disabled = false;
    }
  }
  memoryStart.addEventListener("click", () => { clearTimeout(memoryTimer); memoryLength = 4; memoryStreak = 0; memoryState = "idle"; startMemory(); });
  memoryCheck.addEventListener("click", checkMemory);
  memoryAnswer.addEventListener("keydown", event => { if(event.key === "Enter") checkMemory(); });
  updateMemoryBest();

  // Trivia questions and answers are authored content. This is a local knowledge challenge.
  const questionBank = [
    ["What is the chemical symbol for gold?",["Au","Ag","Fe","Cu"],0],
    ["Which ocean is the largest?",["Indian","Arctic","Atlantic","Pacific"],3],
    ["What does HTML primarily structure?",["A web page","A database","An image file","A payment network"],0],
    ["How many degrees are in a full circle?",["180","270","360","540"],2],
    ["Which is a prime number?",["21","29","35","39"],1],
    ["Which planet is known as the Red Planet?",["Mercury","Saturn","Mars","Venus"],2],
    ["How many bytes are in one kilobyte in decimal SI usage?",["100","512","1000","1024"],2],
    ["What is the capital of Japan?",["Kyoto","Osaka","Tokyo","Sapporo"],2],
    ["Which process do most green plants use to make sugars?",["Photosynthesis","Fermentation","Distillation","Electrolysis"],0],
    ["Which is the smallest continent by land area?",["Europe","Australia","Africa","Antarctica"],1],
    ["What is 12 × 8?",["84","88","96","108"],2],
    ["Which tool checks whether a website connection is encrypted?",["HTTPS indicator","Keyboard layout","Audio volume","Screen brightness"],0],
    ["Who wrote Hamlet?",["Virginia Woolf","William Shakespeare","Jane Austen","Homer"],1],
    ["Which gas makes up most of Earth's atmosphere?",["Oxygen","Nitrogen","Carbon dioxide","Helium"],1],
    ["A probability of 0.25 is equivalent to what percentage?",["2.5%","25%","50%","75%"],1]
  ];
  let triviaQuestions = [], triviaIndex = 0, triviaScore = 0, triviaLocked = false;
  const triviaStart = $("trivia-start"), triviaQuestion = $("trivia-question"), triviaOptions = $("trivia-options"), triviaProgress = $("trivia-progress");
  function mix(list) { const array = [...list]; for (let i=array.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[array[i],array[j]]=[array[j],array[i]];} return array; }
  function showTrivia() {
    const current = triviaQuestions[triviaIndex];
    if (!current) {
      triviaQuestion.textContent = "Round complete: " + triviaScore + " / 5";
      triviaProgress.textContent = triviaScore >= 4 ? "Excellent knowledge!" : "Every round is another opportunity to learn.";
      triviaOptions.replaceChildren(); triviaStart.disabled = false; triviaStart.textContent = "Play another round"; setBest("trivia", triviaScore); $("trivia-best").textContent = "Best score: " + getBest("trivia") + " / 5"; return;
    }
    triviaLocked = false; triviaProgress.textContent = "QUESTION " + (triviaIndex + 1) + " / 5";
    triviaQuestion.textContent = current[0]; triviaOptions.replaceChildren();
    current[1].forEach((answer,index) => {
      const btn = document.createElement("button");btn.type="button";btn.className="option-button";btn.textContent=answer;
      btn.addEventListener("click", () => {
        if(triviaLocked) return;triviaLocked=true;
        if(index===current[2]){triviaScore++;btn.classList.add("correct");}else{btn.classList.add("wrong");}
        Array.from(triviaOptions.children).forEach((option,i)=>{option.disabled=true;if(i===current[2])option.classList.add("correct");});
        setTimeout(()=>{triviaIndex++;showTrivia();},900);
      });
      triviaOptions.append(btn);
    });
  }
  triviaStart.addEventListener("click", () => { triviaQuestions=mix(questionBank).slice(0,5);triviaIndex=0;triviaScore=0;triviaStart.disabled=true;showTrivia(); });
  $("trivia-best").textContent = "Best score: " + getBest("trivia") + " / 5";

  // Forecast journal: local-only, not a public prediction market and not real-money betting.
  const forecastKey = "forecasts";
  let forecasts = safeStorage.get(forecastKey, []);
  if (!Array.isArray(forecasts)) forecasts = [];
  forecasts = forecasts.filter(x => x && typeof x.question==="string" && typeof x.probability==="number").slice(0,100);
  const forecastForm = $("forecast-form"), forecastList = $("forecast-list"), forecastEmpty = $("forecast-empty"), forecastMessage = $("forecast-message");
  const today = new Date(), dateString = [today.getFullYear(),String(today.getMonth()+1).padStart(2,"0"),String(today.getDate()).padStart(2,"0")].join("-");
  $("forecast-date").min = dateString; $("forecast-date").value = dateString;
  $("forecast-probability").addEventListener("input", event => { $("forecast-value").textContent = String(event.target.value) + "%"; });
  function renderForecasts() {
    forecastList.replaceChildren(); $("forecast-total").textContent = String(forecasts.length); forecastEmpty.hidden = forecasts.length>0;
    forecasts.forEach(item => {
      const li=document.createElement("li");li.className="forecast-entry";
      const column=document.createElement("div"),title=document.createElement("strong"),meta=document.createElement("small"),percent=document.createElement("span");
      title.textContent=item.question;meta.textContent=item.category+" · Resolve by "+item.date;percent.textContent=item.probability+"%";
      column.append(title,document.createElement("br"),meta);li.append(column,percent);forecastList.append(li);
    });
  }
  forecastForm.addEventListener("submit", event => {
    event.preventDefault(); const question=$("forecast-question").value.trim(),date=$("forecast-date").value,category=$("forecast-category").value,probability=Number($("forecast-probability").value);
    if(question.length<10 || question.length>240 || date < dateString || !Number.isInteger(probability) || probability<1 || probability>99) { forecastMessage.textContent="Please check the question, date and probability.";return;}
    if(forecasts.length>=100) {forecastMessage.textContent="Maximum 100 local entries. Export and clear before continuing.";return;}
    const record={id: String(Date.now())+"-"+Math.floor(Math.random()*1e6), category,question,date,probability,createdAt:new Date().toISOString()};
    forecasts.unshift(record);
    if(!safeStorage.put(forecastKey,forecasts)){forecasts.shift();forecastMessage.textContent="Browser storage is unavailable. Your entry was not saved.";return;}
    forecastForm.reset();$("forecast-probability").value="50";$("forecast-value").textContent="50%";$("forecast-date").value=dateString;forecastMessage.textContent="Forecast saved on this device.";renderForecasts();
  });
  $("forecast-export").addEventListener("click", () => {
    if (!forecasts.length){forecastMessage.textContent="No saved forecasts to export.";return;}
    const body=JSON.stringify({format:"MOJ_ARENA_FORECAST_JOURNAL_V1",notice:"Non-financial personal forecasts. No wagering.",exportedAt:new Date().toISOString(),entries:forecasts},null,2);
    const url=URL.createObjectURL(new Blob([body],{type:"application/json"}));const a=document.createElement("a");a.href=url;a.download="moj-arena-forecasts.json";document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
    forecastMessage.textContent="Your JSON export has been prepared.";
  });
  $("forecast-clear").addEventListener("click", () => {
    if(!forecasts.length)return;
    if(!window.confirm("Delete all saved forecasts on this device? Export them first if needed."))return;
    if(!safeStorage.remove(forecastKey)){forecastMessage.textContent="Unable to clear local browser storage.";return;}
    forecasts=[];renderForecasts();forecastMessage.textContent="All local forecasts deleted.";
  });
  renderForecasts();

  const marketDetails = {
    us:"State-by-state licenses, authorized operators and geolocation controls are required where applicable. No US real-money product is offered here.",
    uk:"Relevant UK Gambling Commission remote operating permissions would need to be verified. No UK real-money product is offered here.",
    de:"German national and state-specific rules, permitted product scope and licensed access would require verification. No German real-money product is offered here.",
    ch:"Swiss gambling supervision, authorized casino/lottery operators and product permissions require independent verification. No Swiss real-money product is offered here.",
    eu:"European rules differ by country and gambling product. A single EU-wide betting licence cannot be assumed. No real-money product is offered here.",
    other:"Every target jurisdiction requires an independent permission, payments and compliance assessment. No real-money product is offered here."
  };
  $("jurisdiction").addEventListener("change", e => { $("jurisdiction-status").textContent="Real-money wagering is unavailable."; $("jurisdiction-detail").textContent=marketDetails[e.target.value] || marketDetails.other; });
  $("jurisdiction").dispatchEvent(new Event("change"));
  $("compliance-info").addEventListener("click",()=>{ const node=$("compliance-requirements");node.hidden=!node.hidden;$("compliance-info").textContent=node.hidden?"What would unlock this?":"Hide requirements"; });
  $("copyright-year").textContent=String(new Date().getFullYear());

  const translations = {
    safeNotice:"شرط‌بندی واقعی غیرفعال است • بدون واریز • بدون برداشت",
    learnWhy:"علت را بخوانید",
    navExplore:"بخش‌ها",navPlay:"بازی مهارتی",navForecast:"پیش‌بینی رایگان",navPartners:"همکاری تجاری",navLegal:"وضعیت قانونی",backMain:"بازگشت به مج‌پلی‌وین ↗",
    heroEyebrow:"نسل تازه سرگرمی جهانی",heroTitle:"در جهان بازی کن.<br><em>بر لحظه مسلط شو.</em>",heroLead:"یک آرنای جهانی برای مهارت، پیش‌بینی رایگان، استراتژی، خلاقیت و تجربه‌های تعاملی حرفه‌ای. رقابتی سالم و شفاف.",
    startPlaying:"شروع بازی رایگان",openForecasts:"ورود به استودیوی پیش‌بینی",freeToPlay:"بازی مهارتی رایگان",noCash:"بدون شرط پولی",transparent:"قوانین شفاف",
    overlineUniverse:"دنیای سرگرمی",experienceTitle:"یک آرنا؛ دنیاهای متنوع",experienceLead:"گستره‌ای از سرگرمی‌ها و مدل‌های تجاری برای یک پلتفرم بین‌المللی.",
    playOverline:"آزمایشگاه مهارت فعال",playTitle:"بازی واقعی و تعاملی",playLead:"سه چالش مهارتی فعال در مرورگر. بدون هزینه ورود، امتیاز قابل نقدشدن یا جایزه نقدی. رکوردها روی همین دستگاه باقی می‌مانند.",
    forecastTitle:"آینده را تحلیل کن.<br><em>دیدگاهت را ثبت کن.</em>",forecastLead:"برای یک موضوع عمومی یا پروژه شخصی، احتمال وقوع رویدادی را ثبت کن. این دفتر پیش‌بینی رایگان است؛ نه بازار شرط‌بندی و نه وعده جایزه.",
    partnerTitle:"برای سرگرمی ساخته شده؛ برای کسب‌وکار طراحی شده",partnerLead:"مدل درآمدی متنوع برای سازندگان، تبلیغ‌دهندگان، برگزارکنندگان و خریداران محصولات دیجیتال. خدمات پولی فقط پس از فعال شدن واقعی پرداخت و پیشنهاد تجاری عرضه می‌شوند.",
    complianceTitle:"قانونمند در بازارهای لازم؛ شفاف در همه‌جا",complianceLead:"بدون تأیید، ادعای داشتن مجوز شرط‌بندی، قرارداد اپراتوری یا تأیید صلاحیت کشوری نداریم.",
    closingTitle:"کاوش کن. بهتر شو.<br>مسئولانه بازی کن.",closingLead:"توسعه‌ای حرفه‌ای از MojPlayWin برای مخاطبان جهانی و آینده تجاری مسئولانه."
  };
  let lang = safeStorage.get("lang","en") === "fa" ? "fa" : "en";
  const originals = new Map();
  document.querySelectorAll("[data-i18n]").forEach(element=>originals.set(element,element.innerHTML));
  function updateLanguage() {
    document.documentElement.lang=lang;document.documentElement.dir=lang==="fa"?"rtl":"ltr";
    document.querySelectorAll("[data-i18n]").forEach(element=>{
      const key=element.dataset.i18n;
      // Translation HTML comes exclusively from hard-coded trusted strings above.
      element.innerHTML = lang==="fa"&&Object.prototype.hasOwnProperty.call(translations,key)?translations[key]:originals.get(element);
    });
    $("lang-toggle").textContent=lang==="fa"?"EN / FA":"FA / EN";
    $("lang-toggle").setAttribute("aria-label",lang==="fa"?"Switch to English":"تغییر زبان به فارسی");
    safeStorage.put("lang",lang);
  }
  $("lang-toggle").addEventListener("click",()=>{lang=lang==="fa"?"en":"fa";updateLanguage();});
  updateLanguage();
})();
