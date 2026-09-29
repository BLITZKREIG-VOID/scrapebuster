import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import Overview from './pages/Overview';
import Traffic from './pages/Traffic';
import Canaries from './pages/Canaries';
import Probes from './pages/Probes';
import Cases from './pages/Cases';
import CaseDetail from './pages/CaseDetail';

import About from './pages/About';

import Welcome from './pages/Welcome';
import Login from './pages/Login';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<Welcome />} />
        <Route path="/dashboard" element={<Layout />}>
          <Route index element={<Overview />} />
          <Route path="about" element={<About />} />
          <Route path="traffic" element={<Traffic />} />
          <Route path="canaries" element={<Canaries />} />
          <Route path="probes" element={<Probes />} />
          <Route path="cases" element={<Cases />} />
          <Route path="cases/:id" element={<CaseDetail />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
