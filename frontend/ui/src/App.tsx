import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import AppShell from './layouts/AppShell'
import ImoveisList from './pages/ImoveisList'
import ImovelDetalhes from './pages/ImovelDetalhes'
import LeadsList from './pages/LeadsList'
import OpsDashboard from './pages/OpsDashboard'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<AppShell />}> 
          <Route index element={<Navigate to="/imoveis" replace />} />
          {/* ND Imóveis */}
          <Route path="imoveis" element={<ImoveisList />} />
          <Route path="imoveis/:id" element={<ImovelDetalhes />} />
          <Route path="leads" element={<LeadsList />} />
          <Route path="ops" element={<OpsDashboard />} />
          <Route path="*" element={<Navigate to="/imoveis" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
