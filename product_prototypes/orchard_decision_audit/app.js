"use strict";
/* Offline frontend: all analysis is performed by the same locally bound Python server. */
const FIELDS=["revenue","variable_cost","fixed_cost","capital_cost","terminal_value"];
const FIELD_TITLES=["Revenue","Variable cost","Fixed cost","Capital cost","Terminal receipt"];
const STRESSES=["downside","upside"];
const FACTORS=["price_factor","yield_factor","variable_cost_factor"];
const $=(id)=>document.getElementById(id);
let options=[];
let report=null;
let serial=0;
let factors={
  downside:{price_factor:"0.8",yield_factor:"0.9",variable_cost_factor:"1.2"},
  upside:{price_factor:"1.1",yield_factor:"1.1",variable_cost_factor:"0.9"}
};
function newOption(n){
  return {id:++serial,name:n,source:"",years:[]};
}
function rowYear(year) {
  const o={year};
  FIELDS.forEach(k=>{o[k]="0";});
  return o;
}
function fitYears(o,count) {
  while(o.years.length<count+1)o.years.push(rowYear(o.years.length));
  if(o.years.length>count+1)o.years.length=count+1;
}
function horizon(){
  return Number.parseInt($("horizon").value,10);
}
function capture(){
  document.querySelectorAll(".option").forEach(card=>{
    const o=options.find(x=>x.id===Number(card.dataset.key));
    if(!o)return;
    o.name=card.querySelector(".option-name").value;
    o.source=card.querySelector(".option-source").value;
    card.querySelectorAll(".year-table tbody tr").forEach(tr=>{
      const year=Number(tr.dataset.year);
      if(!o.years[year])o.years[year]=rowYear(year);
      tr.querySelectorAll("input[data-field]").forEach(inp=>o.years[year][inp.dataset.field]=inp.value);
    });
  });
  document.querySelectorAll("input[data-scenario]").forEach(inp=>{
    factors[inp.dataset.scenario][inp.dataset.factor]=inp.value;
  });
}
function showMessage(message,success=false) {
  $("editor-message").textContent=message;
  $("editor-message").style.color=success?"#21613b":"#8c3c28";
}
function renderOptions(){
  const focus=document.activeElement?.id;
  const root=$("option-editors");root.replaceChildren();
  const previous=$("reference").value;
  const ref=$("reference");ref.replaceChildren();
  const n=horizon();
  if(!Number.isInteger(n)||n<1||n>30){
    showMessage("Choose 1–30 years before editing.");
    return;
  }
  options.forEach((o,index)=>{
    fitYears(o,n);
    const card=document.createElement("article");
    card.className="option";card.dataset.key=o.id;
    const header=document.createElement("div");header.className="optionhead";
    const name=document.createElement("input");name.className="option-name";
    name.type="text";name.maxLength=80;name.value=o.name;
    name.setAttribute("aria-label","Investment alternative "+(index+1)+" name");
    name.addEventListener("change",()=>{capture();renderReferences();});
    header.append(name);
    const remove=document.createElement("button");remove.className="button small";
    remove.textContent="Remove";remove.type="button";remove.disabled=options.length<=2;
    remove.addEventListener("click",()=>{
      capture();options=options.filter(x=>x.id!==o.id);renderOptions();
    });
    header.append(remove);card.append(header);
    const lab=document.createElement("label");lab.textContent="Source / reference for input estimates (not externally verified)";
    const src=document.createElement("input");src.className="option-source";src.maxLength=250;
    src.placeholder="e.g. grower budget 2025, or estimated";src.value=o.source;
    lab.append(src);card.append(lab);
    const scroll=document.createElement("div");scroll.className="year-scroll";
    const table=document.createElement("table");table.className="year-table";
    const thead=document.createElement("thead");const trow=document.createElement("tr");
    ["Year",...FIELD_TITLES].forEach(t=>{const th=document.createElement("th");th.textContent=t;trow.append(th)});
    thead.append(trow);table.append(thead);
    const tbody=document.createElement("tbody");
    o.years.forEach((y)=>{
      const tr=document.createElement("tr");tr.dataset.year=y.year;
      const td0=document.createElement("td");td0.textContent=y.year===0?"0 now":String(y.year);tr.append(td0);
      FIELDS.forEach((field,fi)=>{
        const cell=document.createElement("td");const input=document.createElement("input");
        input.type="number";input.min="0";input.step="any";input.value=String(y[field]??"0");
        input.dataset.field=field;input.setAttribute("aria-label",o.name+" year "+y.year+" "+FIELD_TITLES[fi]);
        cell.append(input);tr.append(cell);
      });
      tbody.append(tr);
    });
    table.append(tbody);scroll.append(table);card.append(scroll);root.append(card);
  });
  renderReferences(previous);
}
function renderReferences(previous){
  const ref=$("reference");const selected=previous??ref.value;ref.replaceChildren();
  options.forEach(o=>{
    const entry=document.createElement("option");entry.value=o.name;entry.textContent=o.name;ref.append(entry);
  });
  if(options.some(o=>o.name===selected))ref.value=selected;
}
function renderStress(){
  const root=$("stress-editor");root.replaceChildren();
  for(const name of STRESSES){
    const section=document.createElement("div");section.className="scenario";
    const strong=document.createElement("strong");strong.textContent=name==="downside"?"↓ Downside":"↑ Upside";section.append(strong);
    const labels=["Price multiplier","Yield multiplier","Variable cost multiplier"];
    FACTORS.forEach((f,i)=>{
      const label=document.createElement("label");label.textContent=labels[i];
      const input=document.createElement("input");input.type="number";input.step=".01";input.min="0";input.max="4";
      input.value=factors[name][f];input.dataset.scenario=name;input.dataset.factor=f;
      label.append(input);section.append(label);
    });
    root.append(section);
  }
}
function collect(){
  capture();
  if(!Number.isInteger(horizon())||horizon()<1||horizon()>30)throw new Error("Horizon outside 1–30 years");
  const byName=new Set();
  for(const o of options){
    if(!o.name.trim()||byName.has(o.name))throw new Error("Each option must have a unique name.");
    byName.add(o.name);
  }
  const assumptions=[];
  options.forEach(o=>{
    if(o.source.trim()){
      FIELDS.forEach(f=>{
        if(o.years.some(y=>Number(y[f])>0)){
          assumptions.push({option:o.name,field:f,source_reference:o.source,
            evidence_status:"operator_estimate"});
        }
      });
    }
  });
  return {
    currency:$("currency").value.toUpperCase().trim(),unit:$("unit").value,
    money_basis:$("money-basis").value,horizon_years:horizon(),
    discount_rate_pct:$("discount").value,
    reference_option:$("reference").value,
    options:options.map(o=>({name:o.name,years:o.years.map(y=>({...y}))})),
    stress_scenarios:JSON.parse(JSON.stringify(factors)),
    assumptions,
  };
}
function writeTable(rows){
  const table=document.createElement("table");table.className="resulttable";
  const head=document.createElement("tr");
  ["Alternative","NPV","Δ vs reference"].forEach(t=>{const th=document.createElement("th");th.textContent=t;head.append(th)});
  const thead=document.createElement("thead");thead.append(head);table.append(thead);
  const body=document.createElement("tbody");
  rows.forEach(o=>{
    const tr=document.createElement("tr");
    for(const key of ["option","npv","delta_npv_vs_reference"]){
      const td=document.createElement("td");td.textContent=o[key];tr.append(td);
    }
    body.append(tr);
  });
  table.append(body);return table;
}
function renderResult(data){
  report=data;$("result-empty").hidden=true;$("result-area").hidden=false;
  $("winner").textContent=data.leading_option_by_base_npv_not_advice;
  const grid=$("result-grid");grid.replaceChildren();
  for(const key of ["base","downside","upside"]){
    const label=document.createElement("h3");label.className="scenarioheading";
    label.textContent=key.toUpperCase()+" / "+data.currency+" / "+data.unit;
    grid.append(label,writeTable(data.scenarios[key]));
  }
  $("warnings").textContent="Important warnings:\n"+data.warnings.join("\n");
  $("result-area").scrollIntoView({behavior:"smooth",block:"start"});
}
function downloadJson(payload,filename){
  const blob=new Blob([JSON.stringify(payload,null,2)+"\n"],{type:"application/json"});
  const url=URL.createObjectURL(blob);
  const anchor=document.createElement("a");anchor.href=url;anchor.download=filename;
  document.body.append(anchor);anchor.click();anchor.remove();
  URL.revokeObjectURL(url);
}
async function loadFictional(){
  const response=await fetch("/sample.json",{cache:"no-store"});
  if(!response.ok)throw new Error("Sample unavailable");
  const data=await response.json();
  apply(data);
  showMessage("Loaded fictional example. Replace EVERY figure before real use.",true);
}
function apply(data){
  if(!data||!Array.isArray(data.options)||data.options.length<2||data.options.length>5){
    throw new Error("Input JSON must contain two to five alternatives.");
  }
  if(!Number.isInteger(data.horizon_years)||data.horizon_years<1||data.horizon_years>30){
    throw new Error("Input horizon outside 1–30.");
  }
  $("currency").value=data.currency??"USD";$("unit").value=data.unit??"per_hectare";
  $("money-basis").value=data.money_basis??"real";$("horizon").value=data.horizon_years;
  $("discount").value=data.discount_rate_pct??"10";
  options=data.options.map(o=>{
    const value=newOption(o.name);
    value.years=Array.isArray(o.years)?o.years.map(y=>({...y})):[];
    return value;
  });
  if(data.stress_scenarios&&typeof data.stress_scenarios==="object"){
    factors=JSON.parse(JSON.stringify(data.stress_scenarios));
  }
  renderOptions();renderStress();
  $("reference").value=data.reference_option??options[0].name;
  report=null;$("result-area").hidden=true;$("result-empty").hidden=false;
  $("warnings").textContent="Audit warnings appear after calculation.";
}
async function analyze(){
  showMessage("Calculating locally...");
  let data;
  try{data=collect();}
  catch(e){showMessage(e.message);return;}
  try{
    const response=await fetch("/api/analyze",{
      method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(data),cache:"no-store"
    });
    const body=await response.json();
    if(!response.ok)throw new Error(body.detail??body.error??"Calculation failed");
    renderResult(body);showMessage("Private calculation completed.",true);
  }catch(e){showMessage(e.message??"Unexpected processing error");}
}
$("load-sample").addEventListener("click",()=>loadFictional().catch(e=>showMessage(e.message)));
$("import-file").addEventListener("change",async e=>{
  const file=e.target.files[0];
  if(!file)return;
  if(file.size>200000){showMessage("Import exceeds 200 kB");return;}
  try{apply(JSON.parse(await file.text()));showMessage("Input imported (not independently verified).",true);}
  catch(err){showMessage(err.message)}
  finally{e.target.value="";}
});
$("download-input").addEventListener("click",()=>{
  try{downloadJson(collect(),"orchard-decision-input-private.json");}catch(e){showMessage(e.message);}
});
$("download-report").addEventListener("click",()=>{
  if(report)downloadJson(report,"orchard-decision-report-private.json");
});
$("analyze").addEventListener("click",analyze);
$("horizon").addEventListener("change",()=>{capture();renderOptions();});
$("add-option").addEventListener("click",()=>{
  if(options.length>=5){showMessage("Maximum five options.");return;}
  capture();options.push(newOption("Option "+(options.length+1)));renderOptions();
});
options=[newOption("Maintain current operation"),newOption("Alternative investment")];
renderOptions();renderStress();
showMessage("Enter your own figures or load the clearly marked fictional example.",true);
