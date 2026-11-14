/* Pure, offline policy for existing Zomorod inner-page census.
 * No network, no site writes, no homepage.
 */
'use strict';
const PAGES=Object.freeze([
 '/about/','/company/','/services/','/research/','/agriculture/',
 '/industry/','/knowledge/','/economy/','/market/','/contact/','/store/',
 '/tala/','/ghanadi/','/ghanadi/cafe-shiraz/','/faremah/','/amozeshgah/',
 '/business/','/apps/','/games/','/news/','/newsletter/','/studio/','/auctions/'
]);
function assertExactPaths(paths=PAGES){
 if(!Array.isArray(paths)||!paths.length||paths.includes('/')||new Set(paths).size!==paths.length)
  throw new Error('Invalid census routes: duplicates, empty, or homepage');
 if(paths.some(p=>!/^\/[a-z0-9/-]+\/$/.test(p)||p.includes('//')||p.includes('..')))
  throw new Error('Invalid census route syntax');
 return paths.length;
}
function classify(item){
 if(item.error || !item.http) return 'UNKNOWN_FETCH_FAILED';
 if(item.http!==200) return 'HTTP_NOT_200';
 if(item.documentPath && item.documentPath!==item.path) return 'WRONG_DOCUMENT_PATH';
 if(item.censusComplete!==true) return 'UNKNOWN_DOM_UNINSPECTED';
 return 'INSPECTED';
}
function summarize(items,paths=PAGES){
 assertExactPaths(paths);
 if(items.length!==paths.length || items.some((x,i)=>x.path!==paths[i]))
  throw new Error('Census incomplete, reordered or unexpectedly scoped');
 const counts={INSPECTED:0,UNKNOWN_FETCH_FAILED:0,HTTP_NOT_200:0,
  WRONG_DOCUMENT_PATH:0,UNKNOWN_DOM_UNINSPECTED:0};
 for(const item of items)counts[classify(item)]++;
 const pathsWithBlackBands=items.filter(x=>classify(x)==='INSPECTED'&&x.blackBands?.length)
  .map(x=>x.path);
 const http200=items.filter(x=>x.http===200).length;
 const transientFailures=items.filter(x=>x.attempts?.some(a=>a.ok===false) &&
  classify(x)==='INSPECTED').map(x=>x.path);
 return {total:items.length,http200,inspected:counts.INSPECTED,
  fetchErrors:counts.UNKNOWN_FETCH_FAILED,non200:counts.HTTP_NOT_200,
  redirected:counts.WRONG_DOCUMENT_PATH,domIncomplete:counts.UNKNOWN_DOM_UNINSPECTED,
  failedRoutes:items.filter(x=>classify(x)!=='INSPECTED').map(x=>({
   path:x.path,status:classify(x),attempts:x.attempts?.length||0})),
  transientFailures,pathsWithBlackBands,
  allRoutesInspected:counts.INSPECTED===paths.length,
  gate:'NO_GO_UNLESS_ALL_INSPECTED',
  pageSourcesUnchanged:true,liveWrites:0,formsSubmitted:0,
  excludedHomepage:'/'};
}
assertExactPaths();
module.exports={PAGES,assertExactPaths,classify,summarize};
