import * as THREE from 'three';
import {mergeGeometries} from 'three/addons/utils/BufferGeometryUtils.js';
const flat=new THREE.MeshLambertMaterial({vertexColors:true});

// Bake many differently coloured pieces into one draw, keeping texture batches separate.
export function bakeMeshes(meshes){
  const buckets=new Map();
  meshes.forEach(m=>{
    if(m.matrixAutoUpdate)m.updateMatrix();const mat=m.material;const textured=!!mat.map;
    const key=textured?mat.uuid:'flat';if(!buckets.has(key))buckets.set(key,{material:textured?mat:flat,geos:[]});
    const g=(m.geometry.index?m.geometry.toNonIndexed():m.geometry.clone()).applyMatrix4(m.matrix);
    if(!textured){const colors=new Float32Array(g.attributes.position.count*3);for(let i=0;i<colors.length;i+=3){colors[i]=mat.color.r;colors[i+1]=mat.color.g;colors[i+2]=mat.color.b;}g.setAttribute('color',new THREE.BufferAttribute(colors,3));}
    buckets.get(key).geos.push(g);
  });
  const result=[];buckets.forEach(({material,geos})=>{const geo=mergeGeometries(geos);geos.forEach(g=>g.dispose());if(geo){const m=new THREE.Mesh(geo,material);m.castShadow=true;m.receiveShadow=true;result.push(m);}});return result;
}