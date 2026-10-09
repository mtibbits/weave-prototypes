// Three.js side of the hero: loads the Blender export and draws the crowd (plus the Help magnifier).
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

const INK = 0x1b2423;

export async function loadAssets(base) {
  const [gltf, layout] = await Promise.all([
    new GLTFLoader().loadAsync(`${base}coalesce.glb`),
    fetch(`${base}layout.json`).then((res) => {
      if (!res.ok) throw new Error(`layout.json: HTTP ${res.status}`);
      return res.json();
    }),
  ]);
  gltf.scene.updateMatrixWorld(true);
  const geometry = (name) => {
    const node = gltf.scene.getObjectByName(name);
    if (!node || !node.isMesh) throw new Error(`coalesce.glb has no mesh named ${name}`);
    return node.geometry.clone().applyMatrix4(node.matrixWorld);
  };
  return {
    layout,
    person: geometry('Person'),
    magnifierParts: ['MagnifierRim', 'MagnifierCollar', 'MagnifierHandle'].map((name) => geometry(name)),
  };
}

export class CrowdView {
  constructor(canvas, assets, { preserveDrawingBuffer = false } = {}) {
    const { layout } = assets;
    this.layout = layout;
    this.renderer = new THREE.WebGLRenderer({
      canvas, antialias: true, alpha: true, stencil: true, powerPreference: 'high-performance', preserveDrawingBuffer,
    });
    this.renderer.setClearColor(0x000000, 0);
    this.renderer.toneMapping = THREE.AgXToneMapping;
    this.renderer.toneMappingExposure = 1.05;

    this.scene = new THREE.Scene();
    const pmrem = new THREE.PMREMGenerator(this.renderer);
    this.envTexture = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    pmrem.dispose();
    this.scene.environment = this.envTexture;
    this.scene.environmentIntensity = 0.85;
    const key = new THREE.DirectionalLight(0xfff1e0, 2.2);
    key.position.set(-5, 8, 6);
    const rim = new THREE.DirectionalLight(0xffffff, 1.1);
    rim.position.set(4, 6, -6);
    this.scene.add(key, rim);

    const cam = layout.camera;
    this.camera = new THREE.PerspectiveCamera(cam.vfovDeg, cam.aspect, 0.1, 100);
    this.camera.position.fromArray(cam.position);
    this.camera.lookAt(new THREE.Vector3().fromArray(cam.target));
    this.camera.layers.enable(1);
    this.camera.updateMatrixWorld(true);

    // The figure tilts around its own centre: the pivot sits at the centre and the figure is offset back.
    const c = layout.figureCenter;
    this.pivot = new THREE.Group();
    this.pivot.position.fromArray(c);
    this.figure = new THREE.Group();
    this.figure.position.set(-c[0], -c[1], -c[2]);
    this.pivot.add(this.figure);
    this.scene.add(this.pivot);

    this.material = new THREE.MeshPhysicalMaterial({
      color: 0xffffff, roughness: 0.4, clearcoat: 0.3, clearcoatRoughness: 0.35,
    });
    this.mesh = new THREE.InstancedMesh(assets.person, this.material, layout.people.length + 3);
    this.mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    this.mesh.frustumCulled = false;
    this.mesh.setColorAt(0, new THREE.Color(1, 1, 1));
    this.figure.add(this.mesh);

    this._dummy = new THREE.Object3D();
    this._color = new THREE.Color();
    this._raycaster = new THREE.Raycaster();
    this._plane = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0);
    this._inverse = new THREE.Matrix4();
    this._ndc = new THREE.Vector2();
  }

  sync(tokens, scale) {
    const d = this._dummy;
    tokens.forEach((t, i) => {
      d.position.set(t.p[0], t.p[1], t.p[2]);
      d.rotation.set(t.rx, 0, t.rz);
      d.scale.setScalar(scale * Math.max(t.s, 1e-4));
      d.updateMatrix();
      this.mesh.setMatrixAt(i, d.matrix);
      this.mesh.setColorAt(i, this._color.setRGB(t.col[0], t.col[1], t.col[2]));
    });
    this.mesh.count = tokens.length;
    this.mesh.instanceMatrix.needsUpdate = true;
    this.mesh.instanceColor.needsUpdate = true;
  }

  setTilt(x, y) {
    this.pivot.rotation.set(x, y, 0);
  }

  // Where a pointer (normalized device coordinates) meets the plane z = planeZ, in figure coordinates.
  pointerToFigure(ndcX, ndcY, planeZ = 1.0) {
    this.scene.updateMatrixWorld(true);
    this._ndc.set(ndcX, ndcY);
    this._raycaster.setFromCamera(this._ndc, this.camera);
    this._inverse.copy(this.figure.matrixWorld).invert();
    const ray = this._raycaster.ray.clone().applyMatrix4(this._inverse);
    this._plane.constant = -planeZ;
    const hit = ray.intersectPlane(this._plane, new THREE.Vector3());
    return hit ? [hit.x, hit.y, hit.z] : null;
  }

  resize(width, height, pixelRatio) {
    this.renderer.setPixelRatio(pixelRatio);
    this.renderer.setSize(width, height, false);
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
  }

  render() {
    this.renderer.render(this.scene, this.camera);
  }

  dispose() {
    this.mesh.geometry.dispose();
    this.mesh.dispose();
    this.material.dispose();
    this.envTexture.dispose();
    this.renderer.dispose();
  }
}

function glareTexture() {
  const size = 256;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const g = canvas.getContext('2d');
  const shine = g.createRadialGradient(size * 0.34, size * 0.3, 0, size * 0.34, size * 0.3, size * 0.55);
  shine.addColorStop(0, 'rgba(255,255,255,0.32)');
  shine.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = shine;
  g.fillRect(0, 0, size, size);
  const edge = g.createRadialGradient(size / 2, size / 2, size * 0.36, size / 2, size / 2, size * 0.5);
  edge.addColorStop(0, 'rgba(27,36,35,0)');
  edge.addColorStop(1, 'rgba(27,36,35,0.2)');
  g.fillStyle = edge;
  g.fillRect(0, 0, size, size);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

export class MagnifierView {
  constructor(view, assets, { magnification = 2 } = {}) {
    this.view = view;
    this.magnification = magnification;
    const { lensRadius, standoff } = view.layout.magnifier;
    this.standoff = standoff;

    this.group = new THREE.Group();
    this.inkMaterial = new THREE.MeshPhysicalMaterial({ color: INK, roughness: 0.3, metalness: 0.5, clearcoat: 0.4 });
    for (const geometry of assets.magnifierParts) this.group.add(new THREE.Mesh(geometry, this.inkMaterial));
    this.group.traverse((object) => object.layers.set(1));
    view.figure.add(this.group);

    const disc = new THREE.CircleGeometry(lensRadius, 64);
    this.mask = new THREE.Mesh(disc, new THREE.MeshBasicMaterial({
      color: 0x000000, transparent: true, opacity: 0, blending: THREE.NoBlending, depthWrite: false,
      stencilWrite: true, stencilRef: 1, stencilFunc: THREE.AlwaysStencilFunc, stencilZPass: THREE.ReplaceStencilOp,
    }));
    this.glare = new THREE.Mesh(disc, new THREE.MeshBasicMaterial({
      map: glareTexture(), transparent: true, depthTest: false, depthWrite: false,
    }));
    this.mask.matrixAutoUpdate = false;
    this.glare.matrixAutoUpdate = false;
    this.maskScene = new THREE.Scene();
    this.maskScene.add(this.mask);
    this.glareScene = new THREE.Scene();
    this.glareScene.add(this.glare);

    this.zoomCamera = new THREE.PerspectiveCamera();
    this.zoomCamera.layers.set(0);
    this._aim = new THREE.Vector3();
    this._eye = new THREE.Vector3();
    this._centre = new THREE.Vector3();
    this._zoom = new THREE.Matrix4();
  }

  // Place the glass between the viewer and `aim` (figure coordinates), facing the viewer.
  update(aim) {
    const { scene, figure, camera } = this.view;
    scene.updateMatrixWorld(true);
    this._aim.fromArray(aim);
    this._eye.copy(camera.position);
    figure.worldToLocal(this._eye);
    this._eye.sub(this._aim).normalize();
    this.group.position.copy(this._aim).addScaledVector(this._eye, this.standoff);
    this.group.lookAt(camera.position);
    this.group.updateMatrixWorld(true);
    this.mask.matrix.copy(this.group.matrixWorld);
    this.glare.matrix.copy(this.group.matrixWorld);
  }

  render() {
    const { renderer, scene, camera, material } = this.view;
    renderer.render(scene, camera);
    renderer.autoClear = false;
    renderer.clearDepth();
    renderer.clearStencil();
    renderer.render(this.maskScene, camera);
    this.aimZoomCamera();
    material.stencilWrite = true;
    material.stencilFunc = THREE.EqualStencilFunc;
    material.stencilRef = 1;
    material.stencilZPass = THREE.KeepStencilOp;
    renderer.render(scene, this.zoomCamera);
    material.stencilWrite = false;
    material.stencilFunc = THREE.AlwaysStencilFunc;
    renderer.render(this.glareScene, camera);
    renderer.autoClear = true;
  }

  // The zoom camera sees what the main camera sees, scaled up about the lens centre on screen.
  aimZoomCamera() {
    const { camera } = this.view;
    const zoom = this.zoomCamera;
    zoom.position.copy(camera.position);
    zoom.quaternion.copy(camera.quaternion);
    zoom.updateMatrixWorld(true);
    this.group.getWorldPosition(this._centre).project(camera);
    const m = this.magnification;
    this._zoom.set(
      m, 0, 0, this._centre.x * (1 - m),
      0, m, 0, this._centre.y * (1 - m),
      0, 0, 1, 0,
      0, 0, 0, 1,
    );
    zoom.projectionMatrix.multiplyMatrices(this._zoom, camera.projectionMatrix);
    zoom.projectionMatrixInverse.copy(zoom.projectionMatrix).invert();
  }

  dispose() {
    this.view.figure.remove(this.group);
    this.inkMaterial.dispose();
    this.mask.geometry.dispose();
    this.mask.material.dispose();
    this.glare.material.map.dispose();
    this.glare.material.dispose();
  }
}
