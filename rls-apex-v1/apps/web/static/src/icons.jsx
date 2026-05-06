// minimal stroke icon set — 16px optical, 1.5 stroke
const Icon = ({ d, size = 16, stroke = 1.5, fill = "none", className, style }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill={fill}
    stroke="currentColor"
    strokeWidth={stroke}
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    style={style}
    aria-hidden="true"
  >
    {typeof d === "string" ? <path d={d} /> : d}
  </svg>
);

const I = {
  Dashboard: (p) => <Icon {...p} d={<><rect x="3" y="3" width="7" height="9" rx="1.5" /><rect x="14" y="3" width="7" height="5" rx="1.5" /><rect x="14" y="12" width="7" height="9" rx="1.5" /><rect x="3" y="16" width="7" height="5" rx="1.5" /></>} />,
  List: (p) => <Icon {...p} d={<><line x1="8" y1="6" x2="21" y2="6" /><line x1="8" y1="12" x2="21" y2="12" /><line x1="8" y1="18" x2="21" y2="18" /><circle cx="4" cy="6" r="1" fill="currentColor" /><circle cx="4" cy="12" r="1" fill="currentColor" /><circle cx="4" cy="18" r="1" fill="currentColor" /></>} />,
  Plus: (p) => <Icon {...p} d={<><line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" /></>} />,
  Sparkles: (p) => <Icon {...p} d={<><path d="M12 3l1.5 4.5L18 9l-4.5 1.5L12 15l-1.5-4.5L6 9l4.5-1.5L12 3z" /><path d="M19 14l.7 2.1L22 17l-2.3.9L19 20l-.7-2.1L16 17l2.3-.9L19 14z" /></>} />,
  Doc: (p) => <Icon {...p} d={<><path d="M14 3H7a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V8l-5-5z" /><path d="M14 3v5h5" /></>} />,
  Folder: (p) => <Icon {...p} d="M3 7a2 2 0 012-2h4l2 3h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V7z" />,
  Building: (p) => <Icon {...p} d={<><rect x="4" y="3" width="16" height="18" rx="1.5" /><line x1="8" y1="8" x2="8" y2="8.01" /><line x1="12" y1="8" x2="12" y2="8.01" /><line x1="16" y1="8" x2="16" y2="8.01" /><line x1="8" y1="12" x2="8" y2="12.01" /><line x1="12" y1="12" x2="12" y2="12.01" /><line x1="16" y1="12" x2="16" y2="12.01" /><line x1="10" y1="21" x2="10" y2="17" /><line x1="14" y1="21" x2="14" y2="17" /></>} />,
  Scale: (p) => <Icon {...p} d={<><line x1="12" y1="3" x2="12" y2="21" /><path d="M5 8l-3 6h6l-3-6z" /><path d="M19 8l-3 6h6l-3-6z" /><line x1="4" y1="21" x2="20" y2="21" /></>} />,
  Graph: (p) => <Icon {...p} d={<><circle cx="6" cy="6" r="2" /><circle cx="18" cy="6" r="2" /><circle cx="12" cy="18" r="2" /><line x1="7.5" y1="7" x2="11" y2="16.5" /><line x1="16.5" y1="7" x2="13" y2="16.5" /><line x1="8" y1="6" x2="16" y2="6" /></>} />,
  Library: (p) => <Icon {...p} d={<><line x1="4" y1="4" x2="4" y2="20" /><line x1="9" y1="4" x2="9" y2="20" /><path d="M14 5l5 1-3 14-5-1 3-14z" /></>} />,
  Search: (p) => <Icon {...p} d={<><circle cx="11" cy="11" r="7" /><line x1="16" y1="16" x2="21" y2="21" /></>} />,
  Filter: (p) => <Icon {...p} d="M4 5h16l-6 8v6l-4-2v-4L4 5z" />,
  Bell: (p) => <Icon {...p} d={<><path d="M6 9a6 6 0 1112 0c0 5 2 6 2 6H4s2-1 2-6z" /><path d="M10 20a2 2 0 004 0" /></>} />,
  Settings: (p) => <Icon {...p} d={<><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 00.3 1.8l.1.1a2 2 0 11-2.8 2.8l-.1-.1a1.7 1.7 0 00-1.8-.3 1.7 1.7 0 00-1 1.5V21a2 2 0 11-4 0v-.1a1.7 1.7 0 00-1.1-1.5 1.7 1.7 0 00-1.8.3l-.1.1a2 2 0 11-2.8-2.8l.1-.1a1.7 1.7 0 00.3-1.8 1.7 1.7 0 00-1.5-1H3a2 2 0 110-4h.1a1.7 1.7 0 001.5-1.1 1.7 1.7 0 00-.3-1.8l-.1-.1a2 2 0 112.8-2.8l.1.1a1.7 1.7 0 001.8.3H9a1.7 1.7 0 001-1.5V3a2 2 0 114 0v.1a1.7 1.7 0 001 1.5 1.7 1.7 0 001.8-.3l.1-.1a2 2 0 112.8 2.8l-.1.1a1.7 1.7 0 00-.3 1.8V9a1.7 1.7 0 001.5 1H21a2 2 0 110 4h-.1a1.7 1.7 0 00-1.5 1z" /></>} />,
  Chevron: (p) => <Icon {...p} d="M9 6l6 6-6 6" />,
  ChevronDown: (p) => <Icon {...p} d="M6 9l6 6 6-6" />,
  Check: (p) => <Icon {...p} d="M5 12l5 5L20 7" />,
  X: (p) => <Icon {...p} d={<><line x1="6" y1="6" x2="18" y2="18" /><line x1="6" y1="18" x2="18" y2="6" /></>} />,
  Alert: (p) => <Icon {...p} d={<><path d="M12 3l10 18H2L12 3z" /><line x1="12" y1="10" x2="12" y2="14" /><line x1="12" y1="18" x2="12" y2="18.01" /></>} />,
  Info: (p) => <Icon {...p} d={<><circle cx="12" cy="12" r="9" /><line x1="12" y1="8" x2="12" y2="8.01" /><line x1="12" y1="11" x2="12" y2="16" /></>} />,
  Clock: (p) => <Icon {...p} d={<><circle cx="12" cy="12" r="9" /><polyline points="12 7 12 12 15 14" /></>} />,
  Calendar: (p) => <Icon {...p} d={<><rect x="3" y="5" width="18" height="16" rx="2" /><line x1="3" y1="10" x2="21" y2="10" /><line x1="8" y1="3" x2="8" y2="7" /><line x1="16" y1="3" x2="16" y2="7" /></>} />,
  Paperclip: (p) => <Icon {...p} d="M21 12L12.5 20.5a5 5 0 01-7-7L14 5a3.5 3.5 0 015 5L9.5 19" />,
  User: (p) => <Icon {...p} d={<><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0116 0" /></>} />,
  Users: (p) => <Icon {...p} d={<><circle cx="9" cy="8" r="3.5" /><path d="M2.5 21a6.5 6.5 0 0113 0" /><circle cx="17" cy="9" r="3" /><path d="M14 14a5 5 0 017.5 4" /></>} />,
  Shield: (p) => <Icon {...p} d="M12 3l8 3v6c0 5-3.5 8.5-8 9-4.5-.5-8-4-8-9V6l8-3z" />,
  Bolt: (p) => <Icon {...p} d="M13 3L4 14h7l-1 7 9-11h-7l1-7z" />,
  Branch: (p) => <Icon {...p} d={<><circle cx="6" cy="6" r="2" /><circle cx="6" cy="18" r="2" /><circle cx="18" cy="9" r="2" /><path d="M6 8v8" /><path d="M18 11c0 5-6 4-6 7" /></>} />,
  Send: (p) => <Icon {...p} d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />,
  Eye: (p) => <Icon {...p} d={<><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" /><circle cx="12" cy="12" r="3" /></>} />,
  Hash: (p) => <Icon {...p} d={<><line x1="4" y1="9" x2="20" y2="9" /><line x1="4" y1="15" x2="20" y2="15" /><line x1="10" y1="3" x2="8" y2="21" /><line x1="16" y1="3" x2="14" y2="21" /></>} />,
  Map: (p) => <Icon {...p} d={<><path d="M9 4l-6 2v14l6-2 6 2 6-2V4l-6 2-6-2z" /><line x1="9" y1="4" x2="9" y2="18" /><line x1="15" y1="6" x2="15" y2="20" /></>} />,
  Lock: (p) => <Icon {...p} d={<><rect x="4" y="11" width="16" height="10" rx="2" /><path d="M8 11V7a4 4 0 018 0v4" /></>} />,
  Arrow: (p) => <Icon {...p} d={<><line x1="5" y1="12" x2="19" y2="12" /><polyline points="13 6 19 12 13 18" /></>} />,
  ArrowL: (p) => <Icon {...p} d={<><line x1="19" y1="12" x2="5" y2="12" /><polyline points="11 6 5 12 11 18" /></>} />,
  Dot: (p) => <Icon {...p} d={<circle cx="12" cy="12" r="4" fill="currentColor" />} />,
  Edit: (p) => <Icon {...p} d="M3 21l4-1 11-11-3-3L4 17l-1 4z" />,
  Copy: (p) => <Icon {...p} d={<><rect x="9" y="9" width="11" height="11" rx="1.5" /><path d="M5 15V5a2 2 0 012-2h10" /></>} />,
  Spark: (p) => <Icon {...p} d="M12 3v6M12 15v6M3 12h6M15 12h6" />,
  Robot: (p) => <Icon {...p} d={<><rect x="4" y="7" width="16" height="13" rx="2" /><circle cx="9" cy="13" r="1" fill="currentColor" /><circle cx="15" cy="13" r="1" fill="currentColor" /><line x1="12" y1="3" x2="12" y2="7" /><line x1="9" y1="17" x2="15" y2="17" /></>} />,
  Database: (p) => <Icon {...p} d={<><ellipse cx="12" cy="5" rx="8" ry="3" /><path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5" /><path d="M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6" /></>} />,
  Tag: (p) => <Icon {...p} d={<><path d="M3 12V4a1 1 0 011-1h8l9 9-9 9-9-9z" /><circle cx="8" cy="8" r="1.5" /></>} />,
};

window.I = I;
window.Icon = Icon;
