import { useState } from 'react'

function parseInputNames(value) {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

export default function TradeIdeas({ teamNumber }) {
  const [loading, setLoading] = useState(false)
  const [tradeAwayInput, setTradeAwayInput] = useState('')
  const [receiveInput, setReceiveInput] = useState('')
  const [result, setResult] = useState(null)

  const handleCompare = async (event) => {
    event.preventDefault()
    const tradeAwayNames = parseInputNames(tradeAwayInput)
    const receiveNames = parseInputNames(receiveInput)
    if (!tradeAwayNames.length || !receiveNames.length) {
      return
    }

    try {
      setLoading(true)
      const response = await fetch('http://localhost:5000/api/team/trade-compare', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          trade_away: tradeAwayNames,
          trade_for: receiveNames,
          team_number: teamNumber,
        }),
      })
      const data = await response.json()
      if (response.ok) {
        setResult({
          away: data.trade_away,
          receive: data.trade_for,
          delta: Number(data.delta || 0),
          winner: data.winner || 'even',
        })
      }
    } finally {
      setLoading(false)
    }
  }

  if (loading && !result) return <p>Loading trade analysis...</p>

  return (
    <section className="trade-evaluator-shell">
      <form className="trade-form" onSubmit={handleCompare}>
        <div className="trade-input-block">
          <label htmlFor="trade-away-input">Players You Trade Away</label>
          <textarea
            id="trade-away-input"
            value={tradeAwayInput}
            onChange={(event) => setTradeAwayInput(event.target.value)}
            placeholder="Example: Julius Randle, Josh Hart"
            rows={3}
          />
        </div>

        <div className="trade-input-block">
          <label htmlFor="receive-input">Players You Receive</label>
          <textarea
            id="receive-input"
            value={receiveInput}
            onChange={(event) => setReceiveInput(event.target.value)}
            placeholder="Example: Jalen Brunson, OG Anunoby"
            rows={3}
          />
        </div>

        <button className="trade-compare-btn" type="submit">
          Compare Trade
        </button>
      </form>

      {result && (
        <article className="trade-result-card">
          <div className="trade-result-top">
            <h3>Trade Result</h3>
            <span className={`winner-pill ${result.winner === 'your_side' ? 'win' : result.winner === 'other_side' ? 'lose' : 'even'}`}>
              {result.winner === 'your_side'
                ? 'You are winning'
                : result.winner === 'other_side'
                  ? 'Other team is winning'
                  : 'Trade is even'}
            </span>
          </div>

          <p className="trade-totals">
            You send: <strong>{result.away.total}</strong> | You receive: <strong>{result.receive.total}</strong>
          </p>
          <p className={`trade-delta ${result.delta > 0 ? 'positive' : result.delta < 0 ? 'negative' : ''}`}>
            Net value: {result.delta > 0 ? '+' : ''}{result.delta}
          </p>
        </article>
      )}
    </section>
  )
}
