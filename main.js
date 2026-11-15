import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

const S = 1 / 35;
const YAW = THREE.MathUtils.degToRad(7.0);
const MODEL_SCALE = 5.2;
const DRIVE_RANGE = 0.128;   // world edge minus 30 cm (model space)

const canvas = document.getElementById('c');
const renderer = new THREE.WebGLRenderer({
  canvas, antialias: true, alpha: false, preserveDrawingBuffer: true,
  powerPreference: 'high-performance'
});
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.42;
renderer.outputColorSpace = THREE.SRGBColorSpace;

const scene = new THREE.Scene();
let bgTexture = null;
function setBackground(stops) {
  const cv = document.createElement('canvas');
  cv.width = 16;
  cv.height = 512;
  const ctx = cv.getContext('2d');
  const gr = ctx.createLinearGradient(0, 0, 0, 512);
  for (const [pos, col] of stops) gr.addColorStop(pos, col);
  ctx.fillStyle = gr;
  ctx.fillRect(0, 0, 16, 512);
  const tex = new THREE.CanvasTexture(cv);
  tex.colorSpace = THREE.SRGBColorSpace;
  if (bgTexture) bgTexture.dispose();
  bgTexture = tex;
  scene.background = tex;
}
setBackground([[0, '#2a332b'], [0.42, '#131a15'], [0.75, '#0a0e0b'], [1, '#050706']]);
scene.fog = new THREE.FogExp2(0x0a0e0b, 0.012);

const camera = new THREE.PerspectiveCamera(33, innerWidth / innerHeight, 0.01, 200);
camera.position.set(5, 3.4, 5);

const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;
controls.dampingFactor = 0.06;
controls.autoRotate = false;
controls.autoRotateSpeed = 0.55;
controls.minDistance = 1.2;
controls.maxDistance = 22;
controls.maxPolarAngle = Math.PI * 0.495;
controls.target.set(0, 1, 0);

// ---- environment / lights -------------------------------------------------
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
scene.environmentIntensity = 0.42;

const hemi = new THREE.HemisphereLight(0xbfd8ff, 0x3a3322, 1.05);
scene.add(hemi);

const key = new THREE.DirectionalLight(0xfff0da, 2.9);
key.position.set(5, 9, 6);
key.castShadow = true;
key.shadow.mapSize.set(2048, 2048);
key.shadow.camera.left = -6;
key.shadow.camera.right = 6;
key.shadow.camera.top = 7;
key.shadow.camera.bottom = -6;
key.shadow.camera.near = 0.1;
key.shadow.camera.far = 32;
key.shadow.bias = -0.0004;
key.shadow.normalBias = 0.012;
scene.add(key);
scene.add(key.target);

const fill = new THREE.DirectionalLight(0xa9c8e8, 1.15);
fill.position.set(-4, 5, 6);
scene.add(fill);

const fill2 = new THREE.DirectionalLight(0xffd9ad, 0.9);
fill2.position.set(4, 3.5, 5);
scene.add(fill2);

const rim = new THREE.DirectionalLight(0x9fc4ff, 1.35);
rim.position.set(-6, 5, -7);
scene.add(rim);

const warm = new THREE.SpotLight(0xffc58a, 26, 18, Math.PI * 0.24, 0.8, 1.6);
warm.position.set(3.5, 7, 4.5);
warm.target.position.set(0, 0.3, 0);
warm.castShadow = false;
scene.add(warm);
scene.add(warm.target);

// studio floor
const floorMat = new THREE.MeshStandardMaterial({
  color: 0x121614, roughness: 0.94, metalness: 0.0
});
const floor = new THREE.Mesh(new THREE.CircleGeometry(30, 64), floorMat);
floor.rotation.x = -Math.PI / 2;
floor.position.y = -0.004;
floor.receiveShadow = true;
scene.add(floor);

// soft contact shadow disc
const shadowTex = makeRadialTexture();
const contact = new THREE.Mesh(
  new THREE.PlaneGeometry(7, 7),
  new THREE.MeshBasicMaterial({
    map: shadowTex, transparent: true, opacity: 0.55, depthWrite: false,
    color: 0x000000
  })
);
contact.rotation.x = -Math.PI / 2;
contact.position.y = -0.0015;
scene.add(contact);

function makeRadialTexture() {
  const cv = document.createElement('canvas');
  cv.width = cv.height = 256;
  const g = cv.getContext('2d');
  const gr = g.createRadialGradient(128, 128, 10, 128, 128, 128);
  gr.addColorStop(0, 'rgba(0,0,0,0.9)');
  gr.addColorStop(0.55, 'rgba(0,0,0,0.35)');
  gr.addColorStop(1, 'rgba(0,0,0,0)');
  g.fillStyle = gr;
  g.fillRect(0, 0, 256, 256);
  const t = new THREE.CanvasTexture(cv);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

// dust motes
const dustGeo = new THREE.BufferGeometry();
const NDUST = 420;
const dpos = new Float32Array(NDUST * 3);
for (let i = 0; i < NDUST; i++) {
  const r = 2.5 + Math.random() * 3.2;
  const a = Math.random() * Math.PI * 2;
  dpos[i * 3] = Math.cos(a) * r;
  dpos[i * 3 + 1] = 0.15 + Math.random() * 3.4;
  dpos[i * 3 + 2] = Math.sin(a) * r;
}
dustGeo.setAttribute('position', new THREE.BufferAttribute(dpos, 3));
const dust = new THREE.Points(dustGeo, new THREE.PointsMaterial({
  color: 0xffe6b8, size: 0.018, transparent: true, opacity: 0.32,
  depthWrite: false, blending: THREE.AdditiveBlending, sizeAttenuation: true
}));
scene.add(dust);

// ---- lighting scenes + headlights -----------------------------------------
const LIGHT_MODES = {
  day: {
    label: '白天', exposure: 1.42,
    key: [0xfff0da, 2.9, [5, 9, 6]],
    hemi: [0xbfd8ff, 0x3a3322, 1.05],
    fill: [0xa9c8e8, 1.15], fill2: [0xffd9ad, 0.9],
    rim: [0x9fc4ff, 1.35], warm: [0xffc58a, 26],
    fog: [0x0a0e0b, 0.012], floor: [0x121614, 0.94],
    dust: [0xffe6b8, 0.32], head: 0.5,
    bg: [[0, '#2a332b'], [0.42, '#131a15'], [0.75, '#0a0e0b'], [1, '#050706']]
  },
  dusk: {
    label: '黃昏', exposure: 1.30,
    key: [0xffa565, 2.4, [7, 4.2, 2]],
    hemi: [0xffb27a, 0x2a1a14, 0.6],
    fill: [0x7f8fbf, 0.55], fill2: [0xffb070, 0.7],
    rim: [0xff9a5a, 1.8], warm: [0xff8a4a, 18],
    fog: [0x1b1210, 0.016], floor: [0x1a1512, 0.96],
    dust: [0xffc08a, 0.35], head: 7,
    bg: [[0, '#4a3028'], [0.40, '#2a1a17'], [0.75, '#100b0a'], [1, '#060404']]
  },
  night: {
    label: '夜晚', exposure: 1.12,
    key: [0x9db8ff, 0.7, [-4, 8, -4]],
    hemi: [0x1c2a44, 0x05060a, 0.35],
    fill: [0x4a5a80, 0.25], fill2: [0x6a7fb0, 0.2],
    rim: [0x7fa6ff, 0.9], warm: [0x2a3550, 4],
    fog: [0x03060a, 0.02], floor: [0x080b0e, 0.97],
    dust: [0xaec6ff, 0.18], head: 15,
    bg: [[0, '#101a2b'], [0.40, '#0a1220'], [0.75, '#05080c'], [1, '#020304']]
  }
};
let lightMode = 'day';
const headlights = { spots: [], sprites: [] };

function makeGlowTexture() {
  const cv = document.createElement('canvas');
  cv.width = cv.height = 128;
  const g = cv.getContext('2d');
  const gr = g.createRadialGradient(64, 64, 2, 64, 64, 64);
  gr.addColorStop(0, 'rgba(255,255,255,1)');
  gr.addColorStop(0.25, 'rgba(255,240,200,0.75)');
  gr.addColorStop(1, 'rgba(255,220,150,0)');
  g.fillStyle = gr;
  g.fillRect(0, 0, 128, 128);
  const t = new THREE.CanvasTexture(cv);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}
const glowTex = makeGlowTexture();

function applyHeadlights(level) {
  for (const s of headlights.spots) s.intensity = level;
  const op = level <= 0.6 ? 0.0 : Math.min(1.0, 0.22 + level / 18);
  for (const sp of headlights.sprites) sp.material.opacity = op;
}

function setLighting(mode) {
  const p = LIGHT_MODES[mode] || LIGHT_MODES.day;
  lightMode = mode;
  key.color.setHex(p.key[0]);
  key.intensity = p.key[1];
  key.position.set(...p.key[2]);
  hemi.color.setHex(p.hemi[0]);
  hemi.groundColor.setHex(p.hemi[1]);
  hemi.intensity = p.hemi[2];
  fill.color.setHex(p.fill[0]);
  fill.intensity = p.fill[1];
  fill2.color.setHex(p.fill2[0]);
  fill2.intensity = p.fill2[1];
  rim.color.setHex(p.rim[0]);
  rim.intensity = p.rim[1];
  warm.color.setHex(p.warm[0]);
  warm.intensity = p.warm[1];
  scene.fog.color.setHex(p.fog[0]);
  scene.fog.density = p.fog[1];
  floorMat.color.setHex(p.floor[0]);
  floorMat.roughness = p.floor[1];
  dust.material.color.setHex(p.dust[0]);
  dust.material.opacity = p.dust[1];
  renderer.toneMappingExposure = p.exposure;
  setBackground(p.bg);
  applyHeadlights(p.head);
  const out = document.getElementById('outLight');
  if (out) out.textContent = p.label;
  document.querySelectorAll('[data-light]').forEach(b => {
    b.classList.toggle('active', b.dataset.light === mode);
  });
}

function buildHeadlights(hullObj) {
  for (const side of [-1, 1]) {
    const z = -side * 1.30 * S;
    const spr = new THREE.Sprite(new THREE.SpriteMaterial({
      map: glowTex, color: 0xffe6bb, transparent: true, opacity: 0.0,
      depthWrite: false, blending: THREE.AdditiveBlending, toneMapped: false
    }));
    spr.position.set(3.885 * S, 1.08 * S, z);
    spr.scale.setScalar(0.022);
    hullObj.add(spr);
    headlights.sprites.push(spr);

    const spot = new THREE.SpotLight(0xffe2b4, 0, 9, 0.42, 0.7, 2);
    spot.position.set(3.90 * S, 1.12 * S, z);
    const target = new THREE.Object3D();
    target.position.set(7.0 * S, 0.45 * S, z);
    hullObj.add(target);
    hullObj.add(spot);
    spot.target = target;
    headlights.spots.push(spot);
  }
}

setLighting('day');

// ---- glb ------------------------------------------------------------------
const root = new THREE.Group();
scene.add(root);
let hull, turret, gun, turretBase, gunBase;
let wheels = [];
let trackGroup = null;
let trackLinks = [];
let tankWorld = new THREE.Vector3();
let tankForward = new THREE.Vector3(0, 0, -1);
let tankRight = new THREE.Vector3(1, 0, 0);
let dioramaCenter = new THREE.Vector3(0, 1, 0);

function foliageShader(mat) {
  mat.onBeforeCompile = (shader) => {
    shader.vertexShader = 'varying vec3 vFp;\n' + shader.vertexShader.replace(
      '#include <begin_vertex>',
      '#include <begin_vertex>\nvFp = position;'
    );
    shader.fragmentShader = `varying vec3 vFp;
      float fhash(vec3 p){p=fract(p*0.1031);p+=dot(p,p.yzx+33.33);return fract((p.x+p.y)*p.z);}
    ` + shader.fragmentShader.replace(
      '#include <color_fragment>',
      `#include <color_fragment>
       float f1=fhash(vFp*44.0);
       float f2=fhash(vFp*137.0);
       float fs=clamp(0.35+0.75*f1+0.25*f2,0.0,1.35);
       diffuseColor.rgb *= mix(vec3(0.55,0.68,0.48), vec3(1.18,1.25,0.98), fs*0.55);
      `
    );
  };
  mat.customProgramCacheKey = () => 'foliage';
}

// ---- synthesized audio (Web Audio) ---------------------------------------
class SoundFX {
  constructor() {
    this.ctx = null;
    this.master = null;
    this.engine = null;
    this.enabled = true;
    this.initialized = false;
    this.noise = null;
    this.lastServo = 0;
    this.lastLoad = -1;
    this.revLevel = 0;
    this.revTarget = 0;
    this.revUntil = 0;
    this.servoUntil = 0;
    this.servoKind = '';
    this.servoNodes = null;
  }

  makeNoise(seconds = 2) {
    const n = Math.floor(this.ctx.sampleRate * seconds);
    const buf = this.ctx.createBuffer(1, n, this.ctx.sampleRate);
    const d = buf.getChannelData(0);
    let last = 0;
    for (let i = 0; i < n; i++) {
      const w = Math.random() * 2 - 1;
      last = (last + 0.02 * w) / 1.02;
      d[i] = (w * 0.6 + last * 3.0) * 0.5;
    }
    return buf;
  }

  init() {
    if (this.ctx) { if (this.ctx.state === 'suspended') this.ctx.resume(); return; }
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return;
    this.ctx = new AC();
    this.noise = this.makeNoise(2);
    const comp = this.ctx.createDynamicsCompressor();
    comp.threshold.value = -18;
    comp.ratio.value = 4;
    this.master = this.ctx.createGain();
    this.master.gain.value = this.enabled ? 0.22 : 0.0001;
    this.master.connect(comp).connect(this.ctx.destination);
    this.buildEngine();
    this.buildServo();
    this.initialized = true;
    this.setEnabledUI(this.enabled);
    if (this.ctx.state === 'suspended') this.ctx.resume();
  }

  buildEngine() {
    const ctx = this.ctx;
    const mix = ctx.createGain();
    mix.gain.value = 0.55;
    const lp = ctx.createBiquadFilter();
    lp.type = 'lowpass';
    lp.frequency.value = 250;
    lp.Q.value = 1.1;
    const shaper = ctx.createWaveShaper();
    const curve = new Float32Array(1024);
    for (let i = 0; i < 1024; i++) {
      const x = i / 512 - 1;
      curve[i] = Math.tanh(x * 2.2) * 0.75;
    }
    shaper.curve = curve;
    const bus = ctx.createGain();
    bus.gain.value = 0.8;
    mix.connect(shaper).connect(lp).connect(bus).connect(this.master);

    const oscs = [];
    const specs = [
      [34, 'sawtooth', 0.30],
      [68, 'square', 0.15],
      [17, 'triangle', 0.36],
      [102, 'sawtooth', 0.06]
    ];
    for (const [f, type, g] of specs) {
      const o = ctx.createOscillator();
      o.type = type;
      o.frequency.value = f;
      o.detune.value = (Math.random() - 0.5) * 8;
      const gn = ctx.createGain();
      gn.gain.value = g;
      o.connect(gn).connect(mix);
      o.start();
      oscs.push({ o, gn, f });
    }

    const nsrc = ctx.createBufferSource();
    nsrc.buffer = this.noise;
    nsrc.loop = true;
    const nlp = ctx.createBiquadFilter();
    nlp.type = 'lowpass';
    nlp.frequency.value = 180;
    const ng = ctx.createGain();
    ng.gain.value = 0.55;
    nsrc.connect(nlp).connect(ng).connect(mix);
    nsrc.start();

    const lfo = ctx.createOscillator();
    lfo.type = 'sine';
    lfo.frequency.value = 8.2;
    const lg = ctx.createGain();
    lg.gain.value = 0.13;
    lfo.connect(lg).connect(mix.gain);
    lfo.start();

    const lfo2 = ctx.createOscillator();
    lfo2.type = 'sine';
    lfo2.frequency.value = 0.7;
    const lg2 = ctx.createGain();
    lg2.gain.value = 0.05;
    lfo2.connect(lg2).connect(mix.gain);
    lfo2.start();

    this.engine = { mix, lp, bus, oscs, lfo, nsrc };
  }

  buildServo() {
    // persistent, smoothly-gated servo motor (no repeated clicks)
    const ctx = this.ctx;
    const g = ctx.createGain();
    g.gain.value = 0.0001;
    const lp = ctx.createBiquadFilter();
    lp.type = 'lowpass';
    lp.frequency.value = 1400;
    const osc1 = ctx.createOscillator();
    osc1.type = 'sawtooth';
    osc1.frequency.value = 150;
    const g1 = ctx.createGain();
    g1.gain.value = 0.28;
    const osc2 = ctx.createOscillator();
    osc2.type = 'square';
    osc2.frequency.value = 75;
    const g2 = ctx.createGain();
    g2.gain.value = 0.16;
    const n = ctx.createBufferSource();
    n.buffer = this.noise;
    n.loop = true;
    const bp = ctx.createBiquadFilter();
    bp.type = 'bandpass';
    bp.frequency.value = 1100;
    bp.Q.value = 1.4;
    const ng = ctx.createGain();
    ng.gain.value = 0.22;
    osc1.connect(g1).connect(g);
    osc2.connect(g2).connect(g);
    n.connect(bp).connect(ng).connect(g);
    g.connect(lp).connect(this.master);
    osc1.start(); osc2.start(); n.start();
    this.servoNodes = { g, osc1, osc2, bp, lp };
  }

  rev(load = 1) {
    this.revUntil = performance.now() + 280;
    this.revTarget = Math.max(0.15, Math.min(1, load));
  }

  update(dt) {
    if (!this.ctx) return;
    const now = performance.now();
    const target = now < this.revUntil ? this.revTarget : 0;
    this.revLevel += (target - this.revLevel) * Math.min(1, dt * 8);
    if (this.engine) {
      const t = this.ctx.currentTime;
      const rpm = 1 + 0.38 * this.revLevel;
      for (const { o, f } of this.engine.oscs) {
        o.frequency.setTargetAtTime(f * rpm, t, 0.07);
      }
      this.engine.lfo.frequency.setTargetAtTime(8.2 + 5.5 * this.revLevel, t, 0.1);
      this.engine.lp.frequency.setTargetAtTime(240 + 260 * this.revLevel, t, 0.1);
      this.engine.mix.gain.setTargetAtTime(0.55 + 0.18 * this.revLevel, t, 0.1);
    }
    if (this.servoNodes) {
      const active = now < this.servoUntil;
      this.servoNodes.g.gain.setTargetAtTime(active ? 0.11 : 0.0001,
        this.ctx.currentTime, active ? 0.04 : 0.16);
    }
  }

  setDrive(load) {
    this.rev(load);
  }

  servo(kind) {
    if (!this.ctx || !this.enabled || !this.servoNodes) return;
    const now = performance.now();
    this.servoUntil = now + 240;
    const t = this.ctx.currentTime;
    this.servoNodes.g.gain.setTargetAtTime(0.11, t, 0.035);
    if (this.servoKind !== kind) {
      const f = kind === 'turret' ? 150 : 92;
      this.servoNodes.osc1.frequency.setTargetAtTime(f, t, 0.06);
      this.servoNodes.osc2.frequency.setTargetAtTime(f * 0.5, t, 0.06);
      this.servoNodes.bp.frequency.setTargetAtTime(kind === 'turret' ? 1100 : 620, t, 0.06);
      this.servoNodes.lp.frequency.setTargetAtTime(kind === 'turret' ? 1500 : 900, t, 0.06);
      this.servoKind = kind;
    }
  }

  toggle() {
    if (!this.ctx) { this.init(); return true; }
    this.enabled = !this.enabled;
    this.master.gain.setTargetAtTime(this.enabled ? 0.22 : 0.0001,
      this.ctx.currentTime, 0.05);
    this.setEnabledUI(this.enabled);
    return this.enabled;
  }

  setEnabledUI(on) {
    const b = document.getElementById('btnSound');
    if (!b) return;
    b.classList.toggle('active', on);
    b.textContent = on ? '🔊 音效' : '🔇 音效';
  }
}

const sound = new SoundFX();
const startAudio = (e) => {
  if (e && e.target && e.target.closest && e.target.closest('#btnSound')) return;
  if (sound.enabled) sound.init();
};
window.addEventListener('pointerdown', startAudio, { once: true });
window.addEventListener('keydown', startAudio, { once: true });

const loaderEl = document.getElementById('loader');
const bar = document.getElementById('bar');
const pct = document.getElementById('pct');

const draco = new DRACOLoader();
draco.setDecoderPath('./vendor/draco/');
const gltfLoader = new GLTFLoader();
gltfLoader.setDRACOLoader(draco);

gltfLoader.load('./scene.glb', (gltf) => {
  const model = gltf.scene;
  model.traverse((o) => {
    if (o.isMesh) {
      o.castShadow = true;
      o.receiveShadow = true;
      if (o.material) {
        const mats = Array.isArray(o.material) ? o.material : [o.material];
        for (const m of mats) {
          if (m.map) {
            m.map.anisotropy = renderer.capabilities.getMaxAnisotropy();
            m.map.needsUpdate = true;
          }
          m.envMapIntensity = 0.55;
          if (m.name === 'MAT_Hull' || m.name === 'MAT_Turret' || m.name === 'MAT_Gun') {
            m.color.setRGB(1.18, 1.18, 1.18);
          }
          if (m.name === 'MAT_Needles') { m.color.multiplyScalar(0.95); foliageShader(m); }
          if (m.name === 'MAT_Ferns') { m.color.multiplyScalar(0.9); foliageShader(m); }
          if (m.name && m.name.toLowerCase().includes('pine_card')) {
            m.alphaTest = 0.36;
            m.transparent = false;
            m.depthWrite = true;
            m.side = THREE.DoubleSide;
            m.envMapIntensity = 0.35;
            o.castShadow = false;
          }
          if (m.name && m.name.includes('Water')) {
            m.roughness = 0.08;
            m.metalness = 0.0;
            m.color.setHex(0x17120d);
          }
        }
      }
    }
  });

  model.scale.setScalar(MODEL_SCALE);
  model.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(model);
  const center = box.getCenter(new THREE.Vector3());
  model.position.x -= center.x;
  model.position.z -= center.z;
  model.position.y -= box.min.y;
  root.add(model);
  model.updateMatrixWorld(true);

  hull = model.getObjectByName('CTRL_Hull');
  turret = model.getObjectByName('CTRL_Turret');
  gun = model.getObjectByName('CTRL_Gun');
  if (!hull) console.warn('CTRL_Hull not found');
  if (hull) buildHeadlights(hull);
  setLighting(lightMode);

  if (turret) turretBase = turret.quaternion.clone();
  if (gun) gunBase = gun.quaternion.clone();

  // wheels
  model.traverse((o) => {
    if (!o.name) return;
    if (o.name.startsWith('CTRL_Wheel') || o.name.startsWith('CTRL_Idler') ||
        o.name.startsWith('CTRL_Sprocket')) {
      let r = 0.305 * S;
      if (o.name.startsWith('CTRL_Sprocket')) r = 0.30 * S;
      wheels.push({ obj: o, base: o.quaternion.clone(), r });
    }
  });

  // world frame of the tank
  hull.getWorldPosition(tankWorld);
  const q = new THREE.Quaternion();
  hull.getWorldQuaternion(q);
  tankForward.set(1, 0, 0).applyQuaternion(q).normalize();
  tankRight.crossVectors(tankForward, new THREE.Vector3(0, 1, 0)).normalize();
  if (tankRight.length() < 0.1) tankRight.set(1, 0, 0);

  const wholeBox = new THREE.Box3().setFromObject(model);
  dioramaCenter.copy(wholeBox.getCenter(new THREE.Vector3()));

  buildTracks(hull);
  setView('hero', true);

  document.getElementById('loader').classList.add('hidden');
  document.getElementById('bar').style.width = '100%';
  document.getElementById('pct').textContent = '100%';
}, (ev) => {
  if (ev.total) {
    const p = Math.min(99, Math.round(ev.loaded / ev.total * 100));
    bar.style.width = p + '%';
    pct.textContent = p + '%';
  }
}, (err) => {
  console.error(err);
  document.querySelector('.loader-sub').textContent = '載入失敗：請用本機伺服器開啟（見 README）';
});

// ---- tracks ---------------------------------------------------------------
const TRACK = {
  xf: 3.28 * S,
  xr: -3.28 * S,
  zc: 0.39 * S,
  r: 0.34 * S,
  zb: 0.05 * S,
  y: 1.36 * S,
  N: 84,
  pitch: 0.177 * S,
  plateL: 0.170 * S,
  plateW: 0.635 * S,
  plateT: 0.052 * S,
  padL: 0.128 * S,
  padW: 0.50 * S,
  padT: 0.022 * S
};
TRACK.top = TRACK.zc + TRACK.r;
TRACK.L = TRACK.xf - TRACK.xr;
TRACK.arc = Math.PI * TRACK.r;
TRACK.total = 2 * TRACK.L + 2 * TRACK.arc;
TRACK.step = TRACK.total / TRACK.N;

function trackSample(s) {
  s = ((s % TRACK.total) + TRACK.total) % TRACK.total;
  if (s < TRACK.L) {
    return { x: TRACK.xf - s, z: TRACK.zb, tx: -1, tz: 0 };
  }
  s -= TRACK.L;
  if (s < TRACK.arc) {
    const phi = -Math.PI / 2 - s / TRACK.r;
    return {
      x: TRACK.xr + Math.cos(phi) * TRACK.r,
      z: TRACK.zc + Math.sin(phi) * TRACK.r,
      tx: Math.sin(phi), tz: -Math.cos(phi)
    };
  }
  s -= TRACK.arc;
  if (s < TRACK.L) {
    return { x: TRACK.xr + s, z: TRACK.top, tx: 1, tz: 0 };
  }
  s -= TRACK.L;
  const phi = Math.PI / 2 - s / TRACK.r;
  return {
    x: TRACK.xf + Math.cos(phi) * TRACK.r,
    z: TRACK.zc + Math.sin(phi) * TRACK.r,
    tx: Math.sin(phi), tz: -Math.cos(phi)
  };
}

function buildTracks(hullObj) {
  trackGroup = new THREE.Group();
  trackGroup.name = 'ANIM_Tracks';
  hullObj.add(trackGroup);
  const cy = Math.cos(YAW), sy = Math.sin(YAW);

  const plateGeo = new THREE.BoxGeometry(TRACK.plateL, TRACK.plateW, TRACK.plateT);
  const padGeo = new THREE.BoxGeometry(TRACK.padL, TRACK.padW, TRACK.padT);
  const steel = new THREE.MeshStandardMaterial({
    color: 0x3a3327, roughness: 0.55, metalness: 0.62
  });
  const rubber = new THREE.MeshStandardMaterial({
    color: 0x0d0d0b, roughness: 0.92, metalness: 0.0
  });

  for (const side of [-1, 1]) {
    const wc = TRACK.y * side;
    const plate = new THREE.InstancedMesh(plateGeo, steel, TRACK.N);
    const pad = new THREE.InstancedMesh(padGeo, rubber, TRACK.N);
    plate.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    pad.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    plate.frustumCulled = false;
    pad.frustumCulled = false;
    plate.castShadow = true;
    plate.receiveShadow = true;
    pad.castShadow = true;
    pad.receiveShadow = true;
    trackGroup.add(plate, pad);
    trackLinks.push({ side, wc, plate, pad });
  }
  updateTracks(0);
}

const _m = new THREE.Matrix4();
const _p = new THREE.Vector3();
const _t = new THREE.Vector3();
const _w = new THREE.Vector3();
const _n = new THREE.Vector3();

function updateTracks(travel) {
  if (!trackGroup) return;
  const cy = Math.cos(YAW), sy = Math.sin(YAW);
  const padOff = TRACK.plateT / 2 + TRACK.padT / 2;
  for (const L of trackLinks) {
    for (let i = 0; i < TRACK.N; i++) {
      const sm = trackSample(i * TRACK.step + travel);
      const wc = L.wc;
      // Blender local -> world+90 -> glTF Y-up for the hull-local frame
      const px = sm.x * cy - wc * sy;
      const py = sm.x * sy + wc * cy;
      _t.set(sm.tx * cy, sm.tz, -sm.tx * sy).normalize();
      _w.set(-sy, 0, -cy).normalize();
      _n.set(-sm.tz * cy, sm.tx, sm.tz * sy).normalize();
      _p.set(px, sm.z, -py);
      _m.makeBasis(_t, _w, _n);
      _m.setPosition(_p);
      L.plate.setMatrixAt(i, _m);
      _p.addScaledVector(_n, padOff);
      _m.setPosition(_p);
      L.pad.setMatrixAt(i, _m);
    }
    L.plate.instanceMatrix.needsUpdate = true;
    L.pad.instanceMatrix.needsUpdate = true;
  }
}

// ---- controls state -------------------------------------------------------
let travel = 0;
let autoMove = false;
let turretDeg = 0;
let gunDeg = 0;
let movePhase = 0;

const qy = new THREE.Quaternion();
const qx = new THREE.Quaternion();
const qz = new THREE.Quaternion();
const AX_Y = new THREE.Vector3(0, 1, 0);
const AX_X = new THREE.Vector3(1, 0, 0);
const AX_Z = new THREE.Vector3(0, 0, 1);

function applyTurret(deg) {
  turretDeg = deg;
  if (turret && turretBase) {
    turret.quaternion.copy(turretBase).multiply(
      qy.setFromAxisAngle(AX_Y, THREE.MathUtils.degToRad(deg)));
  }
}
function applyGun(deg) {
  gunDeg = THREE.MathUtils.clamp(deg, -10, 15);
  if (gun && gunBase) {
    gun.quaternion.copy(gunBase).multiply(
      qx.setFromAxisAngle(AX_X, THREE.MathUtils.degToRad(gunDeg)));
  }
}
function applyTravel(v) {
  v = THREE.MathUtils.clamp(v, -DRIVE_RANGE, DRIVE_RANGE);
  const moved = Math.abs(v - travel) > 1e-7;
  travel = v;
  if (hull) {
    // tank local forward is -Z of the hull's parent after the +90 world turn
    hull.position.z = -v;
  }
  for (const w of wheels) {
    w.obj.quaternion.copy(w.base).multiply(
      qz.setFromAxisAngle(AX_Z, -v / w.r));
  }
  if (moved) sound.rev(Math.max(0.2, Math.abs(v) / DRIVE_RANGE));
  updateTracks(v);
}

// ---- view presets ---------------------------------------------------------
function setView(name, instant = false) {
  if (!hull) return;
  const up = new THREE.Vector3(0, 1, 0);
  const target = tankWorld.clone().add(up.clone().multiplyScalar(0.55));
  let pos;
  if (name === 'hero') {
    pos = tankWorld.clone()
      .addScaledVector(tankForward, 1.1)
      .addScaledVector(tankRight, 2.8)
      .addScaledVector(up, 1.35);
    target.addScaledVector(tankForward, 0.05);
  } else if (name === 'side') {
    pos = tankWorld.clone()
      .addScaledVector(tankRight, 3.0)
      .addScaledVector(tankForward, 0.25)
      .addScaledVector(up, 1.05);
    target.y = tankWorld.y + 0.38;
  } else {
    pos = dioramaCenter.clone()
      .addScaledVector(tankForward, 5.6)
      .addScaledVector(tankRight, 5.2)
      .addScaledVector(up, 4.2);
    target.copy(dioramaCenter).add(new THREE.Vector3(0, 0.15, 0));
  }
  if (name === 'hero') {
    pos.addScaledVector(tankForward, 0.9);
    target.addScaledVector(tankForward, 0.1);
  }
  controls.target.copy(target);
  if (instant) {
    camera.position.copy(pos);
    controls.update();
  } else {
    animateCamera(pos, target);
  }
  document.querySelectorAll('.presets button[data-view]').forEach(b => {
    b.classList.toggle('active', b.dataset.view === name);
  });
}

let camTween = null;
function animateCamera(pos, target) {
  camTween = {
    p0: camera.position.clone(), p1: pos.clone(),
    t0: controls.target.clone(), t1: target.clone(), t: 0
  };
}

// ---- UI -------------------------------------------------------------------
const $ = (id) => document.getElementById(id);
const turretEl = $('turret'), gunEl = $('gun'), driveEl = $('drive');
const outTurret = $('outTurret'), outGun = $('outGun'), outDrive = $('outDrive');

turretEl.addEventListener('input', (e) => {
  const v = parseFloat(e.target.value);
  outTurret.textContent = v + '°';
  applyTurret(v);
  sound.servo('turret');
});
gunEl.addEventListener('input', (e) => {
  const v = parseFloat(e.target.value);
  outGun.textContent = v.toFixed(1) + '°';
  applyGun(v);
  sound.servo('gun');
});
driveEl.addEventListener('input', (e) => {
  const v = parseFloat(e.target.value);
  outDrive.textContent = (v * DRIVE_RANGE * 100).toFixed(1) + ' cm';
  applyTravel(v * DRIVE_RANGE);
});

$('btnAuto').addEventListener('click', (e) => {
  controls.autoRotate = !controls.autoRotate;
  e.currentTarget.classList.toggle('active', controls.autoRotate);
});
$('btnSound').addEventListener('click', () => {
  if (!sound.ctx) sound.init();
  else sound.toggle();
});
$('btnMove').addEventListener('click', (e) => {
  autoMove = !autoMove;
  movePhase = Math.asin(THREE.MathUtils.clamp(travel / DRIVE_RANGE, -1, 1));
  e.currentTarget.classList.toggle('active', autoMove);
});
$('btnReset').addEventListener('click', () => {
  turretEl.value = 0; gunEl.value = 0; driveEl.value = 0;
  outTurret.textContent = '0°'; outGun.textContent = '0.0°'; outDrive.textContent = '0.0 cm';
  applyTurret(0); applyGun(0); applyTravel(0);
  autoMove = false;
  $('btnMove').classList.remove('active');
  setView('hero');
});
$('btnCollapse').addEventListener('click', () => {
  $('panel').classList.toggle('collapsed');
});
$('btnFull').addEventListener('click', () => {
  if (!document.fullscreenElement) document.documentElement.requestFullscreen();
  else document.exitFullscreen();
});
$('btnShot').addEventListener('click', () => {
  renderer.render(scene, camera);
  const a = document.createElement('a');
  a.href = renderer.domElement.toDataURL('image/png');
  a.download = 'M1A2T-diorama.png';
  a.click();
});
document.querySelectorAll('.presets button[data-view]').forEach(b => {
  b.addEventListener('click', () => setView(b.dataset.view));
});
document.querySelectorAll('[data-light]').forEach(b => {
  b.addEventListener('click', () => setLighting(b.dataset.light));
});

// ---- loop -----------------------------------------------------------------
const clock = new THREE.Clock();
let camTweenT = 0;
function resize() {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight, false);
}
addEventListener('resize', resize);
resize();

function animate() {
  requestAnimationFrame(animate);
  const dt = Math.min(clock.getDelta(), 0.05);
  const t = clock.elapsedTime;

  if (autoMove) {
    movePhase += dt * 0.55;
    const v = Math.sin(movePhase) * DRIVE_RANGE;
    driveEl.value = (v / DRIVE_RANGE).toFixed(2);
    outDrive.textContent = (v * 100).toFixed(1) + ' cm';
    applyTravel(v);
  }

  if (camTween) {
    camTween.t += dt / 0.9;
    const k = Math.min(1, camTween.t);
    const e = 1 - Math.pow(1 - k, 3);
    camera.position.lerpVectors(camTween.p0, camTween.p1, e);
    controls.target.lerpVectors(camTween.t0, camTween.t1, e);
    if (k >= 1) camTween = null;
  }

  sound.update(dt);

  dust.rotation.y += dt * 0.012;
  const pos = dust.geometry.attributes.position;
  for (let i = 0; i < NDUST; i++) {
    let y = pos.array[i * 3 + 1] + dt * 0.012;
    if (y > 3.8) y = 0.15;
    pos.array[i * 3 + 1] = y;
  }
  pos.needsUpdate = true;

  controls.update();
  renderer.render(scene, camera);
}
animate();

// initial UI state
outDrive.textContent = '0.0 cm';
$('btnAuto').classList.remove('active');
applyTurret(0);
applyGun(0);
