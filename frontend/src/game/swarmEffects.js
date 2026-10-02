import * as THREE from 'three';

export class SwarmEffects {
  constructor(scene) {
    this.scene = scene; this.swarms = new Map();
    this.geometry = new THREE.SphereGeometry(.037, 4, 3);
    this.material = new THREE.MeshBasicMaterial({ color: '#b6ca6e' });
    this.dummy = new THREE.Object3D();
  }
  sync(state) {
    const wanted = new Set();
    (state.swarms || []).forEach(s => {
      wanted.add(s.id); let mesh = this.swarms.get(s.id);
      if (!mesh) { mesh = new THREE.InstancedMesh(this.geometry,this.material,32); mesh.frustumCulled = false; mesh.position.set(s.x,1.25,s.z); this.scene.add(mesh); this.swarms.set(s.id,mesh); }
      mesh.userData.target = s;
    });
    this.swarms.forEach((mesh,id) => { if (!wanted.has(id)) { mesh.removeFromParent(); mesh.dispose(); this.swarms.delete(id); } });
  }
  update(dt,time) {
    this.swarms.forEach(mesh => {
      const target = mesh.userData.target;
      mesh.position.x += (target.x-mesh.position.x)*(1-Math.exp(-dt*18)); mesh.position.z += (target.z-mesh.position.z)*(1-Math.exp(-dt*18));
      for(let i=0;i<32;i++) {
        const a=i*2.4+time*(3+i%4), r=.20+(i%7)*.095;
        this.dummy.position.set(Math.cos(a)*r,Math.sin(time*8+i*1.8)*.48,Math.sin(a)*r);
        this.dummy.scale.set(1.8, .65, 1+Math.abs(Math.sin(time*80+i))); this.dummy.updateMatrix(); mesh.setMatrixAt(i,this.dummy.matrix);
      }
      mesh.instanceMatrix.needsUpdate = true;
    });
  }
  clear() { this.sync({ swarms: [] }); }
  dispose() { this.clear(); this.geometry.dispose(); this.material.dispose(); }
}