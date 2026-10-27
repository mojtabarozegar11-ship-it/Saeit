(() => {
  "use strict";

  const rubrics = {
    ebook: [
      ["accuracy","صحت علمی و محتوایی","کنترل ادعاها، روش استناد و درستی اطلاعات",18,true],
      ["sources","منابع و قابلیت راستی‌آزمایی","ارجاعات قابل بازیابی و تفکیک شواهد از تفسیر",16,false],
      ["rights","حقوق اثر و اصالت","مالکیت، مجوز انتشار، نقل‌قول و اصالت محتوا",16,true],
      ["editing","ویرایش و انسجام","زبان، سازمان‌دهی، پیوستگی فصل‌ها و نمایه",10,false],
      ["experience","تجربه مطالعه","ناوبری، خوانایی و تناسب با مخاطب",10,false],
      ["accessibility","استاندارد فایل و دسترس‌پذیری","فهرست، جست‌وجو، متن جایگزین و سازگاری",10,false],
      ["security","ایمنی فایل و حریم خصوصی","پرهیز از محتوای مخرب و گردآوری داده بی‌دلیل",8,true],
      ["delivery","تحویل و پشتیبانی","کامل‌بودن فایل، نسخه‌بندی و پاسخ‌گویی",12,false]
    ],
    game: [
      ["gameplay","کیفیت تجربه و گیم‌پلی","هدف، تعادل، عمق مکانیک‌ها و جذابیت پایدار",19,false],
      ["reliability","پایداری و کارایی","نرخ خطا، پاسخ‌گویی، ذخیره و بازیابی",17,false],
      ["security","امنیت و حریم خصوصی","پرداخت، نشست، داده کودک و آسیب‌پذیری‌ها",15,true],
      ["rights","حقوق مالکیت و دارایی‌ها","مجوز موتور، موسیقی، گرافیک و کد",15,true],
      ["accessibility","دسترس‌پذیری و هدایت کاربر","کنترل‌ها، کنتراست، آموزش و دسترسی",10,false],
      ["economy","اقتصاد و انصاف بازی","تعادل جوایز، شفافیت هزینه و ضدسوءاستفاده",10,false],
      ["compatibility","سازگاری دستگاه‌ها","مرورگر، موبایل، وضوح تصویر و ورودی‌ها",8,false],
      ["delivery","انتشار و پشتیبانی","نصب، به‌روزرسانی و رسیدگی به ایراد",6,false]
    ],
    software: [
      ["functionality","صحت عملکرد","پوشش نیازمندی‌ها، سناریوهای بحرانی و خروجی درست",20,true],
      ["security","امنیت فنی","احراز هویت، مجوزها، تزریق، ذخیره اسرار و ثبت رخداد",20,true],
      ["reliability","قابلیت اطمینان و کارایی","خطا، بازیابی، ظرفیت، کارایی و مشاهده‌پذیری",15,false],
      ["privacy","حریم خصوصی داده","حداقل‌سازی داده، حفظ و حذف، رضایت و شفافیت",10,true],
      ["rights","مجوزها و انطباق حقوقی","مجوز وابستگی‌ها و حق بهره‌برداری تجاری",10,true],
      ["documentation","آزمون و مستندات","آزمون‌های تکرارپذیر، راهنما و تغییرات نسخه",10,false],
      ["accessibility","تجربه کاربری و دسترس‌پذیری","وضوح جریان، پاسخ‌گویی و استانداردهای دسترسی",8,false],
      ["deployment","استقرار و تحویل","پیکربندی، پشتیبان، انتشار و پشتیبانی",7,false]
    ],
    media: [
      ["provenance","اصالت و صحت ادعا","منبع، نسبت‌دادن محتوا و شفافیت تولید",15,false],
      ["creative","کیفیت هنری و روایی","ساختار، صدا، تصویر و انسجام اجرایی",15,false],
      ["rights","مجوز و حقوق بهره‌برداری","موسیقی، تصویر، آثار ثالث و اجازه استفاده",20,true],
      ["technical","کیفیت فنی خروجی","وضوح، فشرده‌سازی، فرمت، رنگ و صدا",15,false],
      ["accessibility","دسترس‌پذیری","زیرنویس، متن جایگزین، خوانایی و تطبیق",10,false],
      ["packaging","بسته‌بندی و فراداده","نسخه، فایل‌های همراه، شرح و برچسب‌گذاری",10,false],
      ["security","ایمنی فایل","سلامت فایل، لینک‌ها و حفاظت از مخاطب",5,true],
      ["utility","ارزش کاربردی و مصرف","تناسب با هدف و تجربه استفاده نهایی",10,false]
    ]
  };
  const typeLabels = {ebook:"کتاب الکترونیکی و محتوای علمی",game:"بازی و تجربه تعاملی",software:"نرم‌افزار و خدمات وب",media:"رسانه و دارایی دیجیتال"};
  const el = id => document.getElementById(id);
  const SHA256_K = [
    0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
    0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
    0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
    0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
    0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
    0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
    0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
    0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
  ];
  function sha256Portable(input) {
    const bytes=new TextEncoder().encode(input);
    const padded=new Uint8Array(Math.ceil((bytes.length+9)/64)*64);
    padded.set(bytes);padded[bytes.length]=0x80;
    const view=new DataView(padded.buffer);
    const bitLength=bytes.length*8;
    view.setUint32(padded.length-8,Math.floor(bitLength/0x100000000));
    view.setUint32(padded.length-4,bitLength>>>0);
    const h=[0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19];
    const rotate=(x,n)=>(x>>>n)|(x<<(32-n));
    for(let offset=0;offset<padded.length;offset+=64) {
      const w=new Uint32Array(64);
      for(let i=0;i<16;i++)w[i]=view.getUint32(offset+i*4);
      for(let i=16;i<64;i++){
        const a=w[i-15],b=w[i-2];
        const s0=rotate(a,7)^rotate(a,18)^(a>>>3);
        const s1=rotate(b,17)^rotate(b,19)^(b>>>10);
        w[i]=(w[i-16]+s0+w[i-7]+s1)>>>0;
      }
      let [a,b,c,d,e,f,g,hh]=h;
      for(let i=0;i<64;i++){
        const s1=rotate(e,6)^rotate(e,11)^rotate(e,25);
        const ch=(e&f)^(~e&g);
        const t1=(hh+s1+ch+SHA256_K[i]+w[i])>>>0;
        const s0=rotate(a,2)^rotate(a,13)^rotate(a,22);
        const maj=(a&b)^(a&c)^(b&c);
        const t2=(s0+maj)>>>0;
        hh=g;g=f;f=e;e=(d+t1)>>>0;d=c;c=b;b=a;a=(t1+t2)>>>0;
      }
      [a,b,c,d,e,f,g,hh].forEach((value,i)=>{h[i]=(h[i]+value)>>>0;});
    }
    return h.map(value=>value.toString(16).padStart(8,"0")).join("");
  }
  async function sha256(input) {
    if(globalThis.crypto?.subtle) {
      const hash=await globalThis.crypto.subtle.digest("SHA-256",new TextEncoder().encode(input));
      return Array.from(new Uint8Array(hash)).map(n=>n.toString(16).padStart(2,"0")).join("");
    }
    return sha256Portable(input);
  }
  let toastTimer;
  function toast(message) {
    const target = el("toast"); if (!target) return;
    target.textContent = message; target.classList.add("show");
    clearTimeout(toastTimer); toastTimer = setTimeout(() => target.classList.remove("show"), 4500);
  }
  function setupNavigation() {
    const toggle = el("menuToggle"), nav = el("mobileNav");
    if (!toggle || !nav) return;
    toggle.addEventListener("click", () => {
      const opened = toggle.getAttribute("aria-expanded") === "true";
      toggle.setAttribute("aria-expanded", String(!opened));
      toggle.setAttribute("aria-label", opened ? "باز کردن فهرست" : "بستن فهرست");
      nav.hidden = opened;
    });
    nav.querySelectorAll("a").forEach(a => a.addEventListener("click", () => {
      nav.hidden = true; toggle.setAttribute("aria-expanded","false");
    }));
    document.addEventListener("keydown", e => {if(e.key === "Escape"){nav.hidden=true;toggle.setAttribute("aria-expanded","false");}});
    el("year").textContent = new Date().getFullYear();
  }

  function setupAuditDesk() {
    if (!el("criteriaList")) return;
    const state = {};
    let currentType = "ebook";
    let currentResult = null;
    const list = el("criteriaList");
    function remember() {
      state[currentType] = rubrics[currentType].map(([id]) => ({
        score:list.querySelector(`[data-score="${id}"]`)?.value || "",
        evidence:list.querySelector(`[data-evidence="${id}"]`)?.value || ""
      }));
    }
    function renderCriteria() {
      const saved = state[currentType] || [];
      list.replaceChildren();
      rubrics[currentType].forEach(([id,label,description,weight,gate],index) => {
        const wrapper = document.createElement("div");
        wrapper.className = "criterion";
        const left = document.createElement("div");
        const main = document.createElement("div"); main.className = "criterion-main";
        const code = document.createElement("span");code.className="criterion-code";code.textContent=String(index+1).padStart(2,"0");
        const name = document.createElement("span");name.className="criterion-label";name.textContent=label;
        const weightLabel = document.createElement("span");weightLabel.className="criterion-weight";weightLabel.textContent=`${weight}%${gate?" ◆":""}`;
        main.append(code,name,weightLabel);
        const desc = document.createElement("p");desc.className="criterion-desc";desc.textContent=description;
        left.append(main,desc);
        const select = document.createElement("select");select.className="criterion-select";select.dataset.score=id;
        select.setAttribute("aria-label",`امتیاز ${label}`);
        [["","ارزیابی نشده"],["0","۰ - مردود"],["1","۱ - ضعیف"],["2","۲ - ناکافی"],["3","۳ - قابل قبول"],["4","۴ - خوب"],["5","۵ - عالی"]].forEach(([value,label])=>{
          const option=document.createElement("option");option.value=value;option.textContent=label;select.append(option);
        });
        select.value=saved[index]?.score ?? "";
        const evidence=document.createElement("input");evidence.type="text";evidence.className="criterion-evidence";evidence.dataset.evidence=id;
        evidence.maxLength=450;evidence.placeholder="شاهد، نتیجه آزمون یا مرجع بررسی را بنویسید (حداقل ۱۲ نویسه)";
        evidence.setAttribute("aria-label",`شاهد ${label}`);
        evidence.value=saved[index]?.evidence ?? "";
        select.addEventListener("change",update);
        evidence.addEventListener("input",update);
        wrapper.append(left,select,evidence);list.append(wrapper);
      });
      update();
    }
    function calculate() {
      const ratings=rubrics[currentType].map(([id,label,description,weight,gate])=>{
        const scoreText=list.querySelector(`[data-score="${id}"]`).value;
        const evidence=list.querySelector(`[data-evidence="${id}"]`).value.trim();
        const score=scoreText===""?null:Number(scoreText);
        return {id,label,description,weight,criticalGate:gate,score,evidence,complete:score!==null && evidence.length>=12};
      });
      const completeCount=ratings.filter(x=>x.complete).length;
      const complete=completeCount===ratings.length && el("productName").value.trim().length>=2;
      const weightedScore=complete?Math.round(ratings.reduce((sum,x)=>sum+x.weight*x.score/5,0)*10)/10:null;
      const failedGates=complete?ratings.filter(x=>x.criticalGate&&x.score<3):[];
      let grade="در انتظار تکمیل شواهد";
      if(complete){grade=failedGates.length?"نیازمند رفع مانع حیاتی":weightedScore>=90?"ممتاز · پیش‌ارزیابی":weightedScore>=80?"قوی · پیش‌ارزیابی":weightedScore>=70?"قابل قبول با اصلاحات":"نیازمند بازنگری";}
      return {ratings,completeCount,complete,weightedScore,failedGates,grade};
    }
    function update() {
      currentResult=calculate();
      const result=currentResult;
      el("coverageValue").textContent=`${result.completeCount} / ۸`;
      el("coverageBar").style.width=`${result.completeCount*12.5}%`;
      el("scoreValue").textContent=result.complete?String(result.weightedScore).replace(".","."):"—";
      el("gaugeProgress").style.strokeDashoffset=String(565.486*(1-(result.complete?result.weightedScore:0)/100));
      el("resultLevel").textContent=result.grade;
      const alert=el("resultAlert");
      alert.classList.toggle("danger",result.complete&&result.failedGates.length>0);
      alert.classList.toggle("success",result.complete&&result.failedGates.length===0);
      const p=alert.querySelector("p");
      if(result.complete&&result.failedGates.length) p.textContent=`مانع حیاتی در ${result.failedGates.map(x=>x.label).join("، ")} ثبت شده است. امتیاز کلی مجوز تأیید محصول نیست.`;
      else if(result.complete) p.textContent="پیش‌ارزیابی تکمیل شد؛ نتیجه تنها بر اساس داده‌های واردشده است و به معنی تأیید مستقل نیست.";
      else p.textContent="برای محاسبه امتیاز، نام محصول، امتیاز هر هشت معیار و شاهد مرتبط با هر معیار را تکمیل کنید.";
      el("resultSub")?.remove();
      el("downloadReport").disabled=!result.complete;
      el("printReport").disabled=!result.complete;
    }
    function buildReport() {
      if(!currentResult?.complete) return null;
      return {
        schema:"AYAR-PREASSESSMENT-v1",
        issuer:"Browser-local self-assessment; NOT an independent certificate",
        generatedAt:new Date().toISOString(),
        product:{name:el("productName").value.trim(),version:el("productVersion").value.trim(),type:currentType,typeLabel:typeLabels[currentType]},
        methodology:{rubricVersion:"2026.1",scoring:"Sum of (criterion score / 5 × weight); eight weighted criteria; pass/fail critical gates"},
        findings:currentResult.ratings.map(({complete,...rest})=>rest),
        weightedScore:currentResult.weightedScore,
        grade:currentResult.grade,
        criticalGatesFailed:currentResult.failedGates.map(x=>x.id),
        scopeNotes:el("scopeNotes").value.trim(),
        disclaimer:"Self-reported preliminary output, not verified by AYAR, MojPlayWin or an independent professional. SHA-256 checksum verifies file consistency only, not authorship or official endorsement."
      };
    }
    async function downloadReport() {
      const report=buildReport();if(!report)return;
      const digest=await sha256(JSON.stringify(report));
      const data={assessment:report,integrity:{algorithm:"SHA-256",digest,meaning:"file integrity only; no authenticity endorsement"}};
      const blob=new Blob([JSON.stringify(data,null,2)],{type:"application/json;charset=utf-8"});
      const url=URL.createObjectURL(blob),a=document.createElement("a");
      a.href=url;a.download=`ayar-preassessment-${new Date().toISOString().slice(0,10)}.json`;
      document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1200);
      toast("گزارش مقدماتی با اثرانگشت فایل دانلود شد.");
    }
    function printReport() {
      const report=buildReport();if(!report)return;
      document.querySelectorAll(".print-sheet").forEach(x=>x.remove());
      const sheet=document.createElement("div");sheet.className="print-sheet";
      const heading=document.createElement("h1");heading.textContent="عـیـار | گزارش پیش‌ارزیابی دیجیتال";
      const disclaimer=document.createElement("div");disclaimer.className="watermark";disclaimer.textContent="خودارزیابی مقدماتی — فاقد تأیید و امضای کارشناس مستقل";
      const meta=document.createElement("p");meta.textContent=`محصول: ${report.product.name} | نسخه: ${report.product.version||"ثبت نشده"} | گروه: ${report.product.typeLabel} | تاریخ: ${new Date(report.generatedAt).toLocaleString("fa-IR")}`;
      const score=document.createElement("h2");score.textContent=`امتیاز وزنی: ${report.weightedScore} از ۱۰۰ — ${report.grade}`;
      const table=document.createElement("table"),thead=document.createElement("thead"),tr=document.createElement("tr");
      ["محور","وزن","امتیاز / ۵","شاهد ثبت‌شده"].forEach(text=>{const th=document.createElement("th");th.textContent=text;tr.append(th);});thead.append(tr);table.append(thead);
      const tbody=document.createElement("tbody");
      report.findings.forEach(f=>{const row=document.createElement("tr");[f.label,`${f.weight}%`,String(f.score),f.evidence].forEach(text=>{const td=document.createElement("td");td.textContent=text;row.append(td);});tbody.append(row);});table.append(tbody);
      const notes=document.createElement("p");notes.textContent=`محدوده و محدودیت: ${report.scopeNotes||"ثبت نشده"}`;
      const foot=document.createElement("p");foot.className="foot";foot.textContent="این فرم با داده‌های واردشده توسط کاربر تولید شده و شواهد آن مستقلاً راستی‌آزمایی نشده‌اند. برای گواهی رسمی، بررسی کارشناسی واقعی و افشای تضاد منافع لازم است.";
      sheet.append(heading,disclaimer,meta,score,table,notes,foot);document.body.append(sheet);
      window.print();
    }
    el("productType").addEventListener("change",e=>{remember();currentType=e.target.value;renderCriteria();});
    el("productName").addEventListener("input",update);
    el("downloadReport").addEventListener("click",()=>downloadReport().catch(()=>toast("خطا در تهیه گزارش؛ دوباره تلاش کنید.")));
    el("printReport").addEventListener("click",printReport);
    el("resetForm").addEventListener("click",()=>{
      if(!confirm("تمام اطلاعات این فرم در این صفحه پاک شود؟"))return;
      for(const key of Object.keys(state))delete state[key];
      ["productName","productVersion","scopeNotes"].forEach(id=>el(id).value="");
      el("productType").value="ebook";currentType="ebook";renderCriteria();toast("فرم پاک شد.");
    });
    document.querySelectorAll("[data-type]").forEach(link=>link.addEventListener("click",()=>{
      if(link.dataset.type===currentType)return;
      remember();currentType=link.dataset.type;el("productType").value=currentType;renderCriteria();
    }));
    renderCriteria();
  }
  async function setupIntegrityVerification() {
    const input=el("verifyFile");if(!input)return;
    const result=el("verifyResult");
    input.addEventListener("change",async()=>{
      const file=input.files?.[0];if(!file)return;
      if(file.size>1024*1024){result.textContent="فایل بیش از ۱ مگابایت است؛ بررسی انجام نشد.";return;}
      try {
        const obj=JSON.parse(await file.text());
        if(obj.assessment?.schema!=="AYAR-PREASSESSMENT-v1"||obj.integrity?.algorithm!=="SHA-256"||!obj.integrity.digest){throw new Error("FORMAT");}
        const actual=await sha256(JSON.stringify(obj.assessment));
        result.textContent=actual===obj.integrity.digest?
          "ساختار و اثرانگشت فایل مطابقت دارند. این فقط کنترل یکپارچگی فایل است؛ اصالت صادرکننده یا استقلال کارشناس را تأیید نمی‌کند.":
          "هشدار: اثرانگشت با داده‌های فایل مطابقت ندارد؛ فایل ممکن است تغییر کرده یا آسیب دیده باشد.";
      }catch{result.textContent="ساختار فایل معتبر نیست یا از قالب گزارش عیار پشتیبانی نمی‌شود.";}
      input.value="";
    });
  }
  setupNavigation();setupAuditDesk();setupIntegrityVerification();
})();
