import { NavLink } from 'react-router-dom';

const ignitionLogo =
  'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="112" height="32"><rect width="112" height="32" rx="6" fill="%23259BD7"/><text x="56" y="21" font-size="13" text-anchor="middle" fill="white" font-family="Arial">Ignition</text></svg>';

const mainLinks = [
  { to: '/', label: 'Talk Track' },
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/compression', label: 'Compression' },
  { to: '/postgres', label: 'PostgreSQL (Lakebase)' },
  { to: '/analytics', label: 'Fleet health & revenue risk' },
  { to: '/market-weather', label: 'NEM market & BOM weather' },
  { to: '/assets', label: 'Assets' },
  { to: '/performance', label: 'Performance' },
  { to: '/architecture', label: 'Architecture' },
  { to: '/data-generation', label: 'Data Generation' },
];

const assetFrameworkLinks = [
  { to: '/asset-framework/hierarchy', label: 'Asset Hierarchy' },
  { to: '/asset-framework/templates', label: 'Templates' },
];

function NavItem({ to, label }: { to: string; label: string }) {
  return (
    <li>
      <NavLink
        to={to}
        end={to === '/'}
        className={({ isActive }) =>
          `block pl-3 py-2 pr-3 rounded-r text-sm transition-colors duration-200 border-l-4 -ml-px focus:outline-none focus-visible:ring-2 focus-visible:ring-databricks-primary focus-visible:ring-inset ${
            isActive
              ? 'border-l-databricks-primary bg-databricks-primary/5 text-databricks-primary font-medium'
              : 'border-l-transparent text-gray-600 hover:text-gray-900 hover:bg-gray-50'
          }`
        }
      >
        {label}
      </NavLink>
    </li>
  );
}

export default function Sidebar() {
  return (
    <nav className="w-56 flex-shrink-0 bg-surface-card border-r border-gray-200 shadow-card flex flex-col">
      {/* Branding block — clear hierarchy and alignment */}
      <div className="p-4 pb-4 border-b border-gray-100">
        <div className="flex items-center gap-3 mb-3">
          <img
            src={ignitionLogo}
            alt="Ignition logo"
            className="h-7 w-auto object-contain flex-shrink-0"
            width={28}
            height={28}
          />
          <h1 className="text-base font-heading font-semibold text-ignition-blue leading-tight tracking-tight">
            OT
            <br />
            Lakehouse
          </h1>
        </div>
        <div className="flex items-center gap-2 text-xs text-databricks-primary font-medium">
          <span>Powered by Databricks</span>
        </div>
      </div>
      <div className="flex-1 overflow-auto p-4 pt-3">
        <p className="text-xs font-semibold uppercase tracking-wider text-gray-500 px-3 mb-2">
          Demo
        </p>
        <ul className="space-y-0.5">
          {mainLinks.map(({ to, label }) => (
            <NavItem key={to} to={to} label={label} />
          ))}
        </ul>
        <div className="mt-6">
          <p className="text-xs font-semibold uppercase tracking-wider text-gray-500 px-3 mb-2">
            Asset Framework
          </p>
          <ul className="space-y-0.5">
            {assetFrameworkLinks.map(({ to, label }) => (
              <NavItem key={to} to={to} label={label} />
            ))}
          </ul>
        </div>
      </div>
    </nav>
  );
}
