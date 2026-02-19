import './IndexProgress.css'

const PHASE_LABELS = {
  idle: 'Idle',
  scanning: 'Scanning folder...',
  loading: 'Loading images...',
  ocr: 'Extracting text (OCR)...',
  embedding: 'Generating embeddings...',
  saving: 'Saving index...',
  done: 'Done!',
}

function IndexProgress({ progress, onStop }) {
  if (!progress || (!progress.is_running && progress.phase === 'idle')) return null

  const { phase, total, processed, from_cache, new_or_modified, is_running } = progress

  const pct = total > 0 ? Math.round((processed / total) * 100) : 0
  const label = PHASE_LABELS[phase] ?? phase

  return (
    <div className={`index-progress ${is_running ? 'running' : 'finished'}`}>
      <div className="progress-header">
        <div className="phase-group">
          <span className="progress-phase">{label}</span>
          {total > 0 && (
            <span className="progress-count">{processed} / {total}</span>
          )}
        </div>
        {is_running && onStop && (
          <button className="stop-btn" onClick={onStop} title="Stop Indexing">
            Stop
          </button>
        )}
      </div>

      {total > 0 && (
        <div className="progress-bar-track">
          <div
            className="progress-bar-fill"
            style={{ width: `${pct}%` }}
          />
        </div>
      )}

      <div className="progress-stats">
        {from_cache > 0 && (
          <span className="stat cache">
            <span className="stat-dot cache-dot" />
            {from_cache} from cache
          </span>
        )}
        {new_or_modified > 0 && (
          <span className="stat new">
            <span className="stat-dot new-dot" />
            {new_or_modified} new / modified
          </span>
        )}
      </div>
    </div>
  )
}

export default IndexProgress
