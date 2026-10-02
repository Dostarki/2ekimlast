import * as THREE from 'three';

const UP=new THREE.Vector3(0,1,0);
export class FlameStreams {
  constructor(scene){this.scene=scene;this.streams=new Map();this.geometry=new THREE.CylinderGeometry(1,.06,1,12,1,true);this.direction=new THREE.Vector3();}
  emit(e){
    const id=e.owner||'local-flame';let group=this.streams.get(id);
    if(!group){
      group=new THREE.Group();
      for(const [color,radius,opacity] of [['#fa6624',1,.26],['#ffd271',.44,.4]]){
        const mesh=new THREE.Mesh(this.geometry,new THREE.MeshBasicMaterial({color,transparent:true,opacity,side:THREE.DoubleSide,depthWrite:false}));mesh.scale.set(radius,1,radius);mesh.userData.opacity=opacity;group.add(mesh);
      }
      this.scene.add(group);this.streams.set(id,group);
    }
    this.direction.set(e.tx-e.x,0,e.tz-e.z);const length=this.direction.length();
    group.position.set((e.x+e.tx)/2,1.23,(e.z+e.tz)/2);
    group.quaternion.setFromUnitVectors(UP,this.direction.normalize());group.scale.set(.35+length*.1,length,.35+length*.1);group.userData.until=performance.now()+230;
  }
  update(time){this.streams.forEach((g,id)=>{if(performance.now()>g.userData.until){this.remove(g);this.streams.delete(id);}else g.children.forEach((m,i)=>{m.material.opacity=m.userData.opacity*(.8+Math.sin(time*35+i)*.15);});});}
  remove(g){g.removeFromParent();g.children.forEach(m=>m.material.dispose());}
  clear(){this.streams.forEach(g=>this.remove(g));this.streams.clear();}
  dispose(){this.clear();this.geometry.dispose();}
}