import { useState } from 'react'
import { Folder, Database, Info, Globe } from 'lucide-react'
import './IndexControls.css'
import IndexProgress from './IndexProgress'

function IndexControls({ onIndex, disabled, indexProgress, indexedFolders = [], selectedFolders = [], onSelectFolders, onRemoveFolder, onStop }) {
  const [folderPath, setFolderPath] = useState('')

  const handleSubmit = (e) => {
    e.preventDefault()
    if (folderPath.trim()) {
      onIndex(folderPath.trim())
    }
  }

  const getFolderName = (path) => {
    return path.split(/[/\\]/).pop() || path
  }

  const toggleFolder = (folder) => {
    if (selectedFolders.includes(folder)) {
      onSelectFolders(selectedFolders.filter(f => f !== folder))
    } else {
      onSelectFolders([...selectedFolders, folder])
    }
  }

  const handleContextMenu = (e, folder) => {
    e.preventDefault()
    if (window.confirm(`Remove "${getFolderName(folder)}" from search index?`)) {
      onRemoveFolder(folder)
    }
  }

  const selectAll = () => {
    onSelectFolders([]) // Empty means search all
  }

  return (
    <div className="index-controls">
      <div className="index-header">
        <div className="title-group">
          <Database size={20} className="icon" />
          <h3>Data Sources</h3>
        </div>
        <div className="header-actions">
          <button 
            className={`search-all-btn ${selectedFolders.length === 0 ? 'active' : ''}`}
            onClick={selectAll}
            data-tooltip="Search across all indexed folders"
          >
            <Globe size={14} />
            Search Everywhere
          </button>
          <p className="hint">
            <Info size={14} />
            Add folders to your collection.
          </p>
        </div>
      </div>

      {indexedFolders.length > 0 && (
        <div className="folders-list">
          {indexedFolders.map((folder, index) => {
            const isSelected = selectedFolders.includes(folder)
            return (
              <div 
                key={index} 
                className={`folder-item ${isSelected ? 'active' : ''}`}
                onClick={() => toggleFolder(folder)}
                onContextMenu={(e) => handleContextMenu(e, folder)}
                data-tooltip={folder}
              >
                <Folder size={16} />
                <span className="folder-name">{getFolderName(folder)}</span>
                {isSelected && <span className="active-badge">Active</span>}
              </div>
            )
          })}
        </div>
      )}

      <form onSubmit={handleSubmit} className="index-form">
        <input
          type="text"
          value={folderPath}
          onChange={(e) => setFolderPath(e.target.value)}
          placeholder="Add new folder path (e.g., C:\Photos)"
          disabled={disabled}
          className="folder-input"
        />
        <button type="submit" disabled={disabled || !folderPath.trim()} className="index-button">
          {indexProgress?.is_running ? 'Indexing...' : 'Add Source'}
        </button>
      </form>
      
      <IndexProgress progress={indexProgress} onStop={onStop} />
    </div>
  )
}

export default IndexControls
