import { useEffect, useState } from 'react'

export default function TradeIdeas() {
  const [ideas, setIdeas] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true)
        setError('')
        const response = await fetch('http://localhost:5000/api/team/trade-ideas')
        const data = await response.json()
        if (!response.ok) {
          throw new Error(data.error || 'Failed to load trade ideas')
        }
        setIdeas(data.trade_ideas || [])
      } catch (err) {
        setError(err.message || 'Failed to load trade ideas')
      } finally {
        setLoading(false)
      }
    }

    load()
  }, [])

  if (loading) {
    return <p>Loading trade ideas...</p>
  }

  if (error) {
    return <p className="error">{error}</p>
  }

  if (!ideas.length) {
    return <p className="empty-state">No clear upgrade trades found right now.</p>
  }

  return (
    <section className="trade-grid">
      {ideas.map((idea, index) => (
        <article className="trade-card" key={`${idea.drop_player}-${idea.add_player}-${index}`}>
          <p className="trade-swap">
            <span className="drop-player">Drop: {idea.drop_player}</span>
            <span className="add-player">Add: {idea.add_player}</span>
          </p>
          <p className="trade-metric">
            Value change: <strong>+{idea.improvement}</strong>
          </p>
          <p className="trade-metric">Shared position: {idea.shared_positions.join(', ')}</p>
          <p className="trade-metric">Yahoo rostered: {idea.ownership_percent}%</p>
        </article>
      ))}
    </section>
  )
}
