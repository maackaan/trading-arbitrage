import { useEffect, useState } from 'react'
import { NavLink, Navigate, Route, Routes } from 'react-router-dom'

import { fetchHealth } from './api/client'
import { SearchPage } from './pages/SearchPage'
import { SkinDetailsPage } from './pages/SkinDetailsPage'
import { DealsPage } from './pages/DealsPage'
import { NewListingsPage } from './pages/NewListingsPage'

import './App.css'

function App() {
  const [health, setHealth] = useState('checking...')

  useEffect(() => {
    void fetchHealth()
      .then((data) => setHealth(`${data.status}${data.use_mock_providers ? ' (mock mode)' : ''}`))
      .catch(() => setHealth('backend unavailable'))
  }, [])

  return (
    <div className="layout">
      <header className="topbar">
        <h1>CS2 Price Comparator</h1>
        <nav>
          <NavLink to="/search">Search</NavLink>
          <NavLink to="/deals">Deals</NavLink>
          <NavLink to="/listings">New listings</NavLink>
        </nav>
        <p className="status">API: {health}</p>
      </header>

      <main>
        <Routes>
          <Route path="/" element={<Navigate to="/search" replace />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/skins/:skinId" element={<SkinDetailsPage />} />
          <Route path="/deals" element={<DealsPage />} />
          <Route path="/listings" element={<NewListingsPage />} />
        </Routes>
      </main>
    </div>
  )
}

export default App
