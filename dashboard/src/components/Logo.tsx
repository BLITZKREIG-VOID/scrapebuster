interface LogoProps {
  size?: number;
  showWordmark?: boolean;
  className?: string;
  badge?: boolean;
  page?: 'overview' | 'traffic' | 'canaries' | 'probes' | 'cases';
}

export default function Logo({
  size = 32,
  showWordmark = false,
  className = '',
  badge = false,
  page = 'overview',
}: LogoProps) {
  // Render page-specific decorative overlay / ring
  const renderPageSpecificGraphics = () => {
    switch (page) {
      case 'traffic':
        return (
          <g className="animate-pulse" opacity="0.85">
            {/* Concentric Sonar / Radar Waves */}
            <circle cx="200" cy="248" r="158" fill="none" stroke="#79b4b2" strokeWidth="6" strokeDasharray="16 12" />
            <circle cx="200" cy="248" r="182" fill="none" stroke="#416866" strokeWidth="4" strokeDasharray="8 8" />
            {/* Sonar sweep beam */}
            <line x1="200" y1="248" x2="330" y2="120" stroke="#79b4b2" strokeWidth="4" strokeLinecap="round" />
            <circle cx="330" cy="120" r="7" fill="#79b4b2" />
            {/* Wave markers */}
            <path d="M 60,248 A 140,140 0 0,1 80,180" fill="none" stroke="#79b4b2" strokeWidth="6" strokeLinecap="round" />
            <path d="M 340,248 A 140,140 0 0,1 320,316" fill="none" stroke="#79b4b2" strokeWidth="6" strokeLinecap="round" />
          </g>
        );

      case 'canaries':
        return (
          <g>
            {/* Golden Honeycomb / Canary Honeytoken Crest */}
            <circle cx="200" cy="248" r="156" fill="none" stroke="#f59e0b" strokeWidth="6" strokeDasharray="14 10" />
            {/* Canary Feather / Honeycomb Token Badge at top */}
            <polygon points="200,30 220,55 200,80 180,55" fill="#f59e0b" stroke="#aec7c6" strokeWidth="3" />
            <circle cx="200" cy="55" r="4" fill="#090c0c" />
            {/* Protective Hexagon Nodes */}
            <polygon points="70,248 85,225 110,225 125,248 110,271 85,271" fill="#416866" stroke="#f59e0b" strokeWidth="3" opacity="0.8" />
            <polygon points="275,248 290,225 315,225 330,248 315,271 290,271" fill="#416866" stroke="#f59e0b" strokeWidth="3" opacity="0.8" />
          </g>
        );

      case 'probes':
        return (
          <g>
            {/* Neural Interrogator Crosshair & Cyber-Optic Targeting Reticle */}
            <circle cx="200" cy="248" r="162" fill="none" stroke="#ef4444" strokeWidth="5" strokeDasharray="24 16" />
            {/* 4 Precision Targeting Reticles */}
            <line x1="200" y1="40" x2="200" y2="85" stroke="#ef4444" strokeWidth="6" strokeLinecap="round" />
            <line x1="200" y1="410" x2="200" y2="455" stroke="#ef4444" strokeWidth="6" strokeLinecap="round" />
            <line x1="10" y1="248" x2="55" y2="248" stroke="#ef4444" strokeWidth="6" strokeLinecap="round" />
            <line x1="345" y1="248" x2="390" y2="248" stroke="#ef4444" strokeWidth="6" strokeLinecap="round" />
            {/* Cyber Interrogation Optic in Doberman eye */}
            <circle cx="218" cy="163" r="10" fill="none" stroke="#ef4444" strokeWidth="3" className="animate-ping" />
            <circle cx="218" cy="163" r="5" fill="#ef4444" />
          </g>
        );

      case 'cases':
        return (
          <g>
            {/* GPS Provenance Orbital Ring & Cardinal Direction Compass */}
            <circle cx="200" cy="248" r="164" fill="none" stroke="#aec7c6" strokeWidth="4" />
            <circle cx="200" cy="248" r="178" fill="none" stroke="#416866" strokeWidth="3" strokeDasharray="6 6" />
            {/* Orbital Satellites / Provenance Pipeline Nodes */}
            <circle cx="200" cy="70" r="10" fill="#aec7c6" stroke="#090c0c" strokeWidth="3" />
            <circle cx="378" cy="248" r="10" fill="#79b4b2" stroke="#090c0c" strokeWidth="3" />
            <circle cx="200" cy="426" r="10" fill="#ef4444" stroke="#090c0c" strokeWidth="3" />
            <circle cx="22" cy="248" r="10" fill="#416866" stroke="#090c0c" strokeWidth="3" />
            {/* GPS Cardinal Compass Pointer */}
            <polygon points="200,90 206,108 200,104 194,108" fill="#aec7c6" />
          </g>
        );

      case 'overview':
      default:
        return (
          <g>
            {/* Active Sentinel Security Shield Pulse */}
            <circle cx="200" cy="248" r="150" fill="none" stroke="#79b4b2" strokeWidth="3" opacity="0.4" />
            {/* 4 Shield Rivets */}
            <circle cx="90" cy="138" r="5" fill="#79b4b2" />
            <circle cx="310" cy="138" r="5" fill="#79b4b2" />
            <circle cx="90" cy="358" r="5" fill="#79b4b2" />
            <circle cx="310" cy="358" r="5" fill="#79b4b2" />
          </g>
        );
    }
  };

  const renderCollarBadge = () => {
    switch (page) {
      case 'traffic':
        return (
          <g>
            <circle cx="200" cy="272" r="7" fill="#79b4b2" stroke="#090c0c" strokeWidth="2" />
            <circle cx="200" cy="272" r="11" fill="none" stroke="#79b4b2" strokeWidth="1.5" strokeDasharray="3 3" />
          </g>
        );
      case 'canaries':
        return (
          <g>
            <polygon points="200,263 209,272 200,281 191,272" fill="#f59e0b" stroke="#090c0c" strokeWidth="2" />
            <circle cx="200" cy="272" r="2.5" fill="#ffffff" />
          </g>
        );
      case 'probes':
        return (
          <g>
            <circle cx="200" cy="272" r="7" fill="#ef4444" stroke="#090c0c" strokeWidth="2" />
            <line x1="192" y1="272" x2="208" y2="272" stroke="#ffffff" strokeWidth="1.5" />
            <line x1="200" y1="264" x2="200" y2="280" stroke="#ffffff" strokeWidth="1.5" />
          </g>
        );
      case 'cases':
        return (
          <g>
            <circle cx="200" cy="272" r="7" fill="#aec7c6" stroke="#090c0c" strokeWidth="2" />
            <polygon points="200,265 203,272 200,270 197,272" fill="#090c0c" />
          </g>
        );
      case 'overview':
      default:
        return (
          <g>
            <polygon points="193,264 207,264 207,274 200,279 193,274" fill="#79b4b2" stroke="#090c0c" strokeWidth="2" />
          </g>
        );
    }
  };

  const getPageTitle = () => {
    switch (page) {
      case 'traffic': return 'TRAFFIC SONAR';
      case 'canaries': return 'CANARY VAULT';
      case 'probes': return 'DOBERMAN PROBE';
      case 'cases': return 'GPS PROVENANCE';
      case 'overview':
      default:
        return 'SCRAPEBUSTER';
    }
  };

  if (showWordmark) {
    return (
      <svg
        viewBox="0 0 400 532"
        width={size}
        height={(size * 532) / 400}
        xmlns="http://www.w3.org/2000/svg"
        className={`select-none shrink-0 ${className}`}
      >
        {/* Page specific outer graphics */}
        {renderPageSpecificGraphics()}

        {/* White circular backdrop behind the Doberman */}
        <circle cx="200" cy="248" r="134" fill="#ffffff" />

        {/* Chest / body */}
        <path d="M 176,268 L 224,268 L 248,366 L 152,366 Z" fill="#090c0c" />

        {/* Red diagonal slash */}
        <line
          x1="99"
          y1="147"
          x2="301"
          y2="349"
          stroke="#CC0000"
          strokeWidth="30"
          strokeLinecap="butt"
        />

        {/* Red prohibition ring */}
        <circle
          cx="200"
          cy="248"
          r="134"
          fill="none"
          stroke="#CC0000"
          strokeWidth="30"
        />

        {/* Left cropped ear */}
        <polygon points="170,128 162,64 188,121" fill="#090c0c" />
        {/* Right cropped ear */}
        <polygon points="230,128 238,64 212,121" fill="#090c0c" />

        {/* Skull + cheeks + neck */}
        <path
          d="
            M 176,268
            L 226,268
            L 228,244
            L 238,190
            L 240,158
            L 224,122
            L 200,114
            L 176,122
            L 160,158
            L 162,190
            L 172,244
            Z
          "
          fill="#090c0c"
        />

        {/* Muzzle panel */}
        <path d="M 184,180 L 216,180 L 217,221 L 183,221 Z" fill="#ffffff" />

        {/* Chin curve */}
        <path
          d="M 183,219 Q 200,230 217,219 L 217,221 L 183,221 Z"
          fill="#e4e4e4"
        />

        {/* Nose */}
        <rect x="190" y="217" width="20" height="11" rx="4" fill="#090c0c" />

        {/* Left eye */}
        <ellipse cx="182" cy="163" rx="9" ry="7" fill="#ffffff" />
        <circle cx="183" cy="164" r="5" fill="#090c0c" />
        <circle cx="185" cy="162" r="1.8" fill="#ffffff" />

        {/* Right eye */}
        <ellipse cx="218" cy="163" rx="9" ry="7" fill="#ffffff" />
        <circle cx="217" cy="164" r="5" fill="#090c0c" />
        <circle cx="219" cy="162" r="1.8" fill="#ffffff" />

        {/* Eyebrow spots */}
        <ellipse cx="182" cy="149" rx="5.5" ry="3.5" fill="#ffffff" />
        <ellipse cx="218" cy="149" rx="5.5" ry="3.5" fill="#ffffff" />

        {/* Left paw */}
        <ellipse cx="162" cy="361" rx="7.5" ry="6.5" fill="#090c0c" />
        <ellipse cx="173" cy="358" rx="7.5" ry="6.5" fill="#090c0c" />
        <ellipse cx="184" cy="361" rx="7.5" ry="6.5" fill="#090c0c" />
        <rect x="150" y="361" width="48" height="30" rx="10" fill="#090c0c" />

        {/* Right paw */}
        <ellipse cx="216" cy="361" rx="7.5" ry="6.5" fill="#090c0c" />
        <ellipse cx="227" cy="358" rx="7.5" ry="6.5" fill="#090c0c" />
        <ellipse cx="238" cy="361" rx="7.5" ry="6.5" fill="#090c0c" />
        <rect x="202" y="361" width="48" height="30" rx="10" fill="#090c0c" />

        {/* Page-Specific Cyber Collar Emblem Badge */}
        {renderCollarBadge()}

        {/* Wordmark */}
        <text
          x="200"
          y="470"
          textAnchor="middle"
          fontFamily="'Barlow Condensed', 'Montserrat', 'Arial Narrow', sans-serif"
          fontWeight="900"
          fontSize="42"
          fill="#ebefee"
          letterSpacing="1.5"
        >
          {getPageTitle()}
        </text>
      </svg>
    );
  }

  // Icon-only compact version for headers, navbars, and badges (cropped viewBox)
  return (
    <div
      style={{ width: size, height: size }}
      className={`relative inline-flex items-center justify-center shrink-0 ${
        badge ? 'rounded-lg bg-white/10 p-0.5 border border-white/20 shadow-sm' : ''
      } ${className}`}
    >
      <svg
        viewBox="10 20 380 430"
        width="100%"
        height="100%"
        xmlns="http://www.w3.org/2000/svg"
        className="overflow-visible"
      >
        {/* Page specific outer graphics */}
        {renderPageSpecificGraphics()}

        {/* Circular white backdrop */}
        <circle cx="200" cy="248" r="134" fill="#ffffff" />

        {/* Chest / body */}
        <path d="M 176,268 L 224,268 L 248,366 L 152,366 Z" fill="#090c0c" />

        {/* Red diagonal slash */}
        <line
          x1="99"
          y1="147"
          x2="301"
          y2="349"
          stroke="#CC0000"
          strokeWidth="30"
          strokeLinecap="butt"
        />

        {/* Red prohibition ring */}
        <circle
          cx="200"
          cy="248"
          r="134"
          fill="none"
          stroke="#CC0000"
          strokeWidth="30"
        />

        {/* Left cropped ear */}
        <polygon points="170,128 162,64 188,121" fill="#090c0c" />
        {/* Right cropped ear */}
        <polygon points="230,128 238,64 212,121" fill="#090c0c" />

        {/* Skull + cheeks + neck */}
        <path
          d="
            M 176,268
            L 226,268
            L 228,244
            L 238,190
            L 240,158
            L 224,122
            L 200,114
            L 176,122
            L 160,158
            L 162,190
            L 172,244
            Z
          "
          fill="#090c0c"
        />

        {/* Muzzle panel */}
        <path d="M 184,180 L 216,180 L 217,221 L 183,221 Z" fill="#ffffff" />

        {/* Chin curve */}
        <path
          d="M 183,219 Q 200,230 217,219 L 217,221 L 183,221 Z"
          fill="#e4e4e4"
        />

        {/* Nose */}
        <rect x="190" y="217" width="20" height="11" rx="4" fill="#090c0c" />

        {/* Left eye */}
        <ellipse cx="182" cy="163" rx="9" ry="7" fill="#ffffff" />
        <circle cx="183" cy="164" r="5" fill="#090c0c" />
        <circle cx="185" cy="162" r="1.8" fill="#ffffff" />

        {/* Right eye */}
        <ellipse cx="218" cy="163" rx="9" ry="7" fill="#ffffff" />
        <circle cx="217" cy="164" r="5" fill="#090c0c" />
        <circle cx="219" cy="162" r="1.8" fill="#ffffff" />

        {/* Eyebrow spots */}
        <ellipse cx="182" cy="149" rx="5.5" ry="3.5" fill="#ffffff" />
        <ellipse cx="218" cy="149" rx="5.5" ry="3.5" fill="#ffffff" />

        {/* Left paw */}
        <ellipse cx="162" cy="361" rx="7.5" ry="6.5" fill="#090c0c" />
        <ellipse cx="173" cy="358" rx="7.5" ry="6.5" fill="#090c0c" />
        <ellipse cx="184" cy="361" rx="7.5" ry="6.5" fill="#090c0c" />
        <rect x="150" y="361" width="48" height="30" rx="10" fill="#090c0c" />

        {/* Right paw */}
        <ellipse cx="216" cy="361" rx="7.5" ry="6.5" fill="#090c0c" />
        <ellipse cx="227" cy="358" rx="7.5" ry="6.5" fill="#090c0c" />
        <ellipse cx="238" cy="361" rx="7.5" ry="6.5" fill="#090c0c" />
        <rect x="202" y="361" width="48" height="30" rx="10" fill="#090c0c" />

        {/* Page-Specific Cyber Collar Emblem Badge */}
        {renderCollarBadge()}
      </svg>
    </div>
  );
}
