// Decorative hero art: the 21 MediaPipe hand landmarks of an open hand, drawn in, gently
// floating, with joints that pulse and a scanning ring. Purely visual (aria-hidden).
const P: [number, number][] = [
  [150, 262], // 0 wrist
  [112, 238], [86, 208], [70, 180], [58, 154], // thumb
  [118, 160], [110, 118], [106, 92], [103, 66], // index
  [148, 154], [148, 106], [148, 76], [148, 48], // middle
  [178, 160], [186, 116], [190, 90], [193, 66], // ring
  [204, 174], [220, 142], [230, 120], [238, 100], // little
];
const BONES: [number, number][] = [
  [0, 1], [1, 2], [2, 3], [3, 4], [0, 5], [5, 6], [6, 7], [7, 8], [5, 9], [9, 10], [10, 11], [11, 12],
  [9, 13], [13, 14], [14, 15], [15, 16], [13, 17], [0, 17], [17, 18], [18, 19], [19, 20],
];

export function HandArt({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 300 300" className={className} aria-hidden>
      <defs>
        <linearGradient id="ha-g" gradientUnits="userSpaceOnUse" x1="40" y1="40" x2="260" y2="280">
          <stop offset="0" stopColor="var(--color-nova-500)" />
          <stop offset="1" stopColor="var(--color-signal)" />
        </linearGradient>
        <radialGradient id="ha-glow"><stop offset="0" stopColor="var(--color-nova-500)" stopOpacity=".22" /><stop offset="1" stopColor="var(--color-nova-500)" stopOpacity="0" /></radialGradient>
      </defs>
      <circle cx="150" cy="160" r="130" fill="url(#ha-glow)" />
      <circle cx="150" cy="160" r="118" fill="none" stroke="url(#ha-g)" strokeOpacity=".35" strokeWidth="1.5" strokeDasharray="4 10">
        <animateTransform attributeName="transform" type="rotate" from="0 150 160" to="360 150 160" dur="40s" repeatCount="indefinite" />
      </circle>
      <g className="float">
        {BONES.map(([a, b], i) => (
          <line key={i} className="draw" style={{ animationDelay: `${120 + i * 45}ms` }} x1={P[a][0]} y1={P[a][1]} x2={P[b][0]} y2={P[b][1]}
            stroke="url(#ha-g)" strokeWidth="3.2" strokeLinecap="round" />
        ))}
        {P.map(([x, y], i) => (
          <circle key={i} className="twinkle" style={{ animationDelay: `${(i % 7) * 0.3}s` }} cx={x} cy={y} r="3"
            fill={i % 4 === 0 ? 'var(--color-signal)' : 'var(--color-nova-500)'} />
        ))}
        <rect x="40" y="40" width="220" height="3" rx="1.5" fill="url(#ha-g)" opacity=".5">
          <animate attributeName="y" values="40;270;40" dur="4.5s" repeatCount="indefinite" />
          <animate attributeName="opacity" values=".1;.6;.1" dur="4.5s" repeatCount="indefinite" />
        </rect>
      </g>
    </svg>
  );
}
