import * as THREE from 'three';

export function flashlightResources() {
  const ground = new THREE.PlaneGeometry(1, 1).rotateX(-Math.PI / 2).translate(0, 0, .5);
  const housing = new THREE.CylinderGeometry(.085, .065, .24, 10).rotateX(Math.PI / 2);
  const lens = new THREE.CircleGeometry(.064, 12);
  const shell = new THREE.MeshLambertMaterial({ color: '#28312c' });
  const glass = new THREE.MeshBasicMaterial({ color: '#fff4d2', toneMapped: false });
  const beam = opacity => new THREE.ShaderMaterial({
    uniforms: { opacity: { value: opacity } },
    vertexShader: `varying vec2 vUv;
      void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: `varying vec2 vUv; uniform float opacity;
      void main() {
        float along = 1.0 - vUv.y;
        float side = abs(vUv.x - .5) * 2.0;
        float width = max(.035, along);
        float edge = 1.0 - smoothstep(width * .55, width, side);
        float falloff = smoothstep(.0, .08, along) * (1.0 - smoothstep(.25, 1.0, along));
        gl_FragColor = vec4(1.0, .94, .73, edge * falloff * opacity);
      }`,
    transparent: true, blending: THREE.AdditiveBlending, depthWrite: false,
    depthTest: true, side: THREE.DoubleSide, toneMapped: false,
    polygonOffset: true, polygonOffsetFactor: -1, polygonOffsetUnits: -1,
  });
  const localBeam = beam(.24), remoteBeam = beam(.16);
  return {
    make(local, id) {
      const fixture = new THREE.Group();
      const body = new THREE.Mesh(housing, shell), bulb = new THREE.Mesh(lens, glass);
      bulb.position.z = .125; fixture.add(body, bulb);
      fixture.userData.testId = `flashlight-fixture-${id}`;
      const patch = new THREE.Mesh(ground, local ? localBeam : remoteBeam);
      patch.userData.testId = `flashlight-beam-${id}`;
      return { fixture, patch, local, length: 26, rayAt: -Infinity, angle: 0 };
    },
    dispose() { [ground, housing, lens, shell, glass, localBeam, remoteBeam].forEach(r => r.dispose()); },
  };
}