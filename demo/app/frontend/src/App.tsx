import { Routes, Route } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import Landing from './pages/Landing';
import Dashboard from './pages/Dashboard';
import PostgresDashboard from './pages/PostgresDashboard';
import Analytics from './pages/Analytics';
import MarketWeather from './pages/MarketWeather';
import Assets from './pages/Assets';
import AssetDetail from './pages/AssetDetail';
import Compression from './pages/Compression';
import Performance from './pages/Performance';
import Architecture from './pages/Architecture';
import AssetHierarchy from './pages/AssetHierarchy';
import AssetTemplates from './pages/AssetTemplates';
import DataGeneration from './pages/DataGeneration';

export default function App() {
  return (
    <div className="flex min-h-screen bg-surface-canvas text-gray-900">
      <Sidebar />
      <main className="flex-1 p-6 overflow-auto">
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/postgres" element={<PostgresDashboard />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/market-weather" element={<MarketWeather />} />
          <Route path="/assets" element={<Assets />} />
          <Route path="/assets/:id" element={<AssetDetail />} />
          <Route path="/compression" element={<Compression />} />
          <Route path="/performance" element={<Performance />} />
          <Route path="/architecture" element={<Architecture />} />
          <Route path="/data-generation" element={<DataGeneration />} />
          <Route path="/asset-framework/hierarchy" element={<AssetHierarchy />} />
          <Route path="/asset-framework/templates" element={<AssetTemplates />} />
        </Routes>
      </main>
    </div>
  );
}
