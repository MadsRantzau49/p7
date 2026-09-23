import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import TrajectoryPage from './components/trajectoryPage'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <TrajectoryPage />
  </StrictMode>,
)
