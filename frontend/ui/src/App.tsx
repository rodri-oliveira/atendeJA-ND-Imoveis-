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
import CatalogList from './pages/CatalogList'
import CatalogVehicleDetails from './pages/CatalogVehicleDetails'
import CatalogVehicleNew from './pages/CatalogVehicleNew'
import CatalogVehicleEdit from './pages/CatalogVehicleEdit'
import CatalogAdmin from './pages/CatalogAdmin'
import RequireAuth from './components/RequireAuth'
import RequireAdmin from './components/RequireAdmin'
import Reports from './pages/Reports'
import { TenantProvider } from './contexts/TenantContext'

// NOTE: legacy Kanban/Orders module intentionally not routed in this SaaS (real estate domain)

export default function App() {
  return (
    <TenantProvider>
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

          {/* Catálogo Genérico */}
          <Route path="catalog/vehicles" element={<RequireAuth><CatalogList /></RequireAuth>} />
          <Route path="catalog/vehicles/novo" element={<RequireAuth><CatalogVehicleNew /></RequireAuth>} />
          <Route path="catalog/vehicles/:id" element={<RequireAuth><CatalogVehicleDetails /></RequireAuth>} />
          <Route path="catalog/vehicles/:id/editar" element={<RequireAuth><CatalogVehicleEdit /></RequireAuth>} />
          <Route path="catalog/admin" element={<RequireAdmin><CatalogAdmin /></RequireAdmin>} />
          <Route path="users" element={<RequireAdmin><UsersAdmin /></RequireAdmin>} />
          <Route path="flows" element={<RequireAdmin><ChatbotFlowsAdmin /></RequireAdmin>} />
          <Route path="super/tenants" element={<RequireAdmin><SuperTenants /></RequireAdmin>} />
          <Route path="sobre" element={<About />} />
          <Route path="*" element={<Navigate to="/imoveis" replace />} />
        </Route>
        <Route path="/login" element={<Login />} />
        <Route path="/accept-invite" element={<AcceptInvite />} />
      </Routes>
    </BrowserRouter>
  </TenantProvider>
  )
}
