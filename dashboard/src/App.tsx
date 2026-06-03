import { useState, useCallback } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { OverviewPage } from './pages/OverviewPage';
import { VisitorsPage } from './pages/VisitorsPage';
import { FunnelPage } from './pages/FunnelPage';
import { HeatmapPage } from './pages/HeatmapPage';
import { AnomaliesPage } from './pages/AnomaliesPage';
import { HealthPage } from './pages/HealthPage';
import { JourneysPage } from './pages/JourneysPage';
import { IdentityPage } from './pages/IdentityPage';

export default function App() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const handleRefresh = useCallback(() => {
    setIsRefreshing(true);
    setRefreshKey((k) => k + 1);
    setTimeout(() => setIsRefreshing(false), 1500);
  }, []);

  return (
    <BrowserRouter>
      <div className="flex h-screen bg-background overflow-hidden">
        {/* Sidebar */}
        <Sidebar collapsed={sidebarCollapsed} />

        {/* Main content */}
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
          <Header
            onToggleSidebar={() => setSidebarCollapsed(!sidebarCollapsed)}
            onRefresh={handleRefresh}
            isRefreshing={isRefreshing}
            systemHealthy={true}
          />

          {/* Page content */}
          <main className="flex-1 overflow-y-auto" key={refreshKey}>
            <Routes>
              <Route path="/" element={<OverviewPage />} />
              <Route path="/visitors" element={<VisitorsPage />} />
              <Route path="/funnel" element={<FunnelPage />} />
              <Route path="/heatmap" element={<HeatmapPage />} />
              <Route path="/anomalies" element={<AnomaliesPage />} />
              <Route path="/health" element={<HealthPage />} />
              <Route path="/journeys" element={<JourneysPage />} />
              <Route path="/identity" element={<IdentityPage />} />
            </Routes>
          </main>
        </div>
      </div>
    </BrowserRouter>
  );
}
