import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import Overview from './pages/Overview';
import Traffic from './pages/Traffic';
import Canaries from './pages/Canaries';
import Probes from './pages/Probes';
import Cases from './pages/Cases';
import CaseDetail from './pages/CaseDetail';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Overview />} />
          <Route path="traffic" element={<Traffic />} />
          <Route path="canaries" element={<Canaries />} />
          <Route path="probes" element={<Probes />} />
          <Route path="cases" element={<Cases />} />
          <Route path="cases/:id" element={<CaseDetail />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
