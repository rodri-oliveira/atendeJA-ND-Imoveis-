import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import AppShell from './layouts/AppShell'
import ImoveisList from './pages/ImoveisList'
import ImovelDetalhes from './pages/ImovelDetalhes'
import LeadsList from './pages/LeadsList'
import OpsDashboard from './pages/OpsDashboard'
import ImportCsv from './pages/ImportCsv'
import About from './pages/About'
import Login from './pages/Login'
import UsersAdmin from './pages/UsersAdmin'
import RequireAuth from './components/RequireAuth'
import Reports from './pages/Reports'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<AppShell />}> 
          <Route index element={<Navigate to="/imoveis" replace />} />
          {/* ND Imóveis */}
          <Route path="imoveis" element={<ImoveisList />} />
          <Route path="imoveis/:id" element={<ImovelDetalhes />} />
          <Route path="import" element={<RequireAuth><ImportCsv /></RequireAuth>} />
          <Route path="leads" element={<LeadsList />} />
          <Route path="ops" element={<OpsDashboard />} />
          <Route path="reports" element={<RequireAuth><Reports /></RequireAuth>} />
          <Route path="users" element={<RequireAuth><UsersAdmin /></RequireAuth>} />
          <Route path="sobre" element={<About />} />
          <Route path="*" element={<Navigate to="/imoveis" replace />} />
        </Route>
        <Route path="/login" element={<Login />} />
      </Routes>
    </BrowserRouter>
  )
}
