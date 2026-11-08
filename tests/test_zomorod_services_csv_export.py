"""Verify the services-page economic report is usable without a server upload."""
from pathlib import Path
import shutil
import subprocess


SERVICES = Path(__file__).resolve().parents[1] / "content/zomorod-nova-pages/services.html"


def test_services_csv_report_has_visible_opt_in_and_input_safety():
    source = SERVICES.read_text(encoding="utf-8")
    assert 'id="zm-margin-download" type="button" disabled' in source
    assert "function csvReport(record)" in source
    assert "function resetPriorResult()" in source
    assert "input.addEventListener('input',resetPriorResult)" in source
    assert "Math.abs(outcome[k])<=Number.MAX_SAFE_INTEGER" in source
    assert "breakEvenPrice:yieldKg>0" in source
    assert "URL.revokeObjectURL(url)" in source
    assert "داده‌ها در مرورگر شما پردازش می‌شوند" in source
    assert "گزارش آموزشی است و تضمین سود" in source


def test_services_csv_report_computes_and_downloads_real_values():
    if not shutil.which("node"):
        return  # The static contract is still checked on Python-only runners.
    javascript = r"""
const fs=require("fs"),vm=require("vm"),assert=require("assert");
const html=fs.readFileSync(process.argv[1],"utf8");
const scripts=html.split("<script>").slice(1).map(x=>x.split("</script>")[0]);
for(const s of scripts){new vm.Script(s);}
const code=scripts.find(s=>s.includes("zm-margin-form"));
assert(code);
const inputs={area:"۲",yield:"۵۰۰۰",price:"۲۵۰۰۰",variable:"۱۰۰۰۰۰۰۰",fixed:"۵۰۰۰۰۰۰"};
const events={},result={hidden:true,textContent:""},error={textContent:""};
const download={disabled:true,addEventListener:(type,handler)=>events.download=handler};
const fields={};
for(const key of Object.keys(inputs)){
  fields[key]={get value(){return inputs[key]},addEventListener:(type,handler)=>{events[key+type]=handler;}};
}
const form={
  querySelector:(selector)=>fields[selector.split('name="')[1].split('"')[0]],
  querySelectorAll:(selector)=>{assert(selector==='input');return Object.values(fields);}
};
const calculate={addEventListener:(type,handler)=>events.calculate=handler};
let blob;
const document={
  getElementById:(id)=>({
    "zm-margin-form":form,"zm-margin-output":result,
    "zm-margin-error":error,"zm-margin-download":download,"zm-margin-run":calculate
  })[id],
  createElement:()=>({click(){},remove(){}}),body:{appendChild(){}}
};
vm.runInNewContext(code,{
  document,Intl,Number,Date,Blob,
  URL:{createObjectURL:(value)=>{blob=value;return "blob:test";},revokeObjectURL(){}},
  setTimeout(){}
});
events.calculate();
assert(!result.hidden && !download.disabled && !error.textContent);
assert(result.textContent.includes(new Intl.NumberFormat("fa-IR").format(220000000)));
assert(result.textContent.includes(new Intl.NumberFormat("fa-IR").format(3000)));
events.download();
assert(blob);
blob.arrayBuffer().then(bytes=>{
  const data=new Uint8Array(bytes);
  assert(data[0]===0xEF && data[1]===0xBB && data[2]===0xBF);
  return blob.text();
}).then(csv=>{
  assert(csv.includes("220000000"));
  assert(csv.includes("600"));
  assert(csv.includes("3000"));
  assert(csv.includes("محدودیت"));
  inputs.price="۲۶۰۰۰";
  events.priceinput();
  assert(download.disabled && result.hidden && result.textContent==="");
  events.calculate();
  assert(!download.disabled && result.textContent.includes(new Intl.NumberFormat("fa-IR").format(230000000)));
  inputs.yield="۰";
  events.yieldchange();
  events.calculate();
  assert(!download.disabled && result.textContent.includes("نامشخص (عملکرد صفر)"));
  events.download();
  return blob.text();
}).then(csv=>{
  assert(csv.includes("غیرقابل محاسبه؛ عملکرد صفر"));
  inputs.area="10000000"; inputs.yield="100000000";inputs.price="1000000000000";
  inputs.variable="0";inputs.fixed="0";
  events.calculate();
  assert(download.disabled && result.hidden && error.textContent.includes("قابل اتکا نیست"));
  inputs.price="";
  events.calculate();
  assert(download.disabled && result.hidden);
  console.log("CSV_REPORT_VALID");
}).catch(error=>{console.error(error);process.exitCode=1;});
"""
    run = subprocess.run(
        ["node", "-e", javascript, str(SERVICES)],
        capture_output=True, text=True, timeout=15, check=False
    )
    assert run.returncode == 0, run.stderr
    assert "CSV_REPORT_VALID" in run.stdout
