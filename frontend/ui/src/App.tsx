import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import AppShell from './layouts/AppShell'
import ImoveisList from './pages/ImoveisList'
import ImovelDetalhes from './pages/ImovelDetalhes'
import ImovelNovo from './pages/ImovelNovo'
import ImovelEditar from './pages/ImovelEditar'
import LeadsList from './pages/LeadsList'
import OpsDashboard from './pages/OpsDashboard'
import ImportCsv from './pages/ImportCsv'
import About from './pages/About'
import Login from './pages/Login'
import UsersAdmin from './pages/UsersAdmin'
import AcceptInvite from './pages/AcceptInvite'
import SuperTenants from './pages/SuperTenants'
import ChatbotFlowsAdmin from './pages/ChatbotFlowsAdmin'
import RequireAuth from './components/RequireAuth'
import Reports from './pages/Reports'

// NOTE: legacy Kanban/Orders module intentionally not routed in this SaaS (real estate domain)

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<AppShell />}> 
          <Route index element={<Navigate to="/imoveis" replace />} />
          {/* ND Imóveis */}
          <Route path="imoveis" element={<ImoveisList />} />
          <Route path="imoveis/novo" element={<ImovelNovo />} />
          <Route path="imoveis/:id" element={<ImovelDetalhes />} />
          <Route path="imoveis/:id/editar" element={<RequireAuth><ImovelEditar /></RequireAuth>} />
          <Route path="import" element={<RequireAuth><ImportCsv /></RequireAuth>} />
          <Route path="leads" element={<LeadsList />} />
          <Route path="ops" element={<OpsDashboard />} />
          <Route path="reports" element={<RequireAuth><Reports /></RequireAuth>} />
                    <Route path="users" element={<RequireAuth><UsersAdmin /></RequireAuth>} />
          <Route path="flows" element={<RequireAuth><ChatbotFlowsAdmin /></RequireAuth>} />
          <Route path="super/tenants" element={<RequireAuth><SuperTenants /></RequireAuth>} />
          <Route path="sobre" element={<About />} />
          <Route path="*" element={<Navigate to="/imoveis" replace />} />
        </Route>
        <Route path="/login" element={<Login />} />
        <Route path="/accept-invite" element={<AcceptInvite />} />
      </Routes>
    </BrowserRouter>
  )
}
