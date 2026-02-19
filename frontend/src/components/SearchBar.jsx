import { useState, useEffect } from 'react'
import { Settings, Search, Filter, Globe } from 'lucide-react'
import './SearchBar.css'

function SearchBar({ onSearch, disabled, initialQuery = '', selectedFolders = [] }) {
  const [query, setQuery] = useState(initialQuery)
  const [useHybrid, setUseHybrid] = useState(true)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [maxResults, setMaxResults] = useState(100)
  const [minMatch, setMinMatch] = useState(0)

  // Sync with prop when it changes (e.g. browser back button)
  useEffect(() => {
    setQuery(initialQuery)
  }, [initialQuery])

  const handleSubmit = (e) => {
    if (e) e.preventDefault()
    if (query.trim()) {
      onSearch(query.trim(), {
        useHybrid,
        maxResults,
        minMatch: minMatch / 100, // Convert percentage to 0-1
        folderPaths: selectedFolders.length > 0 ? selectedFolders : null
      })
    }
  }

  // Auto-refetch when parameters change
  useEffect(() => {
    // We only auto-refetch if there's an actual query and it's not the initial mount
    // The query itself is handled by the user pressing enter or clicking search
    // to avoid excessive API calls while typing.
    if (query.trim()) {
      handleSubmit()
    }
  }, [useHybrid, maxResults, minMatch, selectedFolders])

  const getScopeLabel = () => {
    if (selectedFolders.length === 0) {
      return (
        <span className="scope-badge global">
          <Globe size={14} />
          Searching everywhere
        </span>
      )
    }
    if (selectedFolders.length === 1) {
      const name = selectedFolders[0].split(/[/\\]/).pop() || selectedFolders[0]
      return (
        <span className="scope-badge filtered">
          <Filter size={14} />
          Searching in '{name}'
        </span>
      )
    }
    return (
      <span className="scope-badge filtered">
        <Filter size={14} />
        Searching in {selectedFolders.length} folders
      </span>
    )
  }

  return (
    <form className="search-bar" onSubmit={handleSubmit}>
      <div className="search-input-wrapper">
        <div className="icon-wrapper">
          <Search size={20} />
        </div>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search for images... (e.g., 'sunset over mountains', 'cat playing')"
          disabled={disabled}
          className="search-input"
        />
        <button type="submit" disabled={disabled || !query.trim()} className="search-button">
          Search
        </button>
      </div>
      
      <div className="search-controls">
        <div className="control-group">
          <label className="type-toggle" data-tooltip="Enable text-in-image searching">
            <input
              type="checkbox"
              checked={useHybrid}
              onChange={(e) => setUseHybrid(e.target.checked)}
              disabled={disabled}
            />
            <span className="toggle-label">Text Search</span>
          </label>

          <div className="search-scope">
            {getScopeLabel()}
          </div>
        </div>

        <button 
          type="button" 
          className={`settings-toggle-btn ${showAdvanced ? 'active' : ''}`} 
          onClick={() => setShowAdvanced(!showAdvanced)}
        >
          <Settings size={16} />
          <span>{showAdvanced ? 'Hide Settings' : 'Advanced'}</span>
        </button>
      </div>

      {showAdvanced && (
        <div className="advanced-panel">
          <div className="setting-group">
            <div className="setting-label">
              <span>Max Results</span>
              <span className="value">{maxResults}</span>
            </div>
            <input
              type="range"
              min="20"
              max="500"
              step="20"
              value={maxResults}
              onChange={(e) => setMaxResults(parseInt(e.target.value))}
              className="range-input"
            />
          </div>

          <div className="setting-group">
            <div className="setting-label">
              <span>Min Match Quality</span>
              <span className="value">{minMatch}%</span>
            </div>
            <input
              type="range"
              min="0"
              max="90"
              step="5"
              value={minMatch}
              onChange={(e) => setMinMatch(parseInt(e.target.value))}
              className="range-input"
            />
          </div>
        </div>
      )}
    </form>
  )
}

export default SearchBar
