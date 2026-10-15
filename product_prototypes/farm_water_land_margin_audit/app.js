"use strict";
/* Local-only UI: browser -> Python at 127.0.0.1; no third-party scripts. */
const $=(id)=>document.getElementById(id);
const FIELD_META=[
  ["name","Crop name","text"],
  ["max_hectares","Max planted hectares","decimal"],
  ["water_m3_per_hectare","Water (m³ per ha)","decimal"],
  ["revenue_per_hectare","Revenue per ha","decimal"],
  ["variable_cost_per_hectare","Variable cost per ha","decimal"],
  ["source_reference","Local source / estimate reference","text"],
];
let crops=[];
let lastResult=null;
let serial=0;

function crop(initial={}) {
  const x={_id:++serial,name:"",max_hectares:"0",
    water_m3_per_hectare:"1",revenue_per_hectare:"0",
    variable_cost_per_hectare:"0",source_reference:"",
    source_status:"operator_estimate"};
  for(const k of [...FIELD_META.map(v=>v[0]),"source_status"]){
    if(Object.hasOwn(initial,k))x[k]=String(initial[k]);
  }
  return x;
}
function markEdited(){
  lastResult=null;
  $("result").hidden=true;$("empty-result").hidden=false;
  $("message").textContent="Inputs changed; recalculate for updated results.";
}
function captureCrops(){
  for(const card of document.querySelectorAll(".cropcard")){
    const item=crops.find(x=>x._id===Number(card.dataset.id));
    if(!item)continue;
    card.querySelectorAll("[data-field]").forEach(input=>{
      item[input.dataset.field]=input.value;
    });
  }
}
function addLabel(container,field,title,item,type){
  const label=document.createElement("label");
  const text=document.createElement("span");text.textContent=title;label.append(text);
  const control=document.createElement("input");
  control.dataset.field=field;
  control.value=item[field]??"";
  if(type==="decimal"){
    control.type="text";control.inputMode="decimal";
    control.autocomplete="off";
    control.placeholder="e.g. 12.5";
  }else{
    control.type="text";control.maxLength=field==="source_reference"?240:90;
  }
  control.setAttribute("aria-label",title+" for "+(item.name||"crop"));
  control.addEventListener("input",markEdited);
  label.append(control);container.append(label);
}
function drawCrops(){
  const root=$("crop-editors");root.replaceChildren();
  crops.forEach((item,i)=>{
    const card=document.createElement("article");
    card.className="cropcard";card.dataset.id=item._id;
    const heading=document.createElement("div");heading.className="crophead";
    const strong=document.createElement("strong");strong.textContent="Crop "+(i+1);
    const remove=document.createElement("button");
    remove.type="button";remove.className="button outline small";
    remove.textContent="Remove";remove.disabled=crops.length<=2;
    remove.addEventListener("click",()=>{
      captureCrops();crops=crops.filter(x=>x._id!==item._id);
      drawCrops();markEdited();
    });
    heading.append(strong,remove);card.append(heading);
    const fields=document.createElement("div");fields.className="cropfields";
    FIELD_META.forEach(([field,title,type])=>addLabel(fields,field,title,item,type));
    const sourceLabel=document.createElement("label");
    sourceLabel.textContent="Self-declared evidence type";
    const status=document.createElement("select");status.dataset.field="source_status";
    for(const [value,label] of [
      ["operator_estimate","Unverified estimate"],
      ["operator_record","My record (not independently verified)"]]){
      const opt=document.createElement("option");opt.value=value;
      opt.textContent=label;status.append(opt);
    }
    status.value=item.source_status;
    status.addEventListener("change",markEdited);
    sourceLabel.append(status);fields.append(sourceLabel);
    card.append(fields);root.append(card);
  });
  $("add-crop").disabled=crops.length>=5;
}
function setStatus(message,isError=false){
  $("message").textContent=message;
  $("message").style.color=isError?"#a03a28":"#23714d";
}
function readModel(){
  captureCrops();
  if(crops.length<2||crops.length>5)throw Error("Use two to five crop alternatives.");
  const raw={
    currency:$("currency").value.trim().toUpperCase(),
    land_hectares:$("land").value.trim(),
    water_m3_available:$("water").value.trim(),
    drought_water_fraction:$("drought").value.trim(),
    crops:crops.map(row=>{
      const item={};
      for(const [key] of FIELD_META)item[key]=row[key];
      item.source_status=row.source_status;
      return item;
    })
  };
  if(JSON.stringify(raw).length>150000)throw Error("Input is too long.");
  return raw;
}
function applyModel(model){
  if(!model||typeof model!=="object"||!Array.isArray(model.crops)||
      model.crops.length<2||model.crops.length>5){
    throw Error("Invalid JSON: two to five crops are required.");
  }
  for(const k of ["currency","land_hectares","water_m3_available","drought_water_fraction"]){
    if(model[k]===undefined||model[k]===null)throw Error("Missing "+k);
  }
  const rows=model.crops.map(record=>{
    if(!record||typeof record!=="object")throw Error("Crop record must be an object.");
    for(const k of [...FIELD_META.map(f=>f[0]),"source_status"]){
      if(record[k]===undefined||record[k]===null)throw Error("Missing crop field: "+k);
    }
    return crop(record);
  });
  $("currency").value=model.currency;$("land").value=model.land_hectares;
  $("water").value=model.water_m3_available;$("drought").value=model.drought_water_fraction;
  crops=rows;drawCrops();markEdited();
}
function textTable(columns,rows){
  const table=document.createElement("table");
  const thead=document.createElement("thead"),thRow=document.createElement("tr");
  columns.forEach(label=>{
    const th=document.createElement("th");th.textContent=label;thRow.append(th);
  });
  thead.append(thRow);table.append(thead);
  const body=document.createElement("tbody");
  rows.forEach(values=>{
    const tr=document.createElement("tr");
    values.forEach(value=>{
      const td=document.createElement("td");td.textContent=value==null?"—":String(value);
      tr.append(td);
    });
    body.append(tr);
  });
  table.append(body);return table;
}
function showResult(data){
  if(data.sale_ready!==false||data.store_publication_authorized!==false||
      data.payments_authorized!==false||data.market_demand_verified!==false||
      !Array.isArray(data.water_sensitivity_frontier)||
      data.water_sensitivity_frontier.length!==5){
    throw Error("Unrecognized or commercially promoted report was refused.");
  }
  const summary=$("summary");summary.replaceChildren();
  for(const [label,value] of [
    ["Baseline gross margin",data.baseline.total_gross_margin+" "+data.currency],
    ["Reduced-water gross margin",data.water_scarcity.total_gross_margin+" "+data.currency],
    ["Hypothetical margin difference",data.hypothetical_gross_margin_loss_under_water_scarcity+" "+data.currency],
    ["Drought water fraction",data.drought_water_fraction]]){
    const card=document.createElement("div");card.className="metric";
    const small=document.createElement("small");small.textContent=label;
    const strong=document.createElement("strong");strong.textContent=value;
    card.append(small,strong);summary.append(card);
  }
  const allocation=$("allocations");allocation.replaceChildren();
  const rows=[];
  for(const [name,scenario] of [["Baseline",data.baseline],
                                ["Reduced water",data.water_scarcity]]){
    for(const crop of scenario.allocation){
      rows.push([name,crop.crop,crop.hectares,
                 crop.water_m3_used,crop.gross_margin_contribution]);
    }
  }
  allocation.append(textTable(
    ["Scenario","Crop","Area (ha)","Water used (m³)","Gross margin"],rows));
  const frontier=$("frontier");frontier.replaceChildren();
  frontier.append(textTable(
    ["Water budget fraction","Budget (m³)","Actual water (m³)",
     "Optimal gross margin","Gain since prior interval",
     "Avg gain / added allowed m³"],
    data.water_sensitivity_frontier.map(r=>[
      r.water_budget_fraction,r.water_budget_m3,r.water_used_m3,
      r.optimal_gross_margin,r.gross_margin_gain_in_interval,
      r.average_incremental_gross_margin_per_m3])));
  const warnings=$("warnings");warnings.replaceChildren();
  data.warnings.forEach(w=>{
    const li=document.createElement("li");li.textContent=w;warnings.append(li);
  });
  lastResult=data;
  $("empty-result").hidden=true;$("result").hidden=false;
  $("result").scrollIntoView({behavior:"smooth",block:"nearest"});
}
function saveJSON(data,name){
  const blob=new Blob([JSON.stringify(data,null,2)+"\n"],{type:"application/json"});
  const url=URL.createObjectURL(blob);
  const a=document.createElement("a");a.href=url;a.download=name;
  document.body.append(a);a.click();a.remove();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
}
async function calculate(){
  $("analyze").disabled=true;setStatus("Calculating on this computer...");
  try{
    const data=readModel();
    const response=await fetch("/api/analyze",{
      method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify(data),cache:"no-store"
    });
    const result=await response.json();
    if(!response.ok)throw Error(result.detail||result.error||"Analysis rejected");
    showResult(result);
    setStatus("Private computation complete. Source quality is not verified.");
  }catch(err){
    lastResult=null;$("result").hidden=true;$("empty-result").hidden=false;
    setStatus(err.message||"Could not calculate.",true);
  }finally{$("analyze").disabled=false;}
}
$("add-crop").addEventListener("click",()=>{
  captureCrops();if(crops.length>=5)return;
  crops.push(crop());drawCrops();markEdited();
});
$("sample").addEventListener("click",async()=>{
  try{
    const res=await fetch("/sample.json",{cache:"no-store"});
    if(!res.ok)throw Error("Example could not be loaded.");
    applyModel(await res.json());
    setStatus("FICTIONAL example loaded; every figure must be replaced for real use.");
  }catch(err){setStatus(err.message,true);}
});
$("import-file").addEventListener("change",async e=>{
  const f=e.target.files?.[0];if(!f)return;
  try{
    if(f.size>150000)throw Error("JSON file is too large.");
    applyModel(JSON.parse(await f.text()));
    setStatus("Input JSON imported locally. All evidence remains unverified.");
  }catch(err){setStatus(err.message,true);}
  finally{e.target.value="";}
});
$("export-input").addEventListener("click",()=>{
  try{saveJSON(readModel(),"water-land-input-private.json");}
  catch(err){setStatus(err.message,true);}
});
$("analyze").addEventListener("click",calculate);
$("export-report").addEventListener("click",()=>{
  if(lastResult)saveJSON(lastResult,"water-land-audit-private.json");
});
$("print-report").addEventListener("click",()=>{
  if(lastResult)window.print();
});
["currency","land","water","drought"].forEach(id=>$(id).addEventListener("input",markEdited));
crops=[crop(),crop()];drawCrops();
