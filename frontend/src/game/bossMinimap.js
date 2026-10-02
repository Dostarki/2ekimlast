import { edgeClamp, minimapTransform } from './minimap';

export function drawBossMarkers(ctx,state, pose = state?.me, heading = 0){
  (state.bosses||[]).forEach((b,i)=>{
    if(!b.alive)return;
    const relative = edgeClamp(minimapTransform(b.x-pose.x,b.z-pose.z,heading,1.5), 66);
    const x=80+relative.x,z=80+relative.y;
    ctx.fillStyle=b.color;ctx.strokeStyle='#101912';ctx.lineWidth=2;
    ctx.beginPath();ctx.moveTo(x,z-7);ctx.lineTo(x+7,z);ctx.lineTo(x,z+7);ctx.lineTo(x-7,z);ctx.closePath();ctx.fill();ctx.stroke();
    ctx.fillStyle='#121a13';ctx.font='bold 8px sans-serif';ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(String(i+1),x,z+.5);
  });
}
