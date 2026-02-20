import { useEffect, useMemo, useState } from 'react'

export default function GeneralStatistics() {
  const [payload, setPayload] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true)
        setError('')
        const response = await fetch('http://localhost:5000/api/team/value-stats')
        const data = await response.json()
        if (!response.ok) {
          throw new Error(data.error || 'Failed to load value stats')
        }
        setPayload(data)
      } catch (err) {
        setError(err.message || 'Failed to load value stats')
      } finally {
        setLoading(false)
      }
    }

    load()
  }, [])

  const maxValue = useMemo(() => {
    if (!payload?.players?.length) {
      return 1
    }
    return Math.max(...payload.players.map((p) => p.fantasy_value), 1)
  }, [payload])

  if (loading) {
    return <p>Loading value stats...</p>
  }

  if (error) {
    return <p className="error">{error}</p>
  }

  if (!payload?.players?.length) {
    return <p className="empty-state">No player stats available.</p>
  }

  const { summary } = payload

  return (
    <section>
      <div className="summary-grid">
        <article className="summary-card">
          <p className="summary-label">Highest Value</p>
          <h3>{summary.highest_player}</h3>
          <p className="summary-number">{summary.highest_value}</p>
        </article>
        <article className="summary-card">
          <p className="summary-label">Lowest Value</p>
          <h3>{summary.lowest_player}</h3>
          <p className="summary-number">{summary.lowest_value}</p>
        </article>
        <article className="summary-card">
          <p className="summary-label">Team Average</p>
          <h3>Fantasy Value</h3>
          <p className="summary-number">{summary.average_value}</p>
        </article>
      </div>

      <div className="value-list">
        {payload.players.map((player) => {
          const width = Math.max((player.fantasy_value / maxValue) * 100, 2)
          return (
            <article className="value-row" key={player.player_id ?? player.name}>
              <div className="value-row-top">
                <h4>{player.name}</h4>
                <span className="value-score">{player.fantasy_value}</span>
              </div>
              <div className="value-bar-track">
                <div className="value-bar-fill" style={{ width: `${width}%` }} />
              </div>
            </article>
          )
        })}
      </div>
    </section>
  )
}
