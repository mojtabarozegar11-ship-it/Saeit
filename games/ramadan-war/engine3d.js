import * as THREE from './three.module.js';

export function createEngine(canvas) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha:true, powerPreference: 'high-performance' });
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.setClearColor(0x000000,0);
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.12;
  renderer.shadowMap.enabled = true;
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
  let scene = new THREE.Scene();
  const enemies = new Map(), missiles = new Map();
  const soldierMap = new THREE.TextureLoader().load('./soldier-enemy.webp');
  soldierMap.colorSpace = THREE.SRGBColorSpace; soldierMap.anisotropy = Math.min(4,renderer.capabilities.getMaxAnisotropy());
  const soldierMaterial = new THREE.SpriteMaterial({ map:soldierMap, transparent:true, alphaTest:.045, depthWrite:false, toneMapped:false });
  let world = null, pitch = 0, time = 0, baseFov = 68, scoped = false;
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

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
    g.position.set(.12,-.52,-.7);g.visible=false;return {g,flash};
  }

  let weapon=makeWeapon();

  function setSize(w,h,dpr){renderer.setPixelRatio(dpr);renderer.setSize(w,h,false);camera.aspect=w/Math.max(h,1);camera.updateProjectionMatrix();}

  function build(w, tileFn) {
    world=w;pitch=0;enemies.clear();missiles.clear();
    if(weapon?.g)camera.remove(weapon.g);
    scene=new THREE.Scene();scene.background=null;scene.fog=null;scene.add(camera);
    baseFov=w.hero%6===1?48:68;scoped=false;camera.fov=baseFov;camera.updateProjectionMatrix();weapon=makeWeapon();
    camera.position.set(w.x,1.62,w.y);camera.rotation.order='YXZ';camera.rotation.y=w.angle-Math.PI/2;camera.rotation.x=0;weapon.g.visible=false;
  }

  function enemy(e) {
    const g=new THREE.Group();
    const soldier=new THREE.Sprite(soldierMaterial);soldier.scale.set(1.48,2.22,1);soldier.position.y=1.08;g.add(soldier);
    const barMat=new THREE.MeshBasicMaterial({color:0x17211e,transparent:true,opacity:.88,depthTest:false});
    const fillMat=new THREE.MeshBasicMaterial({color:0xf0715c,depthTest:false});
    const bar=new THREE.Mesh(new THREE.PlaneGeometry(.62,.055),barMat);bar.position.set(0,2.24,0);bar.renderOrder=4;g.add(bar);
    const fill=new THREE.Mesh(new THREE.PlaneGeometry(.58,.034),fillMat);fill.position.set(0,2.24,.002);fill.renderOrder=5;fill.userData.hp=true;g.add(fill);
    const shadow=new THREE.Mesh(new THREE.CircleGeometry(.38,20),new THREE.MeshBasicMaterial({color:0x1a1710,transparent:true,opacity:.3,depthWrite:false}));shadow.rotation.x=-Math.PI/2;shadow.position.y=.012;g.add(shadow);
    scene.add(g);enemies.set(e,g);return g;
  }

  function render(w,ts){if(w)world=w;if(!world)return;w=world;time=ts/1000;camera.position.set(w.x,1.62+Math.sin(time*8)*.012,w.y);camera.rotation.order='YXZ';camera.rotation.y=w.angle-Math.PI/2;camera.rotation.x=pitch;weapon.g.visible=false;weapon.g.position.x=.12+Math.sin(time*7)*.008;weapon.g.position.y=-.52+Math.sin(time*14)*.008-(w.muzzle>0?.025:0);weapon.g.position.z=-.7;weapon.g.rotation.z=Math.sin(time*7)*.008;weapon.flash.intensity=w.muzzle>0?14:0;
    for(const [e,g]of [...enemies])if(!w.enemies.includes(e)){scene.remove(g);enemies.delete(e);}
    for(const e of w.enemies){const g=enemies.get(e)||enemy(e);g.position.set(e.x,0,e.y);g.rotation.y=Math.atan2(w.x-e.x,-(w.y-e.y));for(const o of g.children)if(o.userData.hp)o.scale.x=.06+clamp(e.hp/e.max,0,1);}
    for(const [m,o]of [...missiles])if(!w.missiles.includes(m)){scene.remove(o);missiles.delete(m);}
    for(const m of w.missiles){let o=missiles.get(m);if(!o){o=new THREE.Group();const body=new THREE.Mesh(new THREE.CylinderGeometry(.045,.09,.48,10),new THREE.MeshStandardMaterial({color:0xd3cfbd,metalness:.5,roughness:.38,emissive:0x31190c}));body.rotation.x=Math.PI/2;o.add(body);o.add(new THREE.PointLight(0xff7136,2,3));scene.add(o);missiles.set(m,o);}o.position.set(m.x,1.1,m.y);o.rotation.y=Math.atan2(m.vx,m.vy);}
    renderer.render(scene,camera);
  }

  return {setSize,build,render,look(dx,dy,w){pitch=clamp(pitch+dy*(w<700?.004:.0025),-.42,.42);},scope(on){scoped=on;camera.fov=on?28:baseFov;camera.updateProjectionMatrix();return scoped;},stats(){return {renderer:'webgl-threejs',enemies:enemies.size};}};
}
