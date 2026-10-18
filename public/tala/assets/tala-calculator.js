/* Tala-only transparent gold and jewelry calculator; all monetary inputs are IRR. */
(function(scope){
  'use strict';
  const norm=s=>String(s??'').trim().replace(/[۰-۹]/g,c=>String('۰۱۲۳۴۵۶۷۸۹'.indexOf(c))).replace(/[٠-٩]/g,c=>String('٠١٢٣٤٥٦٧٨٩'.indexOf(c))).replace(/[٬,\s]/g,'').replace(/٫/g,'.');
  function number(value,limit,name,allowZero=true){
    const raw=norm(value);
    if(!/^(?:\d+)(?:\.\d{1,3})?$/.test(raw))throw new Error('مقدار «'+name+'» معتبر نیست.');
    const val=Number(raw);
    if(!Number.isFinite(val)||val<0||val>limit||(!allowZero&&val===0))throw new Error('مقدار «'+name+'» خارج از محدوده است.');
    return val;
  }
  const rounded=n=>Math.round((n+Number.EPSILON)*100)/100;
  function calculate(values){
    const weight=number(values.weight,100000,'وزن',false);
    const purity=number(values.purity,999.9,'عیار',false);
    if(purity<100)throw new Error('عیار باید بین ۱۰۰ و ۹۹۹٫۹ باشد.');
    const rate=number(values.rate,1000000000000,'نرخ هر گرم طلای ۱۸ عیار',false);
    const laborPct=number(values.laborPct||0,100,'درصد اجرت');
    const laborPerGram=number(values.laborPerGram||0,10000000000,'اجرت هر گرم');
    const extra=number(values.extra||0,1000000000000,'هزینه ساخت یا مخراج‌کاری');
    const gem=number(values.gem||0,1000000000000,'ارزش سنگ');
    const profitPct=number(values.profitPct||0,100,'درصد سود');
    const taxPct=number(values.taxPct||0,100,'درصد مالیات');
    const material=rounded(weight*rate*purity/750);
    const labor=rounded(material*laborPct/100+weight*laborPerGram+extra);
    const profit=rounded((material+labor)*profitPct/100);
    // Gold principal is excluded from this estimate's VAT base.
    // Gemstone VAT, if applicable, must be separately verified on the invoice.
    const tax=rounded((labor+profit)*taxPct/100);
    const total=rounded(material+labor+profit+tax+gem);
    if(!Number.isSafeInteger(Math.round(total)))throw new Error('مقدار بسیار بزرگ است.');
    return {material,labor,profit,tax,gem,total,purity,weight,rate};
  }
  const fmt=n=>new Intl.NumberFormat('fa-IR',{maximumFractionDigits:2}).format(n);
  scope.TalaCalc={calculate,number,norm,fmt};
})(typeof window==='undefined'?globalThis:window);
