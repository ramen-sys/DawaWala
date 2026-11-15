// Severity shapes differ as well as colour: circle, triangle, diamond and
// octagon. They are decorative; the band name is always written next to them.
export function SeverityIcon({ band, className = "size-5" }) {
  const common = { viewBox: "0 0 24 24", className, "aria-hidden": "true", focusable: "false" };
  switch (band) {
    case "Critical":
      return (
        <svg {...common}>
          <path d="M8.2 2h7.6L22 8.2v7.6L15.8 22H8.2L2 15.8V8.2z" fill="currentColor" />
          <path d="M12 6.5v7M12 16.2v1.6" stroke="#fff" strokeWidth="2.4" strokeLinecap="round" />
        </svg>
      );
    case "High":
      return (
        <svg {...common}>
          <path d="M12 1.8 22.2 12 12 22.2 1.8 12z" fill="currentColor" />
          <path d="M12 7v6M12 15.8v1.5" stroke="#fff" strokeWidth="2.4" strokeLinecap="round" />
        </svg>
      );
    case "Moderate":
      return (
        <svg {...common}>
          <path d="M12 2.5 22.5 21h-21z" fill="currentColor" />
          <path d="M12 9.5v5.5M12 17.3v1" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" />
        </svg>
      );
    default:
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" strokeWidth="2.2" />
          <path d="M12 11v6M12 7.2v1.2" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
        </svg>
      );
  }
}

export function CapsuleMark({ className = "size-7" }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden="true" focusable="false">
      <g transform="rotate(-40 16 16)">
        <rect x="3" y="10" width="26" height="12" rx="6" fill="#fff" />
        <path d="M16 10h7a6 6 0 0 1 0 12h-7z" fill="#3FB8BC" />
      </g>
    </svg>
  );
}
