import { BrowserRouter, Routes, Route } from 'react-router-dom';
import AppShell from './components/layout/AppShell';
import DashboardPage from './pages/DashboardPage';
import ScrapePersonPage from './pages/ScrapePersonPage';
import ScrapeCompanyPage from './pages/ScrapeCompanyPage';
import ScrapeJobPage from './pages/ScrapeJobPage';
import ScrapePostsPage from './pages/ScrapePostsPage';
import HistoryPage from './pages/HistoryPage';
import ResultDetailPage from './pages/ResultDetailPage';
import SessionsPage from './pages/SessionsPage';
import SettingsPage from './pages/SettingsPage';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/scrape/person" element={<ScrapePersonPage />} />
          <Route path="/scrape/company" element={<ScrapeCompanyPage />} />
          <Route path="/scrape/job" element={<ScrapeJobPage />} />
          <Route path="/scrape/posts" element={<ScrapePostsPage />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/history/:jobId" element={<ResultDetailPage />} />
          <Route path="/sessions" element={<SessionsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
