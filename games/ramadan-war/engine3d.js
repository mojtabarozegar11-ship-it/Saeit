import * as THREE from './three.module.js';

export function createEngine(canvas) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' });
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.12;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;

  const camera = new THREE.PerspectiveCamera(68, 1, .08, 160);
  const mats = {
    stone: new THREE.MeshStandardMaterial({ color: 0xe3dfd1, roughness: .9 }),
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
    scene=new THREE.Scene();scene.background=new THREE.Color(0x91a7ae);scene.fog=new THREE.FogExp2(0x9aa7a3,.008);scene.add(camera);
    baseFov=w.hero%6===1?48:68;scoped=false;camera.fov=baseFov;camera.updateProjectionMatrix();weapon=makeWeapon();
    scene.add(new THREE.HemisphereLight(0xe0efff,0x75614c,1.45));
    const sun=new THREE.DirectionalLight(0xffe3bd,3.2);sun.position.set(-8,15,4);sun.castShadow=true;sun.shadow.mapSize.set(1024,1024);sun.shadow.camera.left=-19;sun.shadow.camera.right=19;sun.shadow.camera.top=19;sun.shadow.camera.bottom=-19;sun.shadow.bias=-.00025;scene.add(sun);
    const fill=new THREE.DirectionalLight(0x8eb6d0,1.1);fill.position.set(8,6,-12);scene.add(fill);
    const groundMat=new THREE.MeshStandardMaterial({map:texture('sand'),roughness:.97});
    const ground=new THREE.Mesh(new THREE.PlaneGeometry(100,100),groundMat);ground.rotation.x=-Math.PI/2;ground.position.set(8,-.055,8);ground.receiveShadow=true;scene.add(ground);
    const wallMat=mats.stone;wallMat.map=texture('stone');wallMat.map.repeat.set(.5,1);
    const cells=[];for(let z=0;z<16;z++)for(let x=0;x<16;x++)if(tileFn(x,z)!==0)cells.push([x+.5,1.62,z+.5]);
    const stones=new THREE.InstancedMesh(new THREE.BoxGeometry(1,3.25,1),wallMat,cells.length);stones.castShadow=stones.receiveShadow=true;const d=new THREE.Object3D();
    cells.forEach((p,i)=>{d.position.set(...p);d.updateMatrix();stones.setMatrixAt(i,d.matrix);});scene.add(stones);
    const trimGeo=new THREE.BoxGeometry(1.08,.12,1.08);for(const [x,y,z]of cells){const cap=box(scene,trimGeo,mats.trim,[x,3.2,z]);cap.castShadow=false;}
    for(const [x,z]of [[1,1],[14,1],[1,14],[14,14]]){const t=new THREE.Mesh(new THREE.CylinderGeometry(1.05,1.25,4,10),mats.stone);t.position.set(x,2,z);t.castShadow=true;t.receiveShadow=true;scene.add(t);const top=new THREE.Mesh(new THREE.ConeGeometry(1.18,.65,10),mats.trim);top.position.set(x,4.3,z);top.castShadow=true;scene.add(top);}
    for(const [x,z]of [[3.1,3.1],[12.5,3.4],[3.5,11.8],[12,12],[5.5,7.5],[10.5,6.8]]){box(scene,new THREE.BoxGeometry(.85,.7,.85),mats.crate,[x,.35,z]);for(let k=-1;k<=1;k++)box(scene,new THREE.BoxGeometry(.055,.72,.88),mats.trim,[x+k*.27,.35,z]);}
    for(let i=0;i<48;i++){const a=Math.random()*Math.PI*2,r=8.5+Math.random()*16,x=8+Math.cos(a)*r,z=8+Math.sin(a)*r,rock=new THREE.Mesh(new THREE.DodecahedronGeometry(.35+Math.random()*1.15,0),mats.rock);rock.position.set(x,-.08+Math.random()*.15,z);rock.scale.y=.35+Math.random()*.55;rock.rotation.set(Math.random(),Math.random(),Math.random());rock.castShadow=true;scene.add(rock);}
    const hills=new THREE.MeshStandardMaterial({color:0x66736f,roughness:1});for(let i=0;i<18;i++){const a=i/18*Math.PI*2,r=30+Math.random()*8,h=7+Math.random()*15,m=new THREE.Mesh(new THREE.ConeGeometry(6+Math.random()*8,h,7),hills);m.position.set(8+Math.cos(a)*r,h/2-1,8+Math.sin(a)*r);m.rotation.y=Math.random();scene.add(m);}
    const sunDisc=new THREE.Mesh(new THREE.SphereGeometry(1.15,16,12),new THREE.MeshBasicMaterial({color:0xffdfa5}));sunDisc.position.set(-28,20,-52);scene.add(sunDisc);
    camera.position.set(w.x,1.62,w.y);camera.rotation.order='YXZ';camera.rotation.y=w.angle-Math.PI/2;camera.rotation.x=0;weapon.g.visible=true;
  }

  function enemy(e) {
    const g=new THREE.Group(),uniform=mats.uniform[e.type%3];
    const torso=new THREE.Mesh(new THREE.CapsuleGeometry(.24,.42,4,8),uniform);torso.position.y=1.08;torso.scale.set(.9,1,.62);g.add(torso);
    const vest=box(g,new THREE.BoxGeometry(.4,.48,.2),mats.armor,[0,1.08,-.13]);vest.rotation.x=-.05;
    for(const x of [-.16,0,.16]){box(g,new THREE.BoxGeometry(.105,.12,.075),mats.gear,[x,.88,-.252]);box(g,new THREE.BoxGeometry(.095,.09,.045),mats.black,[x,.89,-.295]);}
    for(const side of [-1,1]){const pad=new THREE.Mesh(new THREE.SphereGeometry(.13,10,8),mats.armor);pad.position.set(side*.29,1.28,-.03);pad.scale.set(1,.72,1);g.add(pad);box(g,new THREE.BoxGeometry(.19,.13,.16),mats.armor,[side*.12,.46,-.09]);box(g,new THREE.BoxGeometry(.19,.14,.27),mats.black,[side*.12,.08,-.04]);}
    const head=new THREE.Mesh(new THREE.SphereGeometry(.18,12,10),mats.skin);head.position.y=1.54;g.add(head);
    const helmet=new THREE.Mesh(new THREE.SphereGeometry(.195,12,8,0,Math.PI*2,0,Math.PI*.56),e.type===2?mats.metal:mats.black);helmet.position.y=1.61;g.add(helmet);
    box(g,new THREE.BoxGeometry(.28,.12,.07),mats.black,[0,1.45,-.16]);
    const eyeMat=new THREE.MeshStandardMaterial({color:0x111715,roughness:.34});for(const side of [-1,1]){const eye=new THREE.Mesh(new THREE.SphereGeometry(.026,8,6),eyeMat);eye.position.set(side*.07,1.56,-.164);g.add(eye);box(g,new THREE.BoxGeometry(.16,.48,.2),mats.black,[side*.12,.34,0]);const arm=box(g,new THREE.BoxGeometry(.12,.42,.14),uniform,[side*.27,1.08,-.06]);arm.rotation.z=side*.15;}
    const rifle=box(g,new THREE.BoxGeometry(.09,.09,.65),mats.metal,[.27,1.08,-.28]);rifle.rotation.y=-.12;box(g,new THREE.BoxGeometry(.055,.11,.12),mats.black,[.27,1.16,-.28]);
    const barrel=new THREE.Mesh(new THREE.CylinderGeometry(.018,.022,.34,8),mats.black);barrel.rotation.x=Math.PI/2;barrel.position.set(.27,1.08,-.76);g.add(barrel);
    const bar=new THREE.Mesh(new THREE.PlaneGeometry(.56,.055),new THREE.MeshBasicMaterial({color:0x172927}));bar.position.set(0,1.95,0);g.add(bar);
    const fill=new THREE.Mesh(new THREE.PlaneGeometry(.54,.036),new THREE.MeshBasicMaterial({color:0xef7560}));fill.position.set(0,1.95,.002);fill.userData.hp=true;g.add(fill);
    scene.add(g);enemies.set(e,g);return g;
  }

  function render(w,ts){if(w)world=w;if(!world)return;w=world;time=ts/1000;camera.position.set(w.x,1.62+Math.sin(time*8)*.012,w.y);camera.rotation.order='YXZ';camera.rotation.y=w.angle-Math.PI/2;camera.rotation.x=pitch;weapon.g.visible=true;weapon.g.position.x=.12+Math.sin(time*7)*.008;weapon.g.position.y=-.52+Math.sin(time*14)*.008-(w.muzzle>0?.025:0);weapon.g.position.z=-.7;weapon.g.rotation.z=Math.sin(time*7)*.008;weapon.flash.intensity=w.muzzle>0?14:0;
    for(const [e,g]of [...enemies])if(!w.enemies.includes(e)){scene.remove(g);enemies.delete(e);}
    for(const e of w.enemies){const g=enemies.get(e)||enemy(e);g.position.set(e.x,0,e.y);g.rotation.y=Math.atan2(w.x-e.x,-(w.y-e.y));for(const o of g.children)if(o.userData.hp)o.scale.x=.06+clamp(e.hp/e.max,0,1);}
    for(const [m,o]of [...missiles])if(!w.missiles.includes(m)){scene.remove(o);missiles.delete(m);}
    for(const m of w.missiles){let o=missiles.get(m);if(!o){o=new THREE.Group();const body=new THREE.Mesh(new THREE.CylinderGeometry(.045,.09,.48,10),new THREE.MeshStandardMaterial({color:0xd3cfbd,metalness:.5,roughness:.38,emissive:0x31190c}));body.rotation.x=Math.PI/2;o.add(body);o.add(new THREE.PointLight(0xff7136,2,3));scene.add(o);missiles.set(m,o);}o.position.set(m.x,1.1,m.y);o.rotation.y=Math.atan2(m.vx,m.vy);}
    renderer.render(scene,camera);
  }

  return {setSize,build,render,look(dx,dy,w){pitch=clamp(pitch+dy*(w<700?.004:.0025),-.42,.42);},scope(on){scoped=on;camera.fov=on?28:baseFov;camera.updateProjectionMatrix();return scoped;},stats(){return {renderer:'webgl-threejs',enemies:enemies.size};}};
}
