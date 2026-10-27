(() => {
  "use strict";

  const rubrics = {
    ebook: [
      ["accuracy","Scientific and factual accuracy","Source claims, citation practices and factual correctness",18,true],
      ["sources","Evidence and references","Retrievable sources and separation of evidence from opinion",16,false],
      ["rights","Rights and originality","Ownership, distribution licensing, quotations and originality",16,true],
      ["editing","Editing and coherence","Language, structure, chapter consistency and indexing",10,false],
      ["experience","Reading experience","Navigation, readability and audience suitability",10,false],
      ["accessibility","File standards and access","Navigation, search, alternative text and device compatibility",10,false],
      ["security","File safety and privacy","No malicious payloads or unnecessary personal-data collection",8,true],
      ["delivery","Delivery and support","Complete files, versioning and support responsiveness",12,false]
    ],
    game: [
      ["gameplay","Gameplay and engagement","Goals, balance, depth of mechanics and lasting appeal",19,false],
      ["reliability","Reliability and performance","Error rates, responsiveness, save states and recovery",17,false],
      ["security","Security and privacy","Payments, sessions, minors' data and vulnerabilities",15,true],
      ["rights","Intellectual property","Engine, music, graphic and code licenses",15,true],
      ["accessibility","Accessibility and onboarding","Controls, contrast, tutorials and inclusive access",10,false],
      ["economy","In-game economy and fairness","Balanced rewards, clear costs and abuse prevention",10,false],
      ["compatibility","Device compatibility","Browsers, phones, resolutions and inputs",8,false],
      ["delivery","Release and support","Installation, updates and bug handling",6,false]
    ],
    software: [
      ["functionality","Functional correctness","Requirements coverage, critical flows and reliable outputs",20,true],
      ["security","Technical security","Authentication, authorization, injection, secrets and audit logs",20,true],
      ["reliability","Reliability and speed","Errors, recovery, capacity, latency and observability",15,false],
      ["privacy","Data privacy","Data minimization, retention, deletion, consent and transparency",10,true],
      ["rights","Licensing and compliance","Dependency licenses and commercial usage rights",10,true],
      ["documentation","Testing and documentation","Repeatable tests, user guidance and release notes",10,false],
      ["accessibility","Usability and accessibility","Clear flows, responsiveness and accessible design",8,false],
      ["deployment","Deployment and delivery","Configuration, backups, release practices and support",7,false]
    ],
    media: [
      ["provenance","Provenance and truthful claims","Source attribution and transparent production history",15,false],
      ["creative","Creative and narrative quality","Structure, sound, visuals and execution coherence",15,false],
      ["rights","Licensing and usage rights","Music, images, third-party material and reuse permissions",20,true],
      ["technical","Technical output quality","Resolution, compression, format, color and sound",15,false],
      ["accessibility","Accessibility","Captions, alternative text, legibility and adaptation",10,false],
      ["packaging","Packaging and metadata","Version, companion files, description and labels",10,false],
      ["security","File safety","File integrity, links and user protection",5,true],
      ["utility","Practical value","Fitness for purpose and end-user experience",10,false]
    ]
  };
  const typeLabels = {ebook:"E-books & scientific content",game:"Games & interactive experiences",software:"Software & web services",media:"Media & digital assets"};
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
      toggle.setAttribute("aria-label", opened ? "Open menu" : "Close menu");
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
        select.setAttribute("aria-label",`Score for ${label}`);
        [["","Not rated"],["0","0 - Fail"],["1","1 - Poor"],["2","2 - Insufficient"],["3","3 - Acceptable"],["4","4 - Good"],["5","5 - Excellent"]].forEach(([value,label])=>{
          const option=document.createElement("option");option.value=value;option.textContent=label;select.append(option);
        });
        select.value=saved[index]?.score ?? "";
        const evidence=document.createElement("input");evidence.type="text";evidence.className="criterion-evidence";evidence.dataset.evidence=id;
        evidence.maxLength=450;evidence.placeholder="Evidence, test finding or reference (at least 12 characters)";
        evidence.setAttribute("aria-label",`Evidence for ${label}`);
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
      let grade="Awaiting documented evidence";
      if(complete){grade=failedGates.length?"Critical issue requires resolution":weightedScore>=90?"Excellent · preliminary":weightedScore>=80?"Strong · preliminary":weightedScore>=70?"Acceptable with improvements":"Further review required";}
      return {ratings,completeCount,complete,weightedScore,failedGates,grade};
    }
    function update() {
      currentResult=calculate();
      const result=currentResult;
      el("coverageValue").textContent=`${result.completeCount} / 8`;
      el("coverageBar").style.width=`${result.completeCount*12.5}%`;
      el("scoreValue").textContent=result.complete?String(result.weightedScore).replace(".","."):"—";
      el("gaugeProgress").style.strokeDashoffset=String(565.486*(1-(result.complete?result.weightedScore:0)/100));
      el("resultLevel").textContent=result.grade;
      const alert=el("resultAlert");
      alert.classList.toggle("danger",result.complete&&result.failedGates.length>0);
      alert.classList.toggle("success",result.complete&&result.failedGates.length===0);
      const p=alert.querySelector("p");
      if(result.complete&&result.failedGates.length) p.textContent=`Critical gate failed: ${result.failedGates.map(x=>x.label).join(", ")}. A high average cannot authorize certification.`;
      else if(result.complete) p.textContent="Preliminary assessment complete. Results reflect only your inputs, not an independently verified judgment.";
      else p.textContent="Enter the product name, eight criterion scores and supporting evidence to calculate a preliminary result.";
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
      toast("Preliminary report downloaded with a file integrity checksum.");
    }
    function printReport() {
      const report=buildReport();if(!report)return;
      document.querySelectorAll(".print-sheet").forEach(x=>x.remove());
      const sheet=document.createElement("div");sheet.className="print-sheet";
      const heading=document.createElement("h1");heading.textContent="AYAR | Preliminary Digital Product Assessment";
      const disclaimer=document.createElement("div");disclaimer.className="watermark";disclaimer.textContent="USER-GENERATED PRELIMINARY REPORT — NOT INDEPENDENTLY CERTIFIED";
      const meta=document.createElement("p");meta.textContent=`Product: ${report.product.name} | Version: ${report.product.version||"Not provided"} | Category: ${report.product.typeLabel} | Date: ${new Date(report.generatedAt).toLocaleString("en-GB")}`;
      const score=document.createElement("h2");score.textContent=`Weighted score: ${report.weightedScore} / 100 — ${report.grade}`;
      const table=document.createElement("table"),thead=document.createElement("thead"),tr=document.createElement("tr");
      ["Criterion","Weight","Score / 5","Recorded evidence"].forEach(text=>{const th=document.createElement("th");th.textContent=text;tr.append(th);});thead.append(tr);table.append(thead);
      const tbody=document.createElement("tbody");
      report.findings.forEach(f=>{const row=document.createElement("tr");[f.label,`${f.weight}%`,String(f.score),f.evidence].forEach(text=>{const td=document.createElement("td");td.textContent=text;row.append(td);});tbody.append(row);});table.append(tbody);
      const notes=document.createElement("p");notes.textContent=`Scope and limitations: ${report.scopeNotes||"Not provided"}`;
      const foot=document.createElement("p");foot.className="foot";foot.textContent="This user-generated report has not independently verified the underlying evidence. Formal certification requires qualified expert review and conflict-of-interest disclosure.";
      sheet.append(heading,disclaimer,meta,score,table,notes,foot);document.body.append(sheet);
      window.print();
    }
    el("productType").addEventListener("change",e=>{remember();currentType=e.target.value;renderCriteria();});
    el("productName").addEventListener("input",update);
    el("downloadReport").addEventListener("click",()=>downloadReport().catch(()=>toast("Report generation failed. Please try again.")));
    el("printReport").addEventListener("click",printReport);
    el("resetForm").addEventListener("click",()=>{
      if(!confirm("Clear all information in this assessment form?"))return;
      for(const key of Object.keys(state))delete state[key];
      ["productName","productVersion","scopeNotes"].forEach(id=>el(id).value="");
      el("productType").value="ebook";currentType="ebook";renderCriteria();toast("Assessment cleared.");
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
      if(file.size>1024*1024){result.textContent="File exceeds the 1 MB limit; verification was not performed.";return;}
      try {
        const obj=JSON.parse(await file.text());
        if(obj.assessment?.schema!=="AYAR-PREASSESSMENT-v1"||obj.integrity?.algorithm!=="SHA-256"||!obj.integrity.digest){throw new Error("FORMAT");}
        const actual=await sha256(JSON.stringify(obj.assessment));
        result.textContent=actual===obj.integrity.digest?
          "Report structure and checksum match. This proves file consistency only; it does not authenticate the issuer or verify reviewer independence.":
          "Warning: the checksum does not match. The file may have been modified or corrupted.";
      }catch{result.textContent="Invalid file structure or unsupported AYAR report format.";}
      input.value="";
    });
  }
  setupNavigation();setupAuditDesk();setupIntegrityVerification();
})();
