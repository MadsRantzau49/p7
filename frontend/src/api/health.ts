import { apiClient } from './client'

export type HealthStatus = 'checking' | 'healthy' | 'unhealthy'

// Asks the backend whether it and its database are up. A 503, a network error or a timeout all
// count as unhealthy.
export async function checkHealth(): Promise<boolean> {
  try {
    const response = await apiClient.get<{ status: string }>('subtrajectories/health', { timeout: 5000 })
    return response.data.status === 'healthy'
  } catch {
    return false
  }
}
