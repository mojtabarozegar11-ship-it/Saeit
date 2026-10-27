(() => {
  "use strict";
  const $ = id => document.getElementById(id);
  const page = document.body.dataset.page || "";
  const link = "./";
  let csrf = "";
  const rubric = {
    ebook: [["accuracy","Scientific accuracy"],["sources","Sources and references"],["rights","Rights and originality"],["editing","Editing and coherence"],["experience","Reading experience"],["accessibility","Accessible file standards"],["security","File safety and privacy"],["delivery","Delivery and support"]],
    game: [["gameplay","Gameplay and engagement"],["reliability","Reliability"],["security","Security and privacy"],["rights","Intellectual property"],["accessibility","Accessibility"],["economy","Fair economy"],["compatibility","Device compatibility"],["delivery","Release and support"]],
    software: [["functionality","Functional correctness"],["security","Technical security"],["reliability","Reliability"],["privacy","Data privacy"],["rights","Licensing"],["documentation","Testing and documentation"],["accessibility","Accessible user experience"],["deployment","Deployment"]],
    media: [["provenance","Provenance"],["creative","Creative quality"],["rights","Licensing"],["technical","Technical output"],["accessibility","Accessibility"],["packaging","Packaging and metadata"],["security","File safety"],["utility","Practical value"]]
  };
  function h(tag, content="", className="") {
    const e = document.createElement(tag);
    if(className) e.className = className;
    e.textContent = content;
    return e;
  }
  function clear(e) { e?.replaceChildren(); return e; }
  function message(text, kind="") {
    const target = $("feedback");
    if(!target) return;
    target.textContent = text;
    target.className = "a-alert " + kind;
    target.hidden = false;
    target.scrollIntoView({block:"nearest",behavior:"smooth"});
  }
  function nav() {
    const header = $("platformHeader");
    if(header) {
      header.innerHTML = `<header class="a-header"><div class="a-shell a-top"><a class="a-logo" href="./index.html" aria-label="AYAR home">A<span>Y</span>AR.</a><button type="button" class="a-menu" id="platformMenu" aria-label="Toggle navigation" aria-expanded="false">Menu</button><nav class="a-nav" id="platformNav" aria-label="AYAR navigation"><a href="./index.html">Overview</a><a href="./services.html" data-nav="services">Services</a><a href="./submit.html" data-nav="submit">Submit product</a><a href="./track.html" data-nav="track">Track case</a><a href="./registry.html" data-nav="registry">Public reports</a><a href="./methodology.html">Methodology</a><a href="./reviewer.html" data-nav="reviewer">Review desk</a></nav></div></header>`;
      const menu = $("platformMenu"), links = $("platformNav");
      menu?.addEventListener("click",()=>{
        const opened=links.classList.toggle("open");
        menu.setAttribute("aria-expanded",String(opened));
      });
      header.querySelectorAll("[data-nav]").forEach(a=>{
        if(a.dataset.nav===page)a.setAttribute("aria-current","page");
      });
    }
    const footer = $("platformFooter");
    if(footer) {
      footer.innerHTML = `<footer class="a-footer"><div class="a-shell a-footer-inner"><span>© <span id="platformYear"></span> AYAR · A MOJPLAYWIN INITIATIVE</span><span><a href="./privacy.html">Privacy & evidence policy</a> · <a href="./methodology.html">Review charter</a> · <a href="https://mojplaywin.com/">MojPlayWin</a></span><span>Evidence first. No unsupported accreditation claims.</span></div></footer>`;
      $("platformYear").textContent=String(new Date().getFullYear());
    }
  }
  async function request(action, body={}, attachments=null) {
    if(!csrf) {
      const config = await fetch("./api?op=config",{credentials:"same-origin",cache:"no-store"});
      const response = await config.json();
      if(!config.ok || !response.ok) throw Error("AYAR case service is unavailable");
      csrf = response.csrf_token;
    }
    let options = {method:"POST",credentials:"same-origin",cache:"no-store",headers:{"X-CSRFToken":csrf}};
    if(attachments) {
      const data = new FormData();
      data.append("payload",JSON.stringify({action,...body}));
      for(const file of attachments)data.append("files",file,file.name);
      options.body=data;
    } else {
      options.headers["Content-Type"]="application/json";
      options.body=JSON.stringify({action,...body});
    }
    const response=await fetch("./api",options);
    let result;
    try { result = await response.json(); } catch { throw Error("Unexpected server response"); }
    if(!response.ok || !result.ok)throw Error(result.error||"Request failed");
    return result.data;
  }
  async function publicGet(op) {
    const response=await fetch("./api?op="+encodeURIComponent(op),{credentials:"same-origin",cache:"no-store"});
    const data=await response.json();
    if(!response.ok || !data.ok)throw Error(data.error||"Service unavailable");
    return data;
  }
  function field(form,name){return form.elements.namedItem(name);}
  function collectCase(form) {
    return {
      category:field(form,"category").value,
      service:field(form,"service").value,
      product_name:field(form,"product_name").value,
      product_version:field(form,"product_version").value,
      product_url:field(form,"product_url").value,
      email:field(form,"email").value,
      scope:field(form,"scope").value,
      evidence_summary:field(form,"evidence_summary").value,
      rights_declared:field(form,"rights_declared").checked,
      privacy_consent:field(form,"privacy_consent").checked,
      publication_consent:field(form,"publication_consent").checked
    };
  }
  function setupSubmission() {
    const form=$("intakeForm");
    if(!form)return;
    const params=new URLSearchParams(location.search);
    const s=params.get("service");
    if(["screening","professional","enterprise"].includes(s))field(form,"service").value=s;
    form.addEventListener("submit",async event=>{
      event.preventDefault();
      const submit=$("submitCase");
      const files=Array.from(field(form,"files").files||[]);
      const total=files.reduce((sum,f)=>sum+f.size,0);
      if(files.length>3 || files.some(f=>f.size>4*1024*1024) || total>10*1024*1024){
        message("Up to three PDF, PNG, JPG or TXT files are accepted (maximum 4 MB each).","error");return;
      }
      submit.disabled=true;submit.textContent="Submitting securely…";
      try {
        const result=await request("submit",{case:collectCase(form)},files);
        $("receiptCase").textContent=result.case_id;
        $("receiptKey").textContent=result.access_key;
        $("receipt").classList.add("show");
        $("receipt").scrollIntoView({behavior:"smooth",block:"center"});
        form.reset();
        $("feedback").hidden=true;
      } catch(error){message(error.message,"error");}
      finally {submit.disabled=false;submit.textContent="Submit dossier securely ↗";}
    });
    $("copyReceipt")?.addEventListener("click",async()=>{
      const text=`AYAR case: ${$("receiptCase").textContent}\nPrivate access key: ${$("receiptKey").textContent}\nTrack at: https://mojplaywin.com/ayaar/track.html`;
      try { await navigator.clipboard.writeText(text);$("copyReceipt").textContent="Copied securely ✓"; }
      catch { message("Copy was blocked by the browser. Please save the case number and access key.","error"); }
    });
  }
  function addFact(parent,label,value) {
    const box=h("div","","a-fact");
    box.append(h("small",label),h("strong",String(value||"Not provided")));
    parent.append(box);
  }
  function renderReport(container,report) {
    if(!report)return;
    const title=h("h3","Reviewer-attested assessment — not official certification");
    const details=h("div","","a-facts");
    addFact(details,"Reviewer account",report.reviewer_account);
    addFact(details,"Preliminary grade",report.grade);
    addFact(details,"Weighted score",report.score+" / 100");
    addFact(details,"Reviewed at",report.reviewed_at);
    container.append(title,details,h("p",report.notice,"a-small"));
    const table=h("table","","a-table"),head=h("tr");
    ["Criterion","Weight","Score","Reviewer evidence"].forEach(v=>head.append(h("th",v)));
    table.append(head);
    for(const item of report.criteria){
      const tr=h("tr");
      [item.criterion,item.weight+"%",item.score+" / 5",item.evidence].forEach(v=>tr.append(h("td",String(v))));
      table.append(tr);
    }
    const wrap=h("div","","a-table-wrap");wrap.append(table);container.append(wrap);
    container.append(h("p","Independence statement: "+report.independence_statement,"a-small"));
    container.append(h("p","Scope: "+report.review_scope,"a-small"));
    container.append(h("p",report.final_disclaimer,"a-small"));
  }
  function downloadCaseReport(details) {
    const exportData={
      schema:"AYAR-PRIVATE-REVIEW-EXPORT-v1",
      exported_at:new Date().toISOString(),
      case_id:details.case_id, product_name:details.product_name,
      product_version:details.product_version, category:details.category,
      case_history:details.events, review:details.review,
      notice:"Reviewer-attested assessment only; not accredited or independently certified. This downloaded JSON is not cryptographically signed."
    };
    const url=URL.createObjectURL(new Blob([JSON.stringify(exportData,null,2)],{type:"application/json"}));
    const anchor=document.createElement("a");anchor.href=url;
    anchor.download="AYAR-"+details.case_id+"-assessment.json";
    document.body.append(anchor);anchor.click();anchor.remove();
    setTimeout(()=>URL.revokeObjectURL(url),3000);
  }
  function addApplicantFollowup(target,details) {
    if(target.id!=="casePanel" || details.status!=="needs_information")return;
    const section=h("section","","a-followup");
    section.append(h("small","APPLICANT RESPONSE / REQUESTED INFORMATION","a-overline"));
    section.append(h("h3","Respond to the review team"));
    section.append(h("p","A reviewer requested more information. Your response becomes part of this case's permanent event history. You may attach up to three additional evidence files.","a-small"));
    const form=h("form","","a-followup-form");
    const label=h("label","Your response and evidence references *");label.htmlFor="followupNote";
    const note=h("textarea");note.id="followupNote";note.required=true;
    note.minLength=12;note.maxLength=2000;
    note.placeholder="Answer the staff question and describe exactly what has changed (12 characters minimum)…";
    const fileLabel=h("label","Additional PDF, PNG, JPG or TXT files (optional)");fileLabel.htmlFor="followupFiles";
    const files=document.createElement("input");files.type="file";files.id="followupFiles";
    files.multiple=true;files.accept=".pdf,.png,.jpg,.jpeg,.txt";
    const button=h("button","Send follow-up securely ↗","a-button");button.type="submit";
    form.append(label,note,fileLabel,files,button);section.append(form);target.append(section);
    form.addEventListener("submit",async event=>{
      event.preventDefault();
      const extra=Array.from(files.files||[]);
      if(extra.length>3 || extra.some(f=>f.size>4*1024*1024) || extra.reduce((n,f)=>n+f.size,0)>10*1024*1024){
        message("Maximum three files, up to 4 MB each and 10 MB total.","error");return;
      }
      const credentials=$("trackForm");button.disabled=true;
      try {
        const args={case_id:field(credentials,"case_id").value,
          access_key:field(credentials,"access_key").value,note:note.value};
        await request("reply",args,extra);
        const updated=await request("status",{case_id:args.case_id,access_key:args.access_key});
        renderCase(target,updated);
        message("Your additional evidence was received and the case returned to the review queue.","success");
      }catch(error){message(error.message,"error");}
      finally{button.disabled=false;}
    });
  }
  function renderCase(target,details) {
    clear(target);
    target.append(h("h2",details.product_name));
    const status=h("span",details.status.replaceAll("_"," "),"a-status "+details.status);
    target.append(status);
    const facts=h("div","","a-facts");
    addFact(facts,"Case reference",details.case_id);
    addFact(facts,"Product category",details.category);
    addFact(facts,"Review service",details.service);
    addFact(facts,"Created",details.created_at);
    addFact(facts,"Version",details.product_version);
    addFact(facts,"Evidence attachments",details.files.length);
    target.append(facts);
    target.append(h("h3","Recorded scope"));
    target.append(h("p",details.scope||"Not provided"));
    if(details.files.length){
      target.append(h("h3","Evidence inventory"));
      const list=h("ul","","a-evidence-list");
      for(const f of details.files)list.append(h("li",f.original_name+" · "+Math.ceil(f.size/1024)+" KB · SHA-256 "+f.sha256));
      target.append(list);
    }
    if(details.review){
      renderReport(target,details.review);
      const exportButton=h("button","Download documented review (JSON) ↓","a-button a-button-secondary");
      exportButton.type="button";exportButton.addEventListener("click",()=>downloadCaseReport(details));
      target.append(exportButton);
    }
    target.append(h("h3","Case history"));
    for(const event of details.events){
      const div=h("div","","a-event");
      div.append(h("small",event.occurred_at),h("strong",event.action.replaceAll("_"," ")),h("div",event.detail));
      target.append(div);
    }
    addApplicantFollowup(target,details);
  }
  function setupTracking() {
    const form=$("trackForm");
    if(!form)return;
    form.addEventListener("submit",async event=>{
      event.preventDefault();
      $("trackButton").disabled=true;
      try {
        const result=await request("status",{case_id:field(form,"case_id").value,access_key:field(form,"access_key").value});
        const panel=$("casePanel");panel.classList.add("show");renderCase(panel,result);
        $("feedback").hidden=true;
      }catch(error){message(error.message,"error");$("casePanel").classList.remove("show");}
      finally{$("trackButton").disabled=false;}
    });
    $("deleteCase")?.addEventListener("click",async()=>{
      if(!confirm("Remove this case, its history and evidence from active AYAR storage? This cannot be undone in the portal."))return;
      try {
        await request("delete",{case_id:field(form,"case_id").value,access_key:field(form,"access_key").value});
        field(form,"access_key").value="";
        $("casePanel").classList.remove("show");
        message("The case and evidence were removed from AYAR's active records.","success");
      }catch(error){message(error.message,"error");}
    });
  }
  function setupRegistry() {
    const area=$("registryCases");if(!area)return;
    publicGet("registry").then(response=>{
      clear(area);
      if(!response.reports.length){area.append(h("div","No reviewer-attested public reports have been published. The registry does not invent results or certificates.","a-empty"));return;}
      response.reports.forEach(item=>{
        const card=h("article","","a-card a-public-card");
        card.append(h("small",item.case_id+" · "+item.reviewed_at));
        card.append(h("h3",item.product_name));
        card.append(h("span",item.grade+" · "+item.score+"/100","a-status "+(item.grade==="Excellent"?"reviewed":"")));
        card.append(h("p",item.category+" · "+item.notice));
        area.append(card);
      });
    }).catch(error=>{clear(area).append(h("div",error.message,"a-empty"));});
  }
  let selectedCode="";
  async function loadStaffList(){
    const results=await request("staff_list");
    const list=clear($("staffCases"));
    if(!results.cases.length){list.append(h("div","There are no submitted cases yet.","a-empty"));return;}
    results.cases.forEach(item=>{
      const card=h("div","","a-card");
      card.append(h("span",item.case_id+" · "+item.status,"a-status "+item.status));
      card.append(h("h3",item.product_name));
      card.append(h("p",item.category+" · "+item.service+" · "+item.created_at));
      const button=h("button","Open case ↗","a-button a-button-secondary");
      button.type="button";button.addEventListener("click",()=>openStaffCase(item.case_id).catch(error=>message(error.message,"error")));
      card.append(button);list.append(card);
    });
  }
  async function openStaffCase(code) {
    selectedCode=code;
    const details=await request("staff_case",{case_id:code});
    const panel=$("staffDetail");clear(panel);panel.hidden=false;
    renderCase(panel,details);
    panel.append(h("p","Contact email (staff only): "+(details.contact_email||"Not provided"),"a-small"));
    if(details.files.length){
      panel.append(h("h3","Private evidence files"));
      for(const file of details.files){
        const line=h("div","","a-actions");
        const download=h("button","Download "+file.original_name+" ("+Math.ceil(file.size/1024)+" KB)","a-button a-button-secondary");
        download.addEventListener("click",()=>downloadStaffFile(code,file));
        line.append(download);panel.append(line);
      }
    }
    if(details.status!=="reviewed") {
      const statusArea=h("div","","a-paper");
      statusArea.append(h("h3","Record case disposition"));
      const select=h("select");select.id="staffStatus";
      [["in_review","In review"],["needs_information","More information required"],["declined","Decline application"]].forEach(([v,l])=>{const o=h("option",l);o.value=v;select.append(o);});
      const note=h("textarea");note.placeholder="Evidence-based reason or request for the customer…";note.id="staffNote";note.style.width="100%";note.style.minHeight="80px";
      const save=h("button","Save status","a-button");save.addEventListener("click",async()=>{
        try{await request("staff_status",{case_id:code,status:select.value,note:note.value});await openStaffCase(code);await loadStaffList();}
        catch(error){message(error.message,"error");}
      });
      statusArea.append(select,note,save);panel.append(statusArea);
      buildReviewForm(panel,details);
    }
    panel.scrollIntoView({behavior:"smooth",block:"start"});
  }
  function buildReviewForm(parent,details) {
    const form=h("form","","a-paper");form.id="expertReviewForm";form.style.marginTop="25px";
    form.append(h("h3","Reviewer-attested weighted assessment"));
    form.append(h("p","Only qualified staff should complete this record after examining the evidence. A saved report is not external accreditation.","a-small"));
    const fields=h("div","","a-review-grid");
    for(const [key,label] of rubric[details.category]){
      const row=h("div","","a-review-row");
      const labelNode=h("label",label);labelNode.htmlFor="score_"+key;
      const score=h("select");score.id="score_"+key;score.name="score_"+key;
      [["","Choose a score"],["0","0 — Fail"],["1","1 — Poor"],["2","2 — Insufficient"],["3","3 — Acceptable"],["4","4 — Good"],["5","5 — Excellent"]].forEach(([v,l])=>{const o=h("option",l);o.value=v;score.append(o);});
      const evidence=h("textarea");evidence.placeholder="Repeatable test result or documentary reference (12+ characters)";evidence.id="evidence_"+key;evidence.name="evidence_"+key;
      row.append(labelNode,score,evidence);fields.append(row);
    }
    form.append(fields);
    const description=[
      ["independence_statement","Reviewer identity, qualifications and material affiliations"],
      ["review_scope","Precisely tested scope, build and limitations"],
      ["methodology_notes","Test procedures, tools and reproducibility notes"]
    ];
    for(const [id,title] of description) {
      const wrapper=h("div","","a-field wide");wrapper.style.marginTop="18px";
      const label=h("label",title);label.htmlFor=id;
      const text=h("textarea");text.name=id;text.id=id;text.required=true;
      wrapper.append(label,text);form.append(wrapper);
    }
    const affirm=h("label","","a-check");affirm.style.marginTop="16px";
    const input=document.createElement("input");input.type="checkbox";input.name="no_material_conflict";
    affirm.append(input,h("span","I declare that I have no material conflict of interest affecting this decision and have accurately disclosed all affiliations."));
    form.append(affirm);
    const publish=h("label","","a-check");publish.style.marginTop="15px";
    const pub=document.createElement("input");pub.type="checkbox";pub.name="publish_report";pub.disabled=!details.publication_consent;
    publish.append(pub,h("span",details.publication_consent?"Publish anonymized summary in the public registry":"Applicant has not authorized public report listing"));
    form.append(publish);
    const button=h("button","Record final reviewer assessment","a-button");button.type="submit";button.style.marginTop="22px";form.append(button);
    form.addEventListener("submit",async e=>{
      e.preventDefault();
      const criteria={};
      for(const [key] of rubric[details.category]){
        const scoreValue=form.elements.namedItem("score_"+key).value;
        criteria[key]={score:scoreValue===""?null:Number(scoreValue),evidence:form.elements.namedItem("evidence_"+key).value};
      }
      const review={criteria,independence_statement:form.elements.namedItem("independence_statement").value,
        review_scope:form.elements.namedItem("review_scope").value,
        methodology_notes:form.elements.namedItem("methodology_notes").value,
        no_material_conflict:form.elements.namedItem("no_material_conflict").checked,
        publish_report:form.elements.namedItem("publish_report").checked};
      button.disabled=true;
      try{
        await request("staff_review",{case_id:selectedCode,review});
        message("Reviewer-attested report saved. This is not an official accreditation.","success");
        await openStaffCase(selectedCode);await loadStaffList();
      }catch(error){message(error.message,"error");}
      finally{button.disabled=false;}
    });
    parent.append(form);
  }
  async function downloadStaffFile(code,file) {
    try {
      if(!csrf)await publicGet("config").then(result=>csrf=result.csrf_token);
      const response=await fetch("./api",{method:"POST",credentials:"same-origin",headers:{"X-CSRFToken":csrf,"Content-Type":"application/json"},body:JSON.stringify({action:"staff_file",case_id:code,file_id:file.id})});
      if(!response.ok)throw Error("Evidence download denied");
      const blob=await response.blob();
      const url=URL.createObjectURL(blob),a=document.createElement("a");a.href=url;a.download=file.original_name;
      document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),3000);
    }catch(error){message(error.message,"error");}
  }
  async function setupReviewer() {
    if(!$("staffCases"))return;
    try {
      const config=await publicGet("config");csrf=config.csrf_token;
      if(!config.staff){$("staffGate").hidden=false;$("staffWorkspace").hidden=true;return;}
      $("staffGate").hidden=true;$("staffWorkspace").hidden=false;
      await loadStaffList();
      $("refreshStaff")?.addEventListener("click",()=>loadStaffList().catch(error=>message(error.message,"error")));
    }catch(error){message(error.message,"error");}
  }
  nav();setupSubmission();setupTracking();setupRegistry();setupReviewer();
})();
