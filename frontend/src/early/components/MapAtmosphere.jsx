import { useEffect, useRef } from 'react';

export const MapAtmosphere = ({ count }) => {
  const ref = useRef(null);
  useEffect(() => {
    const canvas = ref.current;
    const context = canvas.getContext('2d');
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    let frame;
    const render = (time = 0) => {
      const { width, height } = canvas.getBoundingClientRect();
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      if (canvas.width !== Math.round(width * ratio) || canvas.height !== Math.round(height * ratio)) {
        canvas.width = Math.round(width * ratio); canvas.height = Math.round(height * ratio);
      }
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      context.clearRect(0, 0, width, height);
      for (let i = 0; i < Math.min(count || 0, 100); i++) {
        const x = ((i * 137.31 + 59) % (width * .21)) + (i % 2 ? width * .77 : 0);
        const y = (i * 117.7 + 100) % height;
        context.globalAlpha = reduced ? .55 : .25 + (Math.sin(time / 1300 + i) + 1) * .23;
        context.fillStyle = i % 3 === 0 ? '#d4bd74' : '#9aaf86';
        context.fillRect(x, y, 4, 4);
        context.strokeStyle = '#9aaf86'; context.strokeRect(x - 4, y - 4, 12, 12);
      }
      if (!reduced) frame = requestAnimationFrame(render);
    };
    render();
    const resize = () => { if (reduced) render(); };
    window.addEventListener('resize', resize);
    return () => { cancelAnimationFrame(frame); window.removeEventListener('resize', resize); };
  }, [count]);
  return <div className="map-atmosphere" aria-hidden="true"><div className="map-image" /><div className="map-shade" /><div className="map-grid" /><canvas ref={ref} /><div className="edge-coordinate left">38° 01′ N — SECTOR 07</div><div className="edge-coordinate right">85° 57′ W — RESTRICTED</div><i className="map-cross cross-one" /><i className="map-cross cross-two" /></div>;
};