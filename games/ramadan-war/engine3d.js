import * as THREE from './three.module.js';
import { GLTFLoader } from './three-addons/loaders/GLTFLoader.js';
import * as SkeletonUtils from './three-addons/utils/SkeletonUtils.js';
import { MeshoptDecoder } from './three-addons/libs/meshopt_decoder.module.js';

export function createEngine(canvas) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha:true, powerPreference: 'high-performance' });
  const glContext=renderer.getContext(),gpuName=String(glContext.getParameter(glContext.RENDERER)||'');
  const softwareRenderer=/swiftshader|llvmpipe|softpipe/i.test(gpuName);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.setClearColor(0x000000,0);
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.12;
  renderer.shadowMap.enabled = !softwareRenderer;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;

  const camera = new THREE.PerspectiveCamera(68, 1, .08, 160);
  const mats = {
    stone: new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: .94 }),
    trim: new THREE.MeshStandardMaterial({ color: 0xb5a88e, roughness: .82 }),
    metal: new THREE.MeshStandardMaterial({ color: 0x293534, metalness: .68, roughness: .38 }),
    black: new THREE.MeshStandardMaterial({ color: 0x182321, roughness: .92 }),
    armor: new THREE.MeshStandardMaterial({ color: 0x303a33, metalness: .18, roughness: .78 }),
    gear: new THREE.MeshStandardMaterial({ color: 0x716044, roughness: .92 }),
    uniform: [0x536454, 0x74674d, 0x4b5e60].map(color => new THREE.MeshStandardMaterial({ color, roughness: .9 })),
    skin: new THREE.MeshStandardMaterial({ color: 0x9b8067, roughness: .88 }),
    crate: new THREE.MeshStandardMaterial({ color: 0x6e593c, roughness: .9 }),
    rock: new THREE.MeshStandardMaterial({ color: 0x716b60, roughness: 1 }),
  };
  const sharedMaterials=new Set(Object.values(mats).flat()),assetMaterials=new Set(),assetGeometries=new Set();
  let scene = new THREE.Scene();
  const enemies = new Map(), missiles = new Map(), hostileShots = new Map(), impacts = new Map(), pickups = new Map();
  const soldierMap = new THREE.TextureLoader().load('./soldier-enemy.webp');
  soldierMap.colorSpace = THREE.SRGBColorSpace; soldierMap.anisotropy = Math.min(4,renderer.capabilities.getMaxAnisotropy());
  const soldierMaterial = new THREE.SpriteMaterial({ map:soldierMap, transparent:true, alphaTest:.045, depthWrite:false, toneMapped:false });
  const tracerMat=new THREE.MeshBasicMaterial({color:0xffc36a,toneMapped:false}),tracerCoreMat=new THREE.MeshBasicMaterial({color:0xff7959,toneMapped:false});
  const tracerGeo=new THREE.CylinderGeometry(.012,.025,.58,6),tracerCoreGeo=new THREE.SphereGeometry(.035,7,6);
  const impactRingGeo=new THREE.TorusGeometry(.12,.018,5,16),impactDotGeo=new THREE.SphereGeometry(.045,7,6);
  const sharedGeometries=new Set([tracerGeo,tracerCoreGeo,impactRingGeo,impactDotGeo]);
  sharedMaterials.add(soldierMaterial);sharedMaterials.add(tracerMat);sharedMaterials.add(tracerCoreMat);
  function disposeBranch(root){root?.traverse(o=>{if(o.geometry&&!sharedGeometries.has(o.geometry)&&!assetGeometries.has(o.geometry))o.geometry.dispose();const list=Array.isArray(o.material)?o.material:o.material?[o.material]:[];for(const m of list)if(!sharedMaterials.has(m)&&!assetMaterials.has(m))m.dispose()})}
  const loader = new GLTFLoader();loader.setMeshoptDecoder(MeshoptDecoder);
  let soldierAsset = null, weaponAsset = null, assetReady = { soldier:false, weapon:false };
  loader.load('./soldier-rigged-ccby.glb', gltf => { soldierAsset = gltf;gltf.scene.traverse(o=>{if(o.geometry)assetGeometries.add(o.geometry);if(o.material)(Array.isArray(o.material)?o.material:[o.material]).forEach(m=>assetMaterials.add(m))}); assetReady.soldier = true; if(world) world.enemies.forEach(e => upgradeEnemy(e)); }, undefined, err => console.warn('Soldier model unavailable; using fallback', err));
  loader.load('./m24-sniper-ccby.glb', gltf => {
    weaponAsset = gltf.scene;
    weaponAsset.traverse(o => {if(o.geometry)assetGeometries.add(o.geometry);if(o.material)(Array.isArray(o.material)?o.material:[o.material]).forEach(m=>assetMaterials.add(m)); if(o.isMesh){ o.castShadow = true; o.receiveShadow = true; if(o.material){ o.material.side = THREE.DoubleSide; } } });
    assetReady.weapon = true;
    if(weapon?.g) installWeaponModel(weapon);
    document.querySelector('#game')?.classList.add('model-weapon-loaded');
  }, undefined, err => console.warn('Sniper model unavailable; using fallback', err));
  let world = null, pitch = 0, time = 0, baseFov = 68, scoped = false, missionMarker=null;
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const hitColor=new THREE.Color(0xff4939);
  function disposeEnemy(g){if(!g)return;for(const x of g.userData.materials||[])x.material.dispose();for(const child of g.children){if(child===g.userData.model)continue;child.geometry?.dispose();if(child.material&&child.material!==soldierMaterial)child.material.dispose()}}

  function texture(kind) {
    const c = document.createElement('canvas'); c.width = c.height = 512;
    const x = c.getContext('2d');
    if (kind === 'sand') {
      x.fillStyle = '#89785e'; x.fillRect(0, 0, 512, 512);
      for (let i = 0; i < 10000; i++) {
        x.fillStyle = Math.random() < .5 ? 'rgba(36,32,24,.13)' : 'rgba(233,215,174,.15)';
        x.fillRect(Math.random()*512, Math.random()*512, 1+Math.random()*3, 1+Math.random()*2);
      }
      for (let i = 0; i < 90; i++) { x.strokeStyle='rgba(37,31,23,.13)'; x.beginPath(); const a=Math.random()*512,b=Math.random()*512; x.moveTo(a,b);x.lineTo(a+Math.random()*36-18,b+Math.random()*7);x.stroke(); }
    } else {
      x.fillStyle='#b9b6a8';x.fillRect(0,0,512,512);
      const colors=['#c4c0b2','#aaa99f','#b8b4a9','#d0c8b9'];
      for(let y=0;y<512;y+=38)for(let xx=-56;xx<568;xx+=112){const a=xx+(Math.floor(y/38)%2)*56+Math.random()*7,b=y+Math.random()*4;x.fillStyle=colors[Math.floor(Math.random()*colors.length)];x.fillRect(a+1,b+1,108,34);x.strokeStyle='rgba(38,42,42,.28)';x.strokeRect(a+1,b+1,108,34);}
      for(let i=0;i<3000;i++){x.fillStyle='rgba(38,39,34,.07)';x.fillRect(Math.random()*512,Math.random()*512,1,1);}
    }
    const t=new THREE.CanvasTexture(c);t.wrapS=t.wrapT=THREE.RepeatWrapping;t.colorSpace=THREE.SRGBColorSpace;t.anisotropy=Math.min(4,renderer.capabilities.getMaxAnisotropy());t.repeat.set(kind==='sand'?12:1,kind==='sand'?12:1);return t;
  }
  const stoneTexture=new THREE.TextureLoader().load('./stone-wall.webp');stoneTexture.colorSpace=THREE.SRGBColorSpace;stoneTexture.wrapS=stoneTexture.wrapT=THREE.RepeatWrapping;stoneTexture.repeat.set(1,3);stoneTexture.anisotropy=Math.min(8,renderer.capabilities.getMaxAnisotropy());
  const levelTextures = { sand:texture('sand'), stone:stoneTexture };

  function box(parent, geo, mat, pos, size) {
    const m=new THREE.Mesh(geo,mat);m.position.set(...pos);if(size)m.scale.set(...size);m.castShadow=true;m.receiveShadow=true;parent.add(m);return m;
  }

  function makeWeapon() {
    const g=new THREE.Group();camera.add(g);
    box(g,new THREE.BoxGeometry(.23,.17,.56),mats.metal,[.22,-.19,-.47]);
    box(g,new THREE.BoxGeometry(.14,.15,.32),mats.black,[.15,-.19,-.08]);
    const barrel=new THREE.Mesh(new THREE.CylinderGeometry(.026,.033,.66,12),mats.metal);barrel.rotation.x=Math.PI/2;barrel.position.set(.22,-.145,-.93);g.add(barrel);
    box(g,new THREE.BoxGeometry(.13,.24,.12),mats.black,[.23,-.36,-.42]);
    const mag=box(g,new THREE.BoxGeometry(.105,.23,.14),mats.black,[.22,-.37,-.47]);mag.rotation.x=-.14;
    const scope=new THREE.Mesh(new THREE.CylinderGeometry(.055,.055,.29,16),mats.metal);scope.rotation.x=Math.PI/2;scope.position.set(.22,-.055,-.43);g.add(scope);
    for(const z of [-.32,-.54]){const ring=new THREE.Mesh(new THREE.CylinderGeometry(.068,.068,.025,16),mats.metal);ring.rotation.x=Math.PI/2;ring.position.set(.22,-.055,z);g.add(ring);}
    box(g,new THREE.BoxGeometry(.27,.027,.22),mats.black,[.22,-.1,-.48]);
    const glove=new THREE.MeshStandardMaterial({color:0x35423b,roughness:.96});
    box(g,new THREE.BoxGeometry(.16,.12,.17),glove,[.06,-.27,-.68]);
    box(g,new THREE.BoxGeometry(.24,.25,.28),new THREE.MeshStandardMaterial({color:0x596455,roughness:1}),[.4,-.48,-.37]);
    const flash=new THREE.PointLight(0xffb34e,0,3);flash.position.set(.22,-.145,-1.2);g.add(flash);
    g.position.set(.12,-.52,-.7);g.visible=true;return {g,flash,model:null};
  }

  function installWeaponModel(wp) {
    if (!weaponAsset || !wp?.g || wp.model) return;
    const model = SkeletonUtils.clone(weaponAsset);
    model.scale.setScalar(.68);
    // Keep the authored hip anchor [0.21, -0.12, -0.40] after the group's runtime offset.
    model.position.set(.09,.40,.30);
    model.rotation.set(.03,.08,-.15);
    wp.flash.position.set(.09,.48,-1.12);
    model.traverse(o => { if(o.isMesh){ o.castShadow = true; o.receiveShadow = true; } });
    wp.g.add(model); wp.model = model;
    // Hide only the procedural fallback. Keep the flash light attached to the weapon group.
    for (const child of [...wp.g.children]) if (child !== model && child !== wp.flash) child.visible = false;
  }

  let weapon=makeWeapon();

  function setSize(w,h,dpr){renderer.setPixelRatio(softwareRenderer?Math.min(dpr,.78):dpr);renderer.setSize(w,h,false);camera.aspect=w/Math.max(h,1);camera.updateProjectionMatrix();}

  function build(w, tileFn) {
    world=w;pitch=0;
    if(weapon?.g){for(const child of weapon.g.children)if(child!==weapon.model)disposeBranch(child);camera.remove(weapon.g)}
    for(const child of [...scene.children])if(child!==camera){scene.remove(child);disposeBranch(child)}
    enemies.clear();missiles.clear();hostileShots.clear();impacts.clear();pickups.clear();
    scene=new THREE.Scene();
    // In-world objective beacon provides a real navigational target in the 3D arena.
    missionMarker=new THREE.Group();
    const beaconMat=new THREE.MeshBasicMaterial({color:0x68ffd0,transparent:true,opacity:.48,depthWrite:false,toneMapped:false});
    const beaconColumn=new THREE.Mesh(new THREE.CylinderGeometry(.10,.28,2.7,12,1,true),beaconMat);
    beaconColumn.position.y=1.48;missionMarker.add(beaconColumn);
    const beaconRing=new THREE.Mesh(new THREE.TorusGeometry(.66,.05,8,36),new THREE.MeshBasicMaterial({color:0xfce19e,toneMapped:false}));
    beaconRing.rotation.x=Math.PI/2;beaconRing.position.y=.18;missionMarker.add(beaconRing);
    const tip=new THREE.Mesh(new THREE.OctahedronGeometry(.24),new THREE.MeshBasicMaterial({color:0x92fff0,toneMapped:false}));
    tip.position.y=3.12;missionMarker.add(tip);
    missionMarker.visible=false;scene.add(missionMarker);
    const horizonColor=new THREE.Color(w.mission%3===1?0x788590:0xa89b84);
    scene.background=null;scene.fog=new THREE.Fog(horizonColor,36,68);scene.add(camera);
    const hemi=new THREE.HemisphereLight(0xdce6eb,0x514638,2.05);scene.add(hemi);
    const sun=new THREE.DirectionalLight(w.mission%3===1?0x99b9d0:0xffddb0,2.7);sun.position.set(-8,16,-10);sun.castShadow=true;sun.shadow.mapSize.set(1024,1024);sun.shadow.camera.left=-22;sun.shadow.camera.right=22;sun.shadow.camera.top=22;sun.shadow.camera.bottom=-22;scene.add(sun);
    // Build the playable arena in WebGL from the same collision grid used by the game.
    const sandTex=levelTextures.sand, stoneTex=levelTextures.stone;
    const floorMat=new THREE.MeshStandardMaterial({map:sandTex,color:w.mission%3===1?0x89909a:0xffffff,roughness:1});
    const wallMat=new THREE.MeshStandardMaterial({map:stoneTex,color:w.mission%3===1?0xb4bdc4:0xffffff,roughness:.96});
    const floor=new THREE.Mesh(new THREE.PlaneGeometry(100,100),floorMat);floor.rotation.x=-Math.PI/2;floor.position.set(8,-.06,8);floor.receiveShadow=true;scene.add(floor);
    const wallPositions=[];
    const coverCells=new Set(['3,3','12,3','3,11','5,7','10,6','5,4','12,5','4,10','12,10']);
    for(let z=0;z<16;z++)for(let x=0;x<16;x++)if(tileFn(x,z,w.mission)&&!coverCells.has(`${x},${z}`))wallPositions.push([x+.5,1.62,z+.5]);
    const wallMesh=new THREE.InstancedMesh(new THREE.BoxGeometry(1,3.25,1),wallMat,wallPositions.length);wallMesh.castShadow=wallMesh.receiveShadow=true;
    const capMesh=new THREE.InstancedMesh(new THREE.BoxGeometry(1.08,.12,1.08),mats.trim,wallPositions.length);capMesh.castShadow=false;capMesh.receiveShadow=true;
    const dummy=new THREE.Object3D();wallPositions.forEach(([x,,z],i)=>{dummy.position.set(x,1.62,z);dummy.updateMatrix();wallMesh.setMatrixAt(i,dummy.matrix);dummy.position.y=3.25;dummy.updateMatrix();capMesh.setMatrixAt(i,dummy.matrix);});scene.add(wallMesh,capMesh);
    for(const [x,z] of [[-1,1],[17,1],[-1,15],[17,15]]){const tower=box(scene,new THREE.CylinderGeometry(1.05,1.3,4,10),wallMat,[x,2,z]);tower.castShadow=true;const roof=box(scene,new THREE.ConeGeometry(1.24,.72,10),mats.trim,[x,4.35,z]);roof.castShadow=true;}
    for(let i=0;i<38;i++){const a=Math.random()*Math.PI*2,r=9+Math.random()*12,x=8+Math.cos(a)*r,z=8+Math.sin(a)*r;if(Math.abs(x)<17&&Math.abs(z)<17)continue;const rock=new THREE.Mesh(new THREE.DodecahedronGeometry(.28+Math.random()*.9,0),mats.rock);rock.position.set(x,-.04+Math.random()*.1,z);rock.scale.y=.35+Math.random()*.55;rock.rotation.set(Math.random(),Math.random(),Math.random());rock.castShadow=true;scene.add(rock);}
    const hills=new THREE.MeshStandardMaterial({color:w.mission%3===1?0x586774:0x736b5c,roughness:1});for(let i=0;i<16;i++){const a=i/16*Math.PI*2,r=31+Math.random()*7,height=8+Math.random()*14,hill=new THREE.Mesh(new THREE.ConeGeometry(5+Math.random()*6,height,7),hills);hill.position.set(8+Math.cos(a)*r,height/2-1,8+Math.sin(a)*r);hill.rotation.y=Math.random();scene.add(hill);}
    for(const [x,z]of [[3.5,3.5],[12.5,3.5],[3.5,11.5],[5.5,7.5],[10.5,6.5]]){const crate=box(scene,new THREE.BoxGeometry(.85,.7,.85),mats.crate,[x,.35,z]);crate.rotation.y=.08;for(let k=-1;k<=1;k++)box(scene,new THREE.BoxGeometry(.055,.72,.88),mats.trim,[x+k*.27,.35,z]);}
    // Industrial floodlights and field barriers give the lanes readable depth and cover.
    const poleMat=new THREE.MeshStandardMaterial({color:0x323a3b,metalness:.62,roughness:.42});
    for(const [x,z] of [[2.2,5.5],[13.8,5.5],[2.2,10.5],[13.8,10.5]]){const pole=box(scene,new THREE.CylinderGeometry(.045,.075,4.8,8),poleMat,[x,2.4,z]);pole.castShadow=true;const arm=box(scene,new THREE.BoxGeometry(.72,.075,.075),poleMat,[x,4.65,z]);arm.rotation.z=x<8?.12:-.12;const lamp=box(scene,new THREE.BoxGeometry(.3,.14,.24),new THREE.MeshStandardMaterial({color:0xffe4a8,emissive:0xffb54a,emissiveIntensity:.6}),[x,4.58,z]);const glow=new THREE.PointLight(w.mission%3===1?0x84baff:0xffbd66,1.3,7);glow.position.set(x,4.45,z);scene.add(glow);}
    const barrierMat=new THREE.MeshStandardMaterial({color:0x8e8778,roughness:.94});
    for(const [x,z,rot] of [[5.5,4.5,.18],[12.5,5.5,-.18],[4.5,10.5,-.22],[12.5,10.5,.22]]){const b=box(scene,new THREE.BoxGeometry(1.65,.62,.48),barrierMat,[x,.31,z]);b.rotation.y=rot;const stripe=box(scene,new THREE.BoxGeometry(.42,.64,.018),new THREE.MeshStandardMaterial({color:0xc59d4a,roughness:.8}),[x,.31,z+.246]);stripe.rotation.y=rot;}
    baseFov=w.hero%6===1?48:68;scoped=false;camera.fov=baseFov;camera.updateProjectionMatrix();weapon=makeWeapon();installWeaponModel(weapon);
    camera.position.set(w.x,1.62,w.y);camera.rotation.order='YXZ';camera.rotation.y=w.angle-Math.PI/2;camera.rotation.x=0;
    document.querySelector('#game')?.classList.add('three-world-ready');
  }

  function enemy(e) {
    const g=new THREE.Group();
    const soldier=new THREE.Sprite(soldierMaterial);soldier.scale.set(1.48,2.22,1);soldier.position.y=1.08;g.add(soldier);
    const barMat=new THREE.MeshBasicMaterial({color:0x17211e,transparent:true,opacity:.88,depthTest:false});
    const fillMat=new THREE.MeshBasicMaterial({color:0xf0715c,depthTest:false});
    const bar=new THREE.Mesh(new THREE.PlaneGeometry(.62,.055),barMat);bar.position.set(0,2.24,0);bar.renderOrder=4;g.add(bar);
    const fill=new THREE.Mesh(new THREE.PlaneGeometry(.58,.034),fillMat);fill.position.set(0,2.24,.002);fill.renderOrder=5;fill.userData.hp=true;g.add(fill);
    const shadow=new THREE.Mesh(new THREE.CircleGeometry(.38,20),new THREE.MeshBasicMaterial({color:0x1a1710,transparent:true,opacity:.3,depthWrite:false}));shadow.rotation.x=-Math.PI/2;shadow.position.y=.012;g.add(shadow);
    g.userData.sprite=soldier; g.userData.mixer=null; g.userData.model=null;
    scene.add(g);enemies.set(e,g);upgradeEnemy(e);return g;
  }

  function upgradeEnemy(e) {
    const g=enemies.get(e); if(!g||!soldierAsset||g.userData.model)return;
    const model=SkeletonUtils.clone(soldierAsset.scene);
    model.scale.setScalar(e.type===3?1.16:1);
    const materials=[];
    model.traverse(o=>{if(o.isMesh){o.castShadow=true;o.receiveShadow=true;if(o.material){o.material=Array.isArray(o.material)?o.material.map(m=>m.clone()):o.material.clone();for(const m of (Array.isArray(o.material)?o.material:[o.material])){m.side=THREE.DoubleSide;if(m.emissive)materials.push({material:m,base:m.emissive.clone()})}}}});
    g.add(model);g.userData.model=model;
    g.userData.materials=materials;
    if(g.userData.sprite){g.remove(g.userData.sprite);g.userData.sprite=null;}
    const clips=soldierAsset.animations;
    const idleClip=clips.find(a=>a.name==='aim_idle')||clips.find(a=>a.name==='idle');
    const walkClip=clips.find(a=>a.name==='aim_walk')||clips.find(a=>a.name==='walk')||clips.find(a=>a.name==='run');
    if(idleClip){const mixer=new THREE.AnimationMixer(model),idle=mixer.clipAction(idleClip);idle.play();let walk=null;if(walkClip){walk=mixer.clipAction(walkClip);walk.play();walk.setEffectiveWeight(0)}g.userData.mixer=mixer;g.userData.actions={idle,walk,current:idle};}
  }

  let lastRenderTime=0,lastDrawTime=0;
  function render(w,ts){if(w)world=w;if(!world)return;w=world;time=ts/1000;if(softwareRenderer&&ts-lastDrawTime<32)return;lastDrawTime=ts;const dt=Math.min(.05,Math.max(0,time-lastRenderTime));lastRenderTime=time;camera.position.set(w.x,1.62+Math.sin(time*8)*.012,w.y);camera.rotation.order='YXZ';camera.rotation.y=w.angle-Math.PI/2;camera.rotation.x=pitch;weapon.g.visible=true;weapon.g.position.x=.12+Math.sin(time*7)*.008;weapon.g.position.y=-.52+Math.sin(time*14)*.008-(w.recoil>0?.035:0);weapon.g.position.z=-.7+(w.recoil>0?.12:0);weapon.g.rotation.z=Math.sin(time*7)*.008;weapon.flash.intensity=w.muzzle>0?16:0;if(scoped&&weapon.model)weapon.model.visible=false;else if(weapon.model)weapon.model.visible=true;
    if(missionMarker){missionMarker.visible=!!w.marker;if(w.marker){missionMarker.position.set(w.marker.x,0,w.marker.y);missionMarker.children[1].rotation.z=time*.6;missionMarker.children[2].position.y=3.12+Math.sin(time*3)*.22;}}
    for(const [e,g]of [...enemies])if(!w.enemies.includes(e)){scene.remove(g);disposeEnemy(g);enemies.delete(e);}
    for(const e of w.enemies){const g=enemies.get(e)||enemy(e);g.position.set(e.x,0,e.y);g.rotation.y=Math.atan2(w.x-e.x,-(w.y-e.y));if(g.userData.mixer){const actions=g.userData.actions,desired=e.moving&&actions.walk?actions.walk:actions.idle;if(desired!==actions.current){desired.reset();desired.crossFadeFrom(actions.current,.24,false);desired.play();actions.current=desired}g.userData.mixer.update(dt)}const flash=Math.max(0,Math.min(1,(e.hit||0)/.18));for(const entry of g.userData.materials||[])if(entry.material.emissive)entry.material.emissive.copy(entry.base).lerp(hitColor,flash);for(const o of g.children)if(o.userData.hp)o.scale.x=.06+clamp(e.hp/e.max,0,1);}
    for(const [m,o]of [...missiles])if(!w.missiles.includes(m)){scene.remove(o);disposeBranch(o);missiles.delete(m);}
    for(const m of w.missiles){let o=missiles.get(m);if(!o){o=new THREE.Group();const body=new THREE.Mesh(new THREE.CylinderGeometry(.045,.09,.48,10),new THREE.MeshStandardMaterial({color:0xd3cfbd,metalness:.5,roughness:.38,emissive:0x31190c}));body.rotation.x=Math.PI/2;o.add(body);o.add(new THREE.PointLight(0xff7136,2,3));scene.add(o);missiles.set(m,o);}o.position.set(m.x,1.1,m.y);o.rotation.y=Math.atan2(m.vx,m.vy);}
    const hostile=w.hostile||[];
    for(const [b,o]of [...hostileShots])if(!hostile.includes(b)){scene.remove(o);disposeBranch(o);hostileShots.delete(b);}
    for(const b of hostile){let o=hostileShots.get(b);if(!o){o=new THREE.Group();const tracer=new THREE.Mesh(tracerGeo,tracerMat);tracer.rotation.x=Math.PI/2;tracer.position.z=-.16;o.add(tracer);const core=new THREE.Mesh(tracerCoreGeo,tracerCoreMat);o.add(core);scene.add(o);hostileShots.set(b,o);}o.position.set(b.x,1.35,b.y);const dir=new THREE.Vector3(b.vx,0,b.vy).normalize();o.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),dir);}
    for(const i of (w.impacts||[])){let o=impacts.get(i);if(!o){o=new THREE.Group();const mat=new THREE.MeshBasicMaterial({color:i.type==='head'?0xffe7a5:0x8ce9ce,transparent:true,opacity:.95,toneMapped:false,depthWrite:false});const ring=new THREE.Mesh(impactRingGeo,mat);o.add(ring);const dot=new THREE.Mesh(impactDotGeo,mat);o.add(dot);scene.add(o);impacts.set(i,o);}o.position.set(i.x,i.height||1.1,i.y);o.scale.setScalar(1+(.25-Math.min(.25,i.life||0))*3);for(const child of o.children)child.material.opacity=Math.max(0,Math.min(1,(i.life||0)*5));}
    for(const [i,o]of [...impacts])if(!(w.impacts||[]).includes(i)){scene.remove(o);disposeBranch(o);impacts.delete(i);}
    for(const [p,o]of [...pickups])if(!(w.pickups||[]).includes(p)){scene.remove(o);disposeBranch(o);pickups.delete(p)}
    for(const p of w.pickups||[]){let o=pickups.get(p);if(!o){o=new THREE.Group();const color=p.type==='health'?0x5cffb2:p.type==='ammo'?0xffbd53:0x7bdcff;const glow=new THREE.MeshStandardMaterial({color,emissive:color,emissiveIntensity:.7,metalness:.2,roughness:.32});const core=new THREE.Mesh(p.type==='health'?new THREE.OctahedronGeometry(.22,1):new THREE.BoxGeometry(.26,.2,.18),glow);core.position.y=.38;core.castShadow=true;o.add(core);const ring=new THREE.Mesh(new THREE.TorusGeometry(.33,.025,5,24),new THREE.MeshBasicMaterial({color,transparent:true,opacity:.8,toneMapped:false}));ring.rotation.x=Math.PI/2;ring.position.y=.08;o.add(ring);o.add(new THREE.PointLight(color,1.6,3));scene.add(o);pickups.set(p,o)}o.position.set(p.x,Math.sin(time*3+p.x)*.07,p.y);o.rotation.y=time*.8}
    renderer.render(scene,camera);
  }

  return {setSize,build,render,look(dx,dy,w){pitch=clamp(pitch-dy*(w<700?.004:.0025),-.55,.55);},pitch(){return pitch;},scope(on){scoped=on;camera.fov=on?28:baseFov;camera.updateProjectionMatrix();return scoped;},stats(){return {renderer:'webgl-threejs',enemies:enemies.size,hostileShots:hostileShots.size,pickups:pickups.size,world:'3d',soldierModel:assetReady.soldier,weaponModel:assetReady.weapon};}};
}
