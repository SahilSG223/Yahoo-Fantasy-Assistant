import { useEffect, useState } from 'react'
import './App.css'
import DisplayTeam from './components/display_team'
import GeneralStatistics from './components/general_statistics'
import TradeIdeas from './components/trade_ideas'

function App() {
  const [tab, setTab] = useState('team')
  const [players, setPlayers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    document.title = 'Fantasy Assistant'

    const fetchTeam = async () => {
      try {
        setLoading(true)
        setError('')
        const response = await fetch('http://localhost:5000/api/team')
        const data = await response.json()
        if (!response.ok) {
          throw new Error(data.error || 'Failed to load team')
        }
        setPlayers(data.team || [])
      } catch (err) {
        setError(err.message || 'Failed to load team')
      } finally {
        setLoading(false)
      }
    }

    fetchTeam()
  }, [])

  return (
    <main className="app-shell">
      <header className="hero">
        <p className="eyebrow">2025-26 Season</p>
        <h1>Fantasy Assistant</h1>
      </header>

      <div className="tab-row">
        <button
          className={tab === 'team' ? 'tab-button active' : 'tab-button'}
          onClick={() => setTab('team')}
          type="button"
        >
          My Team
        </button>
        <button
          className={tab === 'stats' ? 'tab-button active' : 'tab-button'}
          onClick={() => setTab('stats')}
          type="button"
        >
          General Statistics
        </button>
        <button
          className={tab === 'trades' ? 'tab-button active' : 'tab-button'}
          onClick={() => setTab('trades')}
          type="button"
        >
          Trade Ideas
        </button>
      </div>

      {tab === 'team' && loading && <p>Loading team...</p>}
      {tab === 'team' && error && <p className="error">{error}</p>}
      {tab === 'team' && !loading && !error && <DisplayTeam players={players} />}
      {tab === 'stats' && <GeneralStatistics />}
      {tab === 'trades' && <TradeIdeas />}
    </main>
  )
}

export default App
