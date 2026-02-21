import { useEffect, useState } from 'react'
import './App.css'
import DisplayTeam from './components/display_team'
import GeneralStatistics from './components/general_statistics'
import SelectTeam from './components/select_team'
import TradeIdeas from './components/trade_ideas'

function App() {
  const [setupDone, setSetupDone] = useState(false)
  const [teamNumber, setTeamNumber] = useState('')
  const [teams, setTeams] = useState([])
  const [setupLoading, setSetupLoading] = useState(false)

  const [tab, setTab] = useState('team')
  const [players, setPlayers] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    document.title = 'Fantasy Assistant'
  }, [])

  const contextQuery = `team_number=${encodeURIComponent(teamNumber)}`

  const fetchTeams = async () => {
    try {
      setSetupLoading(true)
      const response = await fetch('http://localhost:5000/api/league/teams')
      const data = await response.json()
      if (response.ok) {
        const nextTeams = data.teams || []
        setTeams(nextTeams)
        if (nextTeams.length > 0) {
          setTeamNumber(nextTeams[0].team_number || '')
        }
      }
    } catch {
      setTeams([])
    } finally {
      setSetupLoading(false)
    }
  }

  useEffect(() => {
    if (!setupDone) {
      fetchTeams()
    }
  }, [setupDone])

  const startWithSelection = async () => {
    if (!teamNumber) {
      return
    }
    const fetchTeam = async () => {
      try {
        setLoading(true)
        const response = await fetch(`http://localhost:5000/api/team?${contextQuery}`)
        const data = await response.json()
        if (response.ok) {
          setPlayers(data.team || [])
          setSetupDone(true)
        }
      } catch {
      } finally {
        setLoading(false)
      }
    }

    fetchTeam()
  }

  if (!setupDone) {
    return (
      <main className="app-shell">
        <header className="hero">
          <p className="eyebrow">2025-26 Season</p>
          <h1>Fantasy Assistant</h1>
        </header>

        <section className="setup-card">
          <h2>Select Team</h2>
          <p className="setup-copy">Select your team from the list below.</p>

          <button className="setup-button" type="button" onClick={fetchTeams} disabled={setupLoading}>
            {setupLoading ? 'Loading Teams...' : 'Load Team Options'}
          </button>

          <SelectTeam
            teams={teams}
            teamNumber={teamNumber}
            onTeamChange={setTeamNumber}
            onContinue={startWithSelection}
          />
        </section>
      </main>
    )
  }

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
          Trade Analysis 
        </button>
      </div>

      {tab === 'team' && loading && <p>Loading team...</p>}
      {tab === 'team' && !loading && <DisplayTeam players={players} />}
      {tab === 'stats' && <GeneralStatistics teamNumber={teamNumber} />}
      {tab === 'trades' && <TradeIdeas teamNumber={teamNumber} />}
    </main>
  )
}

export default App
