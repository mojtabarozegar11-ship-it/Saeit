#!/usr/bin/env python3
"""One-time, nonbinding, targeted machinery and production-line RFQ from verified company mailbox."""
import csv
import email.utils
import fcntl
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from email.message import EmailMessage

CAMPAIGN = "cn-machinery-150-nonbinding-rfq-20261023"
SENDER = "moj_1ro_1@zomorodmelal.ir"
RECIPIENT_CSV = r'''category,company,email,public_source_url
"packaging","Changzhou Hengyuan Machinery","sales@myhymachinery.com","https://www.myhymachinery.com/info/Contact-Us.html"
"pellet","ALLWIN International TCPEL","jack@tcpel.com","https://tcpel.net/contact-us/"
"pellet","ZCICO Feed Machinery","sales@zcico.com","https://zcico.com/contact/"
"packaging","Jiangsu ASG Packaging Machinery Group","market@asgchina.com","https://www.shinefate.com/en/contact"
"food","Dongguan Good Aider Food Machinery","sales@goodaider.com","https://goodaider.com/pages/contact"
"agricultural","CAGRI Wuxi Agricultural Machinery","Hedong@camcjsw.com","https://www.cagri.com.cn/contact/"
"packaging","Guangdong XC Machinery","kathe_hh@126.com","https://kathyxc.com/contact/"
"beverage","Zhangjiagang Mass Technology","info@masstechx.com","https://masstechx.com/contact-us/"
"packaging","Guangzhou Change Machinery","sales@gzchangemachinery.com","https://www.gzchangemachinery.com/contact_us"
"packaging","Guangzhou Huichuang Machinery","ming@huichuangjixie.cn","https://en.gzhcjixie.com/contact.html"
"beverage","Allot Tech Suzhou","sales@allottech.com","https://fillingmachinechina.com/contact/"
"packaging","Metica Machinery","sales@meticamachinery.com","https://meticamachinery.com/pages/contact-us-9"
"packaging","Shanghai Honest Machinery","info@shhonestmach.com","https://shanghaihonestmachine.com/contact/"
"pellet","Best Pellet Machinery","manager@bestpelletmachinery.com","https://www.cnfeedgranulator.com/contact-us"
"pellet","Zongtu Machinery","igotomyworld@zongtumach.com","https://www.zongtumach.com/message"
"food","Foodline Machinery","info@foodlinecn.com","https://www.foodlinecn.com/contact/"
"packaging","Hebei Lingu LINYOPACK","sales@linyopack.com","https://linyopacking.com/contact/"
"food","Xiamen Yingbo Food Machinery","sales@xmyb.com","https://www.yingbomachinery.com/contact-us_d2"
"agricultural","Leke Machinery","ning@lekemachinery.com","https://www.lekemachinery.com/contact-us"
"food","GELGOOG Machinery","sherry@machinehall.com","https://www.snackfoodm.com/contact-us/"
"beverage","Hubei Intop Machinery","keira@intopmach.com","https://www.intopmachinery.com/contact.html"
"bakery","SINOBAKE Group","info@sinobake.net","https://www.sinobake.net/contactus.html"
"grain","China Rice Mill Machinery Limited","info@chinaricemillmachinery.com","https://www.chinaricemillmachinery.com/contact/"
"beverage","Goldcheer Juice Machinery","sales2@gc-machinery.com","https://fruitjuice-machinery.com/contact/"
"bakery","Hanzun Kunshan Precision Machinery","hanzunkunshanmachinery@gmail.com","https://www.hanzun-ks.com/"
"dairy","Weishu Machinery","weishudairymachinery@weishujixie.com","https://pasteurizationmachine.com/contact-us/"
"bakery","Golden Bake Biscuit Machinery","biscuitline@126.com","https://www.foodsmachine.net/"
"grain","Changzhou Kodi Machinery","ricemill@kodichina.com","https://www.kodiricemill.com/contact-us"
"oil","Shandong Shengshi Hecheng Machinery","gavin@hydraulic-oil-press.com","https://hydraulic-oil-press.com/contact-us/"
"food","Zhengzhou Taizy Machinery","info@potatochipsprocessing.com","https://potatochipsprocessing.com/contact-us/"
"food","Lijie Food Machinery Group","sales03@lijiefoodmachinery.com","https://www.lijiegroup.com/"
"meat","Jiangsu Koray Co Ltd","info@koraymachinery.com","https://www.koraymachinery.com/contact-us.html"
"seafood","Suntok Machinery","sales@suntokmachinery.com","https://www.suntokmachinery.com/contact/"
"food","Joyshine Washing Machinery","sales@joyshinefoodmachine.com","https://www.joyshinewash.com/contact/"
"sterilization","Zhucheng Sumpot Jinding","retort@sumpot.cn","https://www.sumpot.cn/en/"
"seafood","Yuanyu Shrimp Machinery","matt@shrimpmachine.com","https://shrimpmachine.com/contact-us/"
"dairy","Wenzhou Longqiang Machinery","info@chinalongqiang.com","https://www.cnfoodmachines.com/contact.html"
"seafood","HZ Fish Processing Machinery","yudur@chinafishmachine.com","https://hzfishmachine.com/th/contact/"
"sterilization","Wogoal Food Machinery","wogoal@wogoal.cn","https://www.wogoalretort.com/"
"dairy","Shanghai Goingwind Machinery","sales@goingwind.com","https://www.goingwind.com/pages/about-us-1"
"dairy","Shuliy Machinery","info@yogurt-machine.com","https://yogurt-machine.com/contact-us/"
"sterilization","OUSI Sterilization Equipment","sales@ousi-tech.com","https://ousi-tech.com/contact-us/"
"food","Henan Baixin Machinery","Abboot@bxdryer.com","https://www.bxmachinery.com/contact-us/"
"sterilization","DTS Retort Equipment","sales@dtszb.com","https://www.dtszb.cn/"
"meat","Yuanchang Food Machinery","yc7@ycmachine.cn","https://www.ycmachine.cn/english/contact.asp"
"sterilization","Shandong Jizhong Food Machinery","sales@sdjzspjx.com","https://www.sdjzspjx.com/en/inquiry"
"recycling","SUHUI Plastic Recycling Machinery","suhui@suhuimachine.com","https://www.suhuimachine.com/contact-us/"
"plastic","Zhejiang Chaoxin Machinery","cxmachinery@zjchaoxin.com","https://www.zjchaoxin.com/contact"
"packaging","PACAKAIM Packaging Machinery","jason@packaim.com","https://packaim.com/contact/"
"plastic","JINGA Packaging Machinery","Sales@blowmoldingyue.com","https://jingaisbm.com/contact-us/"
"plastic","LIANXIN Machinery","lx@zjglx.com","https://www.lianxinmachinery.com/contact-us/"
"plastic","Chengheng Film Machinery","miranda@cnchengheng.com","https://www.cnchengheng.com/index/contact.html"
"plastic","E SHION Machine","doris@e-shionmachine.com","https://e-shion-machine.com/contact/"
"plastic","Taizhou Fupusi Machinery","bruce@taizhoufupusi.com","https://tzblowmachine.com/contact/"
"plastic","Tongda Machinery","liya@tongdamachine.com","https://www.tongdaebm.com/contact-us"
"recycling","Jiangsu Kitech Machinery","info@kitechpm.com","https://kitech-recycling.com/contact-us/"
"packaging","Boevan Packaging","marketing@boevan.cn","https://www.boevan.com/contact-us/"
"pharma","Shanghai YIQI Pharmaceutical Machinery","yiqi@topharmach.com","https://www.topharmach.com/contactus.html"
"plastic","Wuhan Changxin Plastic Machinery","maple@whcxsj.com","https://en.whcxsj.com/contact_us.html"
"water","Dongguan Qingze Environmental Technology","sales@qingzesystems.com","https://qingzesystems.com/en/contact/"
"recycling","Kailong Machinery","inquiry@klongchina.com","https://www.klongchina.com/contact-us/"
"recycling","GREENMAX Recycling","info@greenmaxrecycling.com","https://www.greenmaxrecycling.com/"
"pellet","Henan Richi Machinery","enquiry@fertilizergranulationmachine.com","https://www.fertilizergranulationmachine.com/contact-us/"
"fertilizer","GoFine Machinery","richard@zzgofine.com","https://fertilizergranulatorequipment.com/contact-gofine"
"fertilizer","Qinhuangdao Echo Automation","julia@ifertilizermachine.com","https://fertilizermachine1.com/contact-us/"
"fertilizer","Henan Jiuling Machinery","info@hnjlme.com","https://jlfertilizerproductionline.com/contact-us/"
"grain","Zhengzhou Beibo Electronics","zeeliu@beibo.com","https://www.beibo.com/en/contact/"
"pellet","Shanghai Shinmac Machinery","info@shinmachinery.com","https://shinmachinery.com/contacto.html"
"agricultural","Shanghai Chidan Technology","chidan@chidantrade.com","https://www.chidantrade.com/en/"
"grain","Xuye Grain Equipment","info@xuyemachinery.com","https://xuyeequipment.com/contact-us.html"
"grain","Shandong Unia Agricultural Machinery","petercui@uniachina.com","https://en.uniachina.com/list_104/341.html"
"grain","Zhengzhou Masely Agro Equipment","jay001@maselyagro.com","https://www.maselyagro.com/contact"
"grain","Hebei Beibu Machinery","alien@hebeibu.com","https://www.beibucleaner.com/"
"fertilizer","Henan Mingchuan Machinery","info@fertilizerproduction.com","https://fertilizerproduction.com/contact-us/"
"agricultural","Link Technology Greenhouse","info@linkdrives.com","https://www.linkdrives.com/contact-us"
"grain","Hebei Julite Sorting Technology","export@julite.com","https://www.julite.com/"
"irrigation","COD Drip Irrigation Machinery","sales@codripirrigation.com","https://www.dripirrigation.cn/"
"drying","Kemolo Freeze Dryer","sales@kemolo.com","https://www.liofilizador.com/contact/"
"sorting","Anhui RealTech Machinery","ChinaColorSorter@126.com","https://www.realtech-colorsorter.com/"
"drying","Beijing Songyuan Huaxing Biotechnology","info@bjsyhx.com.cn","https://www.freeze-dryer.cn/english/contact.html"
"dairy","Snowball Machinery","ice@hiicecream.com","https://hiicecream.com/contact.html"
"sorting","Techik Instrument Shanghai","colorsorter@techik.net","https://www.techik-colorsorter.com/"
"drying","Shanghai Jingyi Tech","info@jingyitechno.com","https://www.jingyitechno.com/contact-us"
"drying","SJ Scientific","info@sjialab.com","https://www.sjialab.com/inquiry"
"drying","LABOAO Laboratory Equipment","sales@laboao.com","https://www.lfreezedryer.com/"
"cold","Kanglong Refrigeration","sales@chinaiqffreezer.com","https://chinaiqffreezer.com/contact/"
"sorting","Anhui BIDA Optoelectronic","info@bidacolorsorter.com","https://www.potatopro.com/companies/anhui-bida-optoelectronic-technology-co-ltd"
"sorting","Hefei Pinghao Optoelectronic","sales@pinghaocolorsorter.com","https://www.pinghaocolorsorter.com/"
"drying","Zhengzhou Geliss Intelligent Equipment","info@geliss.com","https://www.geliss.com/contact-us"
"cold","Jiangnan Chengxin Refrigeration","jim@jncoldroom.com","https://jncoldroom.com/contact-us/"
"carton","Jialong Packaging Machinery","info@jialongmachine.com","https://www.icartonmachine.com/contact-us/"
"automation","X-ROBOTICS","peter@x-robotics.cn","https://x-robotics.cn/contact.php"
"paper","Makon Paper Machinery","info@makonpaper.com","https://www.makonpapermachine.com/contact"
"paper","JORI Paper Machine","info@jorimachine.com","https://www.joripaper.com/products/production-line"
"wood","Beijing Riverland Science Technology","jannyduan88@cwood.com.cn","https://www.cwood.com.cn/about-us.html"
"paper","Voril Tissue Machinery","service@voril.com","https://www.voril.com/contact.html"
"carton","AGICO Carton Machinery","info@agicomachinery.com","https://agicomachinery.com/contact-us/"
"metal","Foshan Lineng Hydraulic Machinery","sales@hydraulic-press.cn","https://www.hydraulic-press.cn/contact/"
"automation","Wuxi Aubrik ABK Machinery","Info@aubrikmc.com","https://aubrikmc.com/contact-us/"
"automation","Wuxi Zhouxiang Welding Robot","robot@wxzhouxianghi.com","https://zxweldingrobot.com/contact-us/"
"carton","Qiandeqian Carton Machinery","qdqpack@qdqmachinery.com","https://www.qdqmachinery.com/contact.html"
"paper","Foshan Meijing Machinery","admin@mjmachine.cn","https://m.chinatissuemachinery.com/contact-us"
"laser","Chinasky Laser","frank@cstlaser.com","https://www.cstechlaser.com/contact-us"
"metal","World Press","info@worldgrouppress.com","https://worldgrouppress.com/contact-us/"
"laser","JQ Laser","info@jqlaser.com","https://jqlasergroup.com/contact/"
"paper","Henan Zejiang Paper Machinery","info@zjpapermachinery.com","https://zjpapermachine.com/contact-us/"
"paper","Henan Xingtu Machinery","andy@xingtumachine.com","https://www.xingtumachine.com/about"
"paper","Foshan Mingyang Machinery","mypapermachinery@gmail.com","https://www.mypapermachinery.com/contact-us.html"
"confectionery","Chengdu LST Chocolate Equipment","lily246311443@gmail.com","https://cocoaguide.com/"
"confectionery","Shanghai SIEN Food Machinery","sien@shsienjx.com","https://www.shsienjx.com/en/pd.jsp?id=181"
"noodles","Da San Jiang Machinery","info@dasanjiang.biz","https://info.dasanjiang.biz/home"
"confectionery","Shanghai Jingyao Industrial","peter@jyindustrial.com","https://www.jingyaoindustrial.com/gummy-candy-pouring-production-line-sweet-strips-rainbow-gummy-machine-product/"
"confectionery","Shanghai Target Industry TG","mango@tgmachine.com","https://www.tgmachinetech.com/contact.html"
"coffee","Nanyang Dongyi Machinery","sales@dongyiguoji.com","https://www.dongyiguoji.com/Company.html"
"confectionery","Suzhou Lejoy Machinery","lejoymachinery@qq.com","https://www.choco-machine.com/"
"coffee","Henan Wintop Machinery","info@wintopmachinery.com","https://www.wintopmachinery.com/contact"
"coffee","Shenzhen Yetinhon Coffee Equipment","mike.wu@yetinhon.com","https://www.yetinhon.com/join-us"
"noodles","Shangjiang NoodleMachinePro","info@NoodleMachinePro.com","https://noodlemachinepro.com/contact/"
"confectionery","Fosta Group Chocolate Equipment","sales@fosta-group.com","https://www.fosta-group.com/en/"
"confectionery","Shanghai Candy Machine","yangling902@gmail.com","https://candymachine-factory.com/"
"confectionery","Ningbo MF Chocolate Machinery","info@chocolatemachinery.cn","https://www.chocolatemachinery.cn/"
"oil","Chocomach Hydraulic Oil Press","info@chocomach.com","https://www.chocooilpress.com/contact/page"
"oil","Huatai Cereals Oil Machinery","info06@cnoilmachine.com","https://www.oilpresscn.com/contact/"
"confectionery","Gusu Chocolate Machinery","stephanie@gusujx.com","https://www.gusumachinery.com/product/chocolate-machine/chocolate-tempering-machine/"
"pharma","Tabletpress Pharmaceutical Equipment","sales@tabletpressmachines.com","https://tabletpressmachines.com/contact-us.html"
"mixing","Vortex Mixing Technology","info@incmachine.com","https://incmachine.com/contacts/"
"pharma","Shanghai Universal Pharmaceutical Machinery","sales1@unipharmach.com","https://www.deeprocess.com/home/supplier/contact/id/47.html"
"beverage","As Filler Machinery","ella@asfiller.com","https://asfiller.com/contact-us/"
"biotech","Cialan Industrial Fermenters","karron@cialan.com","https://www.cialan.com/products/laboratory-equipment/bioreactor-fermenter1/pilot-scale-fermenter.html"
"pharma","Shanghai Chengxiang Machinery","kevin@chinapillpress.com","https://tabletpresscn.com/contact-us/index.htm"
"biotech","Xiamen CRTOP Machinery","allen@crtopmachine.com","https://www.crtopbioreactor.com/"
"beverage","Zhangjiagang U Tech Machine","info@utechmachine.com","https://www.utechmachine.com/contactus.html"
"mixing","Shanghai Shengli Machinery","sl@1985blender.com","https://www.1985shengli.com/contact/"
"mixing","Shuanglong Group","terry.yu@shuanglong.com","https://powder-mixer.com/"
"pulp","Richon Group","sales@richongroup.com","https://richongroup.com/contact/"
"pulp","HGHY Pulp Molding","hghy@hghuanyuan.com","https://hghyeggtraymachine.com/contact-us/"
"poultry","Maideli Chicken Farm Machinery","sales@chinachickenfarm.com","https://www.chinachickenfarm.com/contact-us/"
"grain","Shijiazhuang Hongdefa Machinery","helen@hdfmill.com","https://www.flour-mills-machine.com/"
"pulp","Rotecho Machinery","jelenagao@hotmail.com","https://www.pulpmach.com/"
"pulp","Guangzhou Nanya Pulp Molding","international@nanyaboen.com","https://www.nanyapulp.com/"
"paper","Suzhou Yideng Machinery","mail@yidengjx.com","https://www.bagsmachine.com/contact"
"poultry","YMAKO Poultry Equipment","info@ymako.com","https://ymako.com/contact/"
"pulp","Longkou Yihao Machinery","yihaocheng@yihaomachine.com.cn","https://www.yihaomachine.com/"
"poultry","Henan Xilaiya Husbandry Equipment","xilaiyavip@163.com","https://www.jilongchang.cn/en/user-col.jsp?rname=jilongdianhua"
"paper","Nanjing ZNEP Packaging","machine@cnznep.com","https://www.zneppackage.com/contact-us"
"paper","Jiangsu Nanjiang Machinery","sales@wxnanjiang.com","https://www.nanjiangmachine.com/contactus"
"poultry","Huanghua Chengxin Livestock Equipment","jimwang@cnort.com","https://www.cxlivestock.com/contact.html"
"poultry","Guangzhou Taiyang Animal Husbandry","gztaiyang@139.com","https://en.gztaiyang.com/contact.html"
"paper","Wenzhou MTED Packaging Machinery","info@mtdpack.com","https://www.mtdpack.com/contact-us/"
"grain","Henan Taixing Machinery","info@taixingmachinery.com","https://www.taixingmachinery.com/contactus/"
'''
FOCUS = {
"packaging":"automatic packing, bottling, labeling, sealing and case packing machinery",
"pellet":"feed, biomass and agricultural pellet production equipment and turnkey production lines",
"food":"industrial food preparation, washing, cutting, roasting, drying and processing lines",
"agricultural":"agricultural implements, harvesting and farm production systems",
"beverage":"juice, water, beverage preparation, filling, capping and process lines",
"bakery":"industrial biscuit, bakery, dough, oven and pastry production systems",
"grain":"grain milling, cleaning, silos, dryers and seed processing equipment",
"dairy":"milk, yoghurt, UHT, pasteurisation and dairy equipment for lawful non-alcoholic products",
"oil":"edible oil extraction, pressing, filtration and refining machinery",
"meat":"halal poultry, beef, lamb and other lawful meat-processing equipment; NO swine processing",
"seafood":"fish, shrimp and seafood processing equipment",
"sterilization":"food retort and heat sterilisation equipment for packaged foods",
"recycling":"plastic recycling sorting, washing, pelletising and reprocessing machinery",
"plastic":"blown film, thermoforming, extrusion, injection and blow moulding machinery",
"pharma":"pharmaceutical and food-grade tableting, filling and process equipment",
"water":"industrial process water treatment and purification systems",
"fertilizer":"organic and mineral fertilizer processing, mixing and granulation lines",
"irrigation":"drip irrigation line production, pipe extrusion and farm irrigation systems",
"drying":"industrial food freeze drying, vacuum drying and dehydration equipment",
"sorting":"optical sorting, food inspection and grading equipment",
"cold":"food cold-room, refrigeration, IQF and cold-storage equipment",
"carton":"corrugated cartons, box converting and packing lines",
"automation":"industrial robotic handling, welding, assembly and conveyor systems",
"paper":"paper cups, industrial paper bags, tissue and paper packaging machinery",
"wood":"wood-processing, MDF and panel-board production machinery",
"metal":"hydraulic presses, stamping, CNC metal forming equipment",
"laser":"industrial laser processing and cutting systems",
"confectionery":"chocolate, confectionery and halal candy lines excluding any porcine ingredients",
"noodles":"noodles, pasta and nonalcoholic prepared food production lines",
"coffee":"industrial coffee roasting, grinding and instant coffee production systems",
"mixing":"industrial food-grade powder mixing, blending and process machinery",
"biotech":"industrial fermentation and bioreactor equipment for lawful nonalcoholic food and biological processes",
"pulp":"moulded-pulp egg tray, paper container and fiber packaging lines",
"poultry":"poultry farming, laying systems, climate control and egg-handling machinery",
"mushroom":"commercial mushroom cultivation, substrate, sterilisation and packing systems",
"greenhouse":"controlled-environment greenhouse and hydroponic agriculture equipment",
"extrusion":"food and animal feed extrusion production lines",
"biomass":"biomass carbonisation and sustainable agricultural waste processing machinery",
}

def write_state(path, data):
    fd, tmp = tempfile.mkstemp(prefix=".mailtemp-", dir=str(path.parent), text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            os.chmod(tmp, 0o600)
            json.dump(data, out, ensure_ascii=False, indent=2, sort_keys=True)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def letter(row):
    category, company, recipient = row["category"], row["company"], row["email"]
    sector = FOCUS[category]
    msg=EmailMessage()
    msg["From"]=f"Zomorod Melal Procurement <{SENDER}>"
    msg["To"]=recipient
    msg["Reply-To"]=SENDER
    msg["Date"]=email.utils.formatdate(localtime=False,usegmt=True)
    msg["Message-ID"]=email.utils.make_msgid(domain="zomorodmelal.ir")
    msg["Subject"]=f"Zomorod Melal Iran | {company} | Complete machinery catalogue, turnkey lines, pricing and trade credit RFQ"
    body=f"""Dear {company} International Sales and Engineering Team,

On behalf of Zomorod Melal Agro-Industry Company (Iran), under CEO Mojtaba Roozegar, we are considering qualified manufacturers of industrial machinery and turnkey production lines for potential lawful procurement and long-term cooperation in Iran. We understand your specialty is: {sector}.

1. COMPLETE MANUFACTURER EQUIPMENT CATALOGUE
Please send your complete current factory-manufactured range (PDF/Excel), all models and configurations, technical specifications, production capacities, automation levels, utilities, energy consumption, dimensions, required operator count, reference factory projects, original manufacturer and production location. Distinguish machines built in your own plant from sourced/traded machines, and identify subcontractors or third-party components.

2. ITEMISED TURNKEY PRODUCTION LINE PROPOSAL
Please propose typical small, medium and large-capacity complete-line configurations that your company actually supports, including raw material handling, main process equipment, utilities, automation PLC/HMI, quality controls, packaging where relevant, installation scope, factory layout and bill of materials. Provide per-machine costs separately from integrated-line pricing, both EXW/FCA/FOB and CIF Iran ports if legally feasible. Our initial inquiry does not specify a firm capacity, project site or purchase budget: show available standard alternatives without assuming approval for a plant.

3. QUALITY, CERTIFICATION AND ACCEPTANCE
Please provide original factory business registration, ISO/CE certificates where legitimately applicable, independent references, videos of running machinery, machine drawings, operational manuals, spare-parts lists, electrical compatibility for typical Iran 380V/50Hz or customization, food-contact certificates where applicable, FAT (factory acceptance test) and SAT (site acceptance test) procedures with measurable throughput and performance guarantees. For poultry/meat and food lines, NO pig/swine or porcine-processing equipment, and no alcoholic-food projects.

4. CONTRACT, WARRANTY AND MAINTENANCE
Please specify manufacturer warranty duration and exclusions, installation and commissioning conditions, operator training (online/on-site in Iran if legally possible), engineering travel costs, annual servicing, 2-year critical spares quotation, emergency parts lead time, software/PLC access and manuals, and equipment lifetime support.

5. PAYMENT TERMS AND LEGAL EXPORT
We request your consideration of a 180-250 calendar day deferred supplier trade-credit term calculated from shipment documents, SUBJECT to commercial risk approval. If unavailable, please describe legally compliant, available export credit insurance, usance LC, bank-guarantee or staged milestone payment terms. Confirm whether your company can lawfully sell and export applicable machines to Iran, and what export-control, documentation and shipment conditions apply. No sanction circumvention is requested or authorised.

6. LONG-TERM COOPERATION
We are open to genuine authorized Iranian distributorship, service representation, spare parts cooperation, or OEM machinery made by your company with truthful identification of its actual factory and origin. Please designate an export manager to send the full catalogue and non-binding price indications.

This is a preliminary, NON-BINDING REQUEST FOR INFORMATION AND QUOTATION only. It does not constitute a purchase order, payment promise, bank guarantee, exclusive agency, or approved plant investment.

Kind regards,
International Procurement and Cooperation
On behalf of Mojtaba Roozegar, Chief Executive Officer
Zomorod Melal Agro-Industry Company, Iran
https://zomorodmelal.ir
Reply email: {SENDER}

中文摘要：伊朗 Zomorod Melal 农工公司希望了解贵司自有工厂生产的{sector}设备。请提供全部机型目录、完整生产线方案和报价、产能/能耗/布局、原厂及认证证明、FAT/SAT验收、安装培训、保修及备件、合法出口伊朗条件，并说明是否可在信用评估后考虑180–250天账期。本函仅为非约束性询价，不构成订单或付款承诺。
"""
    msg.set_content(body,charset="utf-8")
    return msg

def main():
    os.umask(0o077)
    rows=list(csv.DictReader(io.StringIO(RECIPIENT_CSV)))
    addresses=[r["email"].strip().lower() for r in rows]
    names=[r["company"].strip().lower() for r in rows]
    if len(rows)!=150 or len(set(addresses))!=150 or len(set(names))!=150:
        raise SystemExit("UNIQUE_RECIPIENT_PREFLIGHT_FAILED")
    if any(r["category"] not in FOCUS or not r["public_source_url"].startswith("https://") for r in rows):
        raise SystemExit("CATEGORY_OR_SOURCE_PREFLIGHT_FAILED")
    info=subprocess.run(["uapi","--output=json","Email","list_pops"],capture_output=True,text=True,timeout=35,check=True)
    result=json.loads(info.stdout).get("result",{})
    known={str(x.get("email","")).lower() for x in (result.get("data") or []) if isinstance(x,dict)}
    if result.get("status")!=1 or SENDER not in known:
        raise SystemExit("COMPANY_SENDER_MAILBOX_NOT_OWNED")
    if not Path("/usr/sbin/sendmail").exists():
        raise SystemExit("LOCAL_EXIM_SENDMAIL_MISSING")
    private=Path.home()/".company-outreach-private"
    private.mkdir(mode=0o700,parents=True,exist_ok=True)
    private.chmod(0o700)
    ledger=private/(CAMPAIGN+".json")
    lock=private/(CAMPAIGN+".lock")
    with lock.open("a+") as fh:
        os.chmod(lock,0o600)
        fcntl.flock(fh,fcntl.LOCK_EX)
        state=json.loads(ledger.read_text(encoding="utf-8")) if ledger.exists() else {"campaign":CAMPAIGN,"sender":SENDER,"entries":{}}
        print("CAMPAIGN="+CAMPAIGN,flush=True)
        print("EXPECTED_RECIPIENTS=150",flush=True)
        for idx,row in enumerate(rows,1):
            email=row["email"].lower()
            if email in state["entries"]:
                print(f"RECIPIENT_{idx:03d}=ALREADY_ATTEMPTED",flush=True)
                continue
            msg=letter(row)
            state["entries"][email]={"category":row["category"],"company":row["company"],"source":row["public_source_url"],"status":"attempt_started","message_id":str(msg["Message-ID"])}
            write_state(ledger,state)
            try:
                result=subprocess.run(["/usr/sbin/sendmail","-t","-i","-f",SENDER],input=msg.as_bytes(),capture_output=True,timeout=35)
                state["entries"][email]["status"]="accepted_by_local_exim" if result.returncode==0 else "mail_submission_failed"
                state["entries"][email]["exit_code"]=result.returncode
            except Exception as error:
                state["entries"][email]["status"]="submission_exception"
                state["entries"][email]["error_type"]=type(error).__name__
            write_state(ledger,state)
            print(f"RECIPIENT_{idx:03d}={row['category']}:{state['entries'][email]['status']}",flush=True)
            if idx<150:
                time.sleep(4)
        accepted=sum(v["status"]=="accepted_by_local_exim" for v in state["entries"].values())
        print("SUBMITTED_TO_EXIM="+str(accepted),flush=True)
        print("NOT_CONFIRMED_OR_FAILED="+str(len(rows)-accepted),flush=True)
        print("REMOTE_MAILBOX_DELIVERY_AND_REPLY_NOT_VERIFIED",flush=True)
        if accepted!=150:
            raise SystemExit(2)

if __name__=="__main__":
    main()
