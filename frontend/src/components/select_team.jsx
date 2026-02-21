export default function SelectTeam({ teams, teamNumber, onTeamChange, onContinue }) {
  if (!teams?.length) {
    return null
  }

  const formatLabel = (team) => {
    const base = (team.team_name || `Team ${team.team_number || '?'}`).toString()
    return base.length > 48 ? `${base.slice(0, 48)}...` : base
  }

  return (
    <>
      <label htmlFor="team-select">Select Team</label>
      <select
        id="team-select"
        className="setup-input"
        value={teamNumber}
        onChange={(event) => onTeamChange(event.target.value)}
      >
        {teams.map((team) => (
          <option key={team.team_key} value={team.team_number}>
            {formatLabel(team)}
          </option>
        ))}
      </select>

      <button className="setup-button accent" type="button" onClick={onContinue}>
        Continue
      </button>
    </>
  )
}
