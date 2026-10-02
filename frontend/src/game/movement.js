import * as CANNON from 'cannon-es';

// Local prediction uses the same wall rectangles as the authoritative Pymunk world.
export class MovementController{
  constructor(){
    this.world=new CANNON.World({gravity:new CANNON.Vec3(0,0,0)});this.world.broadphase=new CANNON.SAPBroadphase(this.world);
    this.body=new CANNON.Body({mass:1,shape:new CANNON.Sphere(.65),fixedRotation:true,linearDamping:0,collisionFilterGroup:1});this.body.position.y=1;this.body.linearFactor.set(1,0,1);this.world.addBody(this.body);
    this.blocks=new Map();this.initialized=false;this.speed=0;this.vx=0;this.vz=0;
  }
  load(chunks){
    const ids=new Set(chunks.map(c=>c.id));this.blocks.forEach((bodies,id)=>{if(!ids.has(id)){bodies.forEach(b=>this.world.removeBody(b));this.blocks.delete(id);}});
    chunks.forEach(c=>{if(this.blocks.has(c.id))return;const bodies=(c.barriers||[]).map(b=>{const body=new CANNON.Body({mass:0,shape:new CANNON.Box(new CANNON.Vec3(b.w/2,2,b.d/2)),collisionFilterGroup:2});body.position.set(b.x,1,b.z);this.world.addBody(body);return body;});this.blocks.set(c.id,bodies);});
  }
  rayDistance(x,z,dx,dz,range){const result=new CANNON.RaycastResult();this.world.raycastClosest(new CANNON.Vec3(x,1,z),new CANNON.Vec3(x+dx*range,1,z+dz*range),{collisionFilterMask:2},result);return result.hasHit?result.distance:range;}
  reset(x,z){this.body.position.set(x,1,z);this.body.velocity.setZero();this.vx=this.vz=0;this.initialized=true;}
  noteInput(input, now) {
    const signature = `${input.x}:${input.z}:${!!input.sprint}`;
    if (signature !== this.intent) { this.intent = signature; this.intentSeq = input.seq; this.intentAt = now; }
  }
  update(dt,input,me,age,rtt=0){
    if(!this.initialized||this.id!==me.id){this.reset(me.x,me.z);this.id=me.id;}
    const moving=Math.hypot(input.x,input.z)>.01&&me.hp>0;
    const running=input.sprint&&me.stamina>1, speed=(running?10:6)*(me.statuses?.webbed>0?.45:1);
    const len=Math.max(1,Math.hypot(input.x,input.z));
    const tx=moving?input.x/len*speed:0,tz=moving?input.z/len*speed:0;
    const blend=1-Math.exp(-dt*(moving?28:35));this.vx+=(tx-this.vx)*blend;this.vz+=(tz-this.vz)*blend;
    // Account for transit time; do not pull a just-stopped player to an old moving state.
    const transit=Math.min(.35,Math.max(0,age)+Math.min(.25,rtt/2000));
    const expectedX=me.x+(moving?(me.vx||0)*transit:0),expectedZ=me.z+(moving?(me.vz||0)*transit:0);
    const error=Math.hypot(this.body.position.x-expectedX,this.body.position.z-expectedZ);
    const awaitingAck=me.hp>0&&(me.input_seq||0)<(this.intentSeq||0)&&performance.now()-(this.intentAt||0)<650;
    if(!awaitingAck&&error>5)this.reset(me.x,me.z);
    else if(!awaitingAck&&(!moving||error>.65)){const correction=1-Math.exp(-dt*(moving?3:10));this.body.position.x+=(expectedX-this.body.position.x)*correction;this.body.position.z+=(expectedZ-this.body.position.z)*correction;}
    this.body.velocity.set(this.vx,0,this.vz);this.world.step(1/60,Math.min(dt,.1),6);
    this.body.position.x=Math.max(-787,Math.min(787,this.body.position.x));this.body.position.z=Math.max(-787,Math.min(787,this.body.position.z));
    this.speed=Math.hypot(this.vx,this.vz);
    return {x:this.body.position.x,z:this.body.position.z,speed:this.speed,running:running&&moving};
  }
}