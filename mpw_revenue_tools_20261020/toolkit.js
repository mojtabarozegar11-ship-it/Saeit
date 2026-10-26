(()=>{"use strict";
const mount=document.getElementById("mpw-functional-tool");
if(!mount)return;
const slug=mount.dataset.tool||"";
const metric=(event)=>{if(!/^(tool_generated|quote_click|game_interacted)$/.test(event))return;try{const beacon=new Image(1,1);beacon.src="/mpw-editorial/revenue/metrics.php?slug="+encodeURIComponent(slug)+"&event="+event+"&r="+Math.random().toString(36).slice(2)}catch{}};
document.querySelectorAll('a[data-cta="quote"]').forEach(a=>a.addEventListener("click",()=>metric("quote_click")));
const $=(tag,attrs={},...kids)=>{const e=document.createElement(tag);for(const [k,v] of Object.entries(attrs)){if(k==="className")e.className=v;else if(k==="text")e.textContent=String(v);else if(k==="value")e.value=String(v);else e.setAttribute(k,String(v))}for(const v of kids)if(v!=null)e.append(typeof v==="string"?document.createTextNode(v):v);return e};
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const trim=s=>String(s??"").trim().slice(0,600);
const num=(v,d=0)=>Number.isFinite(Number(v))?Number(v):d;
const usd=n=>new Intl.NumberFormat("en-US",{style:"currency",currency:"USD"}).format(n);
const csvCell=v=>{let s=String(v??"");if(/^[=+\-@\t\r]/.test(s))s="'"+s;return '"'+s.replace(/"/g,'""')+'"';};
const csv=rows=>rows.map(row=>row.map(csvCell).join(",")).join("\r\n");
const download=(name,body,mime)=>{const blob=new Blob([body],{type:mime}),u=URL.createObjectURL(blob),a=$("a",{href:u,download:name});document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(u),1200)};
const page=(title,body)=>'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+esc(title)+'</title><style>body{font:17px system-ui;line-height:1.6;max-width:780px;margin:40px auto;padding:25px;background:#f7f5f0;color:#202733}h1{line-height:1.25}h2{margin-top:32px}a{color:#095c4b}button{padding:12px;border-radius:8px}hr{border:0;border-top:1px solid #ccc}@media print{button{display:none}}</style></head><body>'+body+'</body></html>';
const defs={
"website-doctor":{title:"Website Doctor · self-check",tip:"A real, downloadable checklist. Browser-only tool: it does not claim to crawl external websites.",fields:[["url","Website URL","url","https://example.com"],["goal","Primary website goal","text","Sell digital products"],["speed","Largest page load (seconds, measured by you)","number","4"]]},
"landing-page-studio":{title:"Landing Page Builder",tip:"Produce a working downloadable, mobile-responsive HTML landing page.",fields:[["company","Business name","text","Northstar Studio"],["offer","Offer / service","text","Website design"],["audience","Ideal customer","text","Small businesses"],["email","Public contact email","email","hello@example.com"]]},
"ai-automation":{title:"Workflow Blueprint Builder",tip:"Create a documented JSON workflow with manual approval gates; this tool does not connect to private accounts.",fields:[["process","Business process","text","Customer enquiry triage"],["trigger","What starts the workflow","text","New customer request"],["output","Desired result","text","Reviewed reply draft"],["owner","Human approver role","text","Operations manager"]]},
"business-spreadsheets":{title:"Business Cost & Margin Spreadsheet",tip:"Calculate unit economics and export an Excel-compatible CSV. Values are illustrative; verify tax and accounting assumptions.",fields:[["item","Product / service","text","Digital course"],["qty","Expected units sold","number","40"],["price","Sale price per unit (USD)","number","29"],["unitcost","Variable cost per unit (USD)","number","7"],["fixed","Monthly fixed costs (USD)","number","250"]]},
"website-templates":{title:"Responsive Website Starter",tip:"Export a complete single-file HTML template with usable navigation and responsive layout.",fields:[["business","Business title","text","Evergreen Works"],["headline","Homepage headline","text","Your next big idea starts here"],["service","Main service","text","Digital strategy"],["contact","Contact email","email","hello@example.com"]]},
"social-media-kits":{title:"7-day Social Content Kit",tip:"Generate seven editable caption drafts and export a schedule as CSV; review before posting.",fields:[["brand","Brand / product","text","Creative Studio"],["benefit","Customer benefit","text","Save time"],["audience","Target audience","text","Business owners"],["website","Website","url","https://example.com"]]},
"resume-builder":{title:"Professional Resume Builder",tip:"Draft an editable resume and export a print-ready HTML file. Do not include private identification numbers.",fields:[["name","Full name","text","Alex Morgan"],["role","Target role","text","Operations Analyst"],["experience","Experience summary","textarea","Managed workflows, reporting and cross-functional projects."],["skills","Skills (comma-separated)","text","Excel, Python, Communication"],["email","Professional contact email","email","alex@example.com"]]},
"logo-studio":{title:"Logo Concept Studio",tip:"Create a simple original SVG wordmark concept. Check trademark similarity before commercial use.",fields:[["name","Brand name","text","Nova Labs"],["initials","Initials (max 3)","text","NL"],["color","Accent color","color","#c89e59"],["bg","Background color","color","#121b2a"]]},
"browser-games":{title:"Play: Reach 24 in Four Moves",tip:"A working logic game. Start from zero, use exactly four operations, and try to reach 24. No wagering, prizes or payment.",fields:[]},
"marketing-ai":{title:"Campaign Planner · no external AI required",tip:"A working local campaign planner. This version is rule-based, not a connected generative-AI service.",fields:[["brand","Brand","text","Nova Labs"],["goal","Campaign goal","text","New product awareness"],["audience","Target audience","text","Small business owners"],["offer","Call to action","text","Book a free consultation"]]},
"business-calculators":{title:"Break-even & Margin Calculator",tip:"Compute contribution margin, break-even quantity and estimated operating profit.",fields:[["price","Selling price per unit (USD)","number","49"],["variable","Variable cost per unit (USD)","number","14"],["fixed","Monthly fixed costs (USD)","number","850"],["units","Expected monthly sales (units)","number","40"]]},
"website-care":{title:"Website Care Audit Tracker",tip:"Build a monthly technical maintenance checklist and export a record. This does not perform remote server maintenance.",fields:[["site","Website / application","url","https://example.com"],["owner","Responsible team","text","Site operations"],["backup","Last recovery-tested backup date","date","2026-10-01"],["ticket","Current support reference","text","MAINT-001"]]}
};
const def=defs[slug];if(!def)return;
mount.innerHTML="";
mount.className="mpw-functional-wrap";
const hd=$("div",{className:"mpw-functional-heading"},$("span",{className:"mpw-demo-badge",text:"WORKING FREE TOOL"}),$("h2",{text:def.title}),$("p",{text:def.tip}));
const form=$("form",{className:"mpw-form"}),result=$("div",{className:"mpw-tool-result",role:"status","aria-live":"polite"});
for(const [key,label,type,ph]of def.fields){const field=$("label",{className:"mpw-field"});field.append($("span",{text:label}));const el=type==="textarea"?$("textarea",{name:key,rows:"3",placeholder:ph}):$("input",{name:key,type,placeholder:ph,value:(type==="color"||type==="number"||type==="date")?ph:""});if(type!=="number"&&type!=="color"&&type!=="date")el.value=ph;field.append(el);form.append(field)}
const submit=$("button",{type:"submit",className:"mpw-tool-button",text:"Generate my result"});
const note=$("p",{className:"mpw-tool-note",text:"Your inputs stay in this browser. No money is collected by this tool. Premium custom work requires a separate written quotation."});
if(slug!=="browser-games")form.append(submit);mount.append(hd,form,result,note);
const val=key=>trim(form.elements.namedItem(key)?.value);
const emit=(title,summary,filename,data,mime="text/plain;charset=utf-8",htmlPreview="")=>{
  result.replaceChildren($("h3",{text:title}),$("p",{text:summary}));
  const btn=$("button",{type:"button",className:"mpw-tool-button",text:"Download result"});
  btn.addEventListener("click",()=>download(filename,data,mime));result.append(btn);
  if(htmlPreview){const frame=$("iframe",{title:"Live preview",sandbox:"",className:"mpw-tool-preview"});frame.srcdoc=htmlPreview;result.append(frame)}
};
function run(){
  if(slug==="website-doctor"){
    let u;try{u=new URL(val("url"));if(!["https:","http:"].includes(u.protocol))throw Error("invalid")}catch{return result.replaceChildren($("p",{text:"Enter a valid public website URL."}))}
    const sec=Math.max(0,num(val("speed"),0)),checks=[
      ["HTTPS","Check TLS and redirect to HTTPS"],
      ["Mobile layout","Test at 360px viewport width"],
      ["Navigation","Every page needs an understandable route home"],
      ["SEO metadata","Unique title and meta description per page"],
      ["Indexing","Validate robots.txt and XML sitemap"],
      ["Checkout","Test real login, invoice and delivery"],
      ["Accessibility","Keyboard focus, labels and alt text"],
      ["Performance","Measure LCP, INP and CLS in PageSpeed Insights"],
      ["Security","Maintain tested backups, updates and least privilege"],
      ["Structured data","Only publish accurate Product, Service and Organization metadata"],
      ["Trust","Show real terms, pricing and contact details"],
      ["Conversion","Provide one clear primary call to action"]
    ];if(sec>3)checks.unshift(["Slow load","Investigate likely load time bottlenecks; unverified until Lighthouse measurement"]);
    const html=page("Website review plan — "+u.hostname,"<h1>Website review plan: "+esc(u.hostname)+"</h1><p>Objective: "+esc(val("goal"))+"</p><p>Visitor-provided load estimate: "+esc(sec)+" seconds (not remotely measured).</p><ol>"+checks.map(x=>"<li><strong>"+esc(x[0])+"</strong> — "+esc(x[1])+"</li>").join("")+"</ol><p>This checklist is not an automated security scan or SEO ranking guarantee.</p>");
    return emit("Audit plan ready",checks.length+" practical checkpoints. These must be checked against the live site.","website-review-"+u.hostname+".html",html,"text/html;charset=utf-8",html)
  }
  if(slug==="landing-page-studio"||slug==="website-templates"){
    const name=val(slug==="landing-page-studio"?"company":"business"),headline=slug==="landing-page-studio"?"Get "+val("offer")+" for "+val("audience"):val("headline"),desc=slug==="landing-page-studio"?"Helping "+val("audience")+" with "+val("offer"):val("service"),email=val(slug==="landing-page-studio"?"email":"contact");
    const html=page(name,'<header><strong>'+esc(name)+'</strong><nav aria-label="Primary"><a href="#service">Services</a> · <a href="#contact">Contact</a></nav></header><main><h1>'+esc(headline)+'</h1><p>'+esc(desc)+'</p><p><a href="#contact">Get in touch →</a></p><section id="service"><h2>What we offer</h2><p>'+esc(desc)+'</p></section><section id="contact"><h2>Contact</h2><p>'+esc(email)+'</p></section></main><footer>© '+esc(name)+'</footer>');
    return emit("Live landing-page draft","Responsive HTML is ready to preview, download and customize.",slug+".html",html,"text/html;charset=utf-8",html)
  }
  if(slug==="ai-automation"){
    const info={name:val("process"),trigger:val("trigger"),expected_result:val("output"),human_approver:val("owner"),steps:["Receive and validate incoming data","Prepare a draft or recommended action","Human approval gate","Execute only an explicitly approved step","Log the result and allow rollback"],safety:{default:"dry-run",external_actions:"require explicit approval",secrets:"Do not store in plain text",logging:"redact personal data"}};
    return emit("Workflow blueprint generated","A structured, implementation-ready outline with approval gates.", "automation-blueprint.json",JSON.stringify(info,null,2),"application/json")
  }
  if(slug==="business-spreadsheets"||slug==="business-calculators"){
    const p=num(val(slug==="business-spreadsheets"?"price":"price")),v=num(val(slug==="business-spreadsheets"?"unitcost":"variable")),f=num(val("fixed")),q=num(val(slug==="business-spreadsheets"?"qty":"units"));
    if([p,v,f,q].some(x=>x<0)||p<=0)return result.replaceChildren($("p",{text:"Enter nonnegative amounts and a positive selling price."}));
    const m=p-v,breakEven=m>0?Math.ceil(f/m):"Not achievable at current price",revenue=q*p,operating=q*m-f;
    const rows=[["Metric","Value (USD unless units)"],["Unit price",p],["Unit variable cost",v],["Unit contribution margin",m],["Monthly fixed cost",f],["Projected units",q],["Revenue",revenue],["Projected operating profit (before tax)",operating],["Break-even units",breakEven]];
    result.replaceChildren($("h3",{text:"Calculated economics"}),$("p",{text:"Monthly sales "+usd(revenue)+" · Operating profit "+usd(operating)+" · Break-even "+breakEven+" units"}));
    const btn=$("button",{type:"button",className:"mpw-tool-button",text:"Download CSV for Excel"});btn.onclick=()=>download("business-economics.csv",csv(rows),"text/csv;charset=utf-8");result.append(btn);return
  }
  if(slug==="social-media-kits"||slug==="marketing-ai"){
    const brand=val("brand"),benefit=val(slug==="social-media-kits"?"benefit":"goal"),audience=val("audience"),url=slug==="social-media-kits"?val("website"):val("offer");
    const hooks=["A common problem","A simple how-to","Behind the scenes","Three mistakes to avoid","Customer question","Practical checklist","A clear next step"];
    const rows=[["Day","Content angle","Draft caption","Review status"]];
    hooks.forEach((angle,i)=>rows.push([i+1,angle,brand+": "+angle.toLowerCase()+". For "+audience+", focus on "+benefit+". "+url,"Draft — review before publishing"]));
    return emit("Seven-day editorial calendar","Seven original editable starting prompts and captions; not AI-generated or automatically published.","seven-day-marketing-plan.csv",csv(rows),"text/csv;charset=utf-8")
  }
  if(slug==="resume-builder"){
    const skills=val("skills").split(",").map(x=>x.trim()).filter(Boolean).slice(0,18);
    const html=page(val("name")+" — resume","<h1>"+esc(val("name"))+"</h1><p><strong>"+esc(val("role"))+"</strong> · "+esc(val("email"))+"</p><h2>Profile</h2><p>"+esc(val("experience"))+"</p><h2>Skills</h2><ul>"+skills.map(x=>"<li>"+esc(x)+"</li>").join("")+"</ul><h2>Professional experience</h2><p>Add employers, dates and measurable achievements here.</p><p>Check all claims before submitting to an employer.</p>");
    return emit("Resume draft generated","Print this HTML to PDF using your browser, or edit the file before applying.","resume.html",html,"text/html;charset=utf-8",html)
  }
  if(slug==="logo-studio"){
    const brand=val("name"),initials=val("initials").slice(0,3).toUpperCase().replace(/[^A-Z0-9]/g,"")||"M",c=val("color"),bg=val("bg");
    if(!/^#[\da-fA-F]{6}$/.test(c)||!/^#[\da-fA-F]{6}$/.test(bg))return;
    const svg='<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="400" viewBox="0 0 1000 400"><rect width="1000" height="400" rx="28" fill="'+bg+'"/><circle cx="230" cy="200" r="130" fill="none" stroke="'+c+'" stroke-width="9"/><text x="230" y="223" fill="'+c+'" text-anchor="middle" font-size="90" font-family="Arial,sans-serif" font-weight="700">'+initials+'</text><text x="422" y="207" fill="#ffffff" font-size="56" font-family="Arial,sans-serif">'+esc(brand.slice(0,24))+'</text></svg>';
    result.replaceChildren($("h3",{text:"Wordmark SVG ready"}),$("p",{text:"Review similarity and licensing before commercial use."}));
    const b=$("button",{type:"button",className:"mpw-tool-button",text:"Download editable SVG"});b.onclick=()=>download("logo-concept.svg",svg,"image/svg+xml");result.append(b);const img=$("img",{alt:"Generated wordmark concept preview",className:"mpw-logo-preview"});img.src="data:image/svg+xml;charset=utf-8,"+encodeURIComponent(svg);result.append(img);return
  }
  if(slug==="website-care"){
    const tasks=["SSL certificate is valid","Public pages and checkout tested","Backups restored in a safe environment","Software updates reviewed","Search indexing and sitemap checked","Browser and mobile display checked","Error logs reviewed","Security alerts and monitoring checked"];
    const obj={site:val("site"),owner:val("owner"),last_restore_test:val("backup"),support_ref:val("ticket"),checklist:tasks.map(x=>({task:x,status:"To verify"}))};
    return emit("Maintenance report template ready",tasks.length+" tasks recorded with explicit unverified status.","website-care-report.json",JSON.stringify(obj,null,2),"application/json")
  }
}
if(slug==="browser-games"){
 let value=0,moves=0,logged=false;
 const display=$("h3",{text:"Value: 0 · Moves: 0/4"}),msg=$("p",{text:"Try to reach exactly 24 in four operations."});
 const ops=$("div",{className:"mpw-game-controls"});
 const reset=()=>{value=0;moves=0;display.textContent="Value: 0 · Moves: 0/4";msg.textContent="Try to reach exactly 24 in four operations."};
 for(const op of ["+","×","−"])for(const n of [2,3,4,6]){
  const b=$("button",{type:"button",className:"mpw-game-btn",text:op+" "+n});
  b.onclick=()=>{
    if(moves>=4)return;
    if(!logged){metric("game_interacted");logged=true;}
    value=op==="+"?value+n:op==="−"?value-n:value*n;
    moves++;display.textContent="Value: "+value+" · Moves: "+moves+"/4";
    msg.textContent=moves===4?(value===24?"Success! You reached exactly 24.":"Finished at "+value+". Try another strategy."):("Keep going — "+(4-moves)+" moves left.");
  };ops.append(b)
 }
 const start=$("button",{type:"button",className:"mpw-tool-button",text:"Restart puzzle"});start.onclick=reset;
 result.append(display,msg,ops,start);
}else{form.addEventListener("submit",e=>{e.preventDefault();try{run();if(result.querySelector("h3"))metric("tool_generated")}catch(error){result.replaceChildren($("p",{text:"The input could not be processed. Check the fields and try again."}))}})}
})();
