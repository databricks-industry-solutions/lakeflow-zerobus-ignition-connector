# Zerobus Connector Frontend (legacy React)

This folder contains a legacy React-based configuration UI.

**Current implementation**: the module serves a static HTML UI from:
- `module/src/main/resources/web/zerobus-config.html` (served at `GET /system/zerobus/configure`)

Ignition 8.3 integrates this UI into the left navigation via a small SystemJS shim:
- `module/src/main/resources/mounted/js/web-ui/zerobus.js`

## Development

### Prerequisites

- Node.js 18.x or higher
- npm 9.x or higher

### Setup

```bash
# Install dependencies
npm install

# Start development server
npm start
```

The development server will run at `http://localhost:3000` and proxy API requests to `http://localhost:8088` (your Ignition Gateway).

### Building

```bash
# Build for production
npm run build
```

This creates optimized static files in the `build/` directory.

### Integration with Ignition Module

If you choose to revive the React UI, you can wire the output into the module’s web resources.
Today, the module does **not** require this React build to function.

These files are then packaged into the `.modl` file and served by the Ignition Gateway at `/system/zerobus/` (or configured mount point).

## Component Structure

```
src/
├── App.js          - Main configuration UI component
├── App.css         - Styling
├── index.js        - React entry point
└── index.css       - Global styles
```

## REST API Integration

The UI expects the following Gateway REST endpoints (to be implemented in Java):

- `GET /system/zerobus/config` - Load current configuration
- `POST /system/zerobus/config` - Save configuration
- `POST /system/zerobus/test-connection` - Test Databricks connection
- `GET /system/zerobus/diagnostics` - Get diagnostics info

The REST endpoints are implemented in the Java module under `/system/zerobus/*`.

## Configuration Fields

The UI manages all ConfigModel fields:
- **Databricks Connection**: Workspace URL, OAuth credentials, target table
- **Tag Selection**: Mode (folder/pattern/explicit) and paths
- **Performance**: Batch size, flush interval, queue size, rate limit
- **Control**: Enable/disable, debug logging

## Proxy Configuration

During development, API requests are proxied to `http://localhost:8088` as configured in `package.json`:

```json
"proxy": "http://localhost:8088"
```

This avoids CORS issues when testing against a local Ignition Gateway.

## Production Build

The production build is optimized and minified. Static assets (JS, CSS, images) have content hashes for cache busting.

## Browser Support

Supports modern browsers:
- Chrome (last 2 versions)
- Firefox (last 2 versions)
- Safari (last 2 versions)
- Edge (last 2 versions)

