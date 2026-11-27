import type { HealthStatus } from '../api/health'

type Props = {
  status: HealthStatus
  onRetry: () => void
}

const MESSAGES: Record<HealthStatus, string> = {
  checking: 'Checking connection...',
  healthy: 'Connected',
  unhealthy: 'No connection, searching is disabled',
}

export default function HealthBanner({ status, onRetry }: Props) {
  return (
    <div className={`health-banner ${status}`} role="status" aria-live="polite">
      <span className="health-dot" aria-hidden="true" />
      <span>{MESSAGES[status]}</span>
    </div>
  )
}
