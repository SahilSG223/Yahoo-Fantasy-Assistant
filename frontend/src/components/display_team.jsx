export default function DisplayTeam({ players }) {
  if (!players || players.length === 0) {
    return <p className="empty-state">No players found.</p>
  }

  return (
    <section className="team-grid">
      {players.map((player, index) => {
        const name = player.name?.full ?? player.name ?? "Unknown"
        const positions = Array.isArray(player.eligible_positions)
          ? player.eligible_positions
          : []

        return (
          <article
            className="player-card"
            key={`${player.player_id ?? name ?? "player"}-${index}`}
          >
            <h2>{name}</h2>
            <div className="position-row">
              {positions.length > 0 ? (
                positions.map((position) => (
                  <span
                    className="position-chip"
                    key={`${name}-${position}`}
                  >
                    {position}
                  </span>
                ))
              ) : (
                <span className="position-chip">N/A</span>
              )}
            </div>
          </article>
        )
      })}
    </section>
  )
}
