import { useState, useRef, useEffect } from 'react'
import { Toaster, toast } from 'sonner'
import { Eye } from 'lucide-react'
import './App.css'
import SearchBar from './components/SearchBar'
import ImageGallery from './components/ImageGallery'
import IndexControls from './components/IndexControls'

const API_URL = 'http://localhost:8000'

function App() {
  const [searchResults, setSearchResults] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [status, setStatus] = useState(null)
  const [indexProgress, setIndexProgress] = useState(null)
  const [isDragging, setIsDragging] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedFolders, setSelectedFolders] = useState([])
  const [indexedFolders, setIndexedFolders] = useState([])
  const pollRef = useRef(null)

  const handleSearch = async (query, options = {}) => {
    const { useHybrid = true, maxResults = 100, minMatch = 0, skipHistory = false, folderPaths = null } = options
    setIsLoading(true)
    setSearchQuery(query)

    // Update URL if not skipping history (history state)
    if (!skipHistory) {
      const url = new URL(window.location)
      url.searchParams.set('q', query)
      if (folderPaths && folderPaths.length > 0) url.searchParams.set('folders', folderPaths.join(','))
      else url.searchParams.delete('folders')
      window.history.pushState({ query, options }, '', url)
    }

    try {
      const response = await fetch(`${API_URL}/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          query, 
          top_k: maxResults, 
          use_hybrid: useHybrid,
          folder_paths: folderPaths
        })
      })
      
      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Search failed')
      }
      
      const results = await response.json()
      // Filter by minMatch on client side
      const filteredResults = results.filter(r => r.score >= minMatch)
      setSearchResults(filteredResults)
      
      if (filteredResults.length === 0 && results.length > 0) {
        toast.info(`Found ${results.length} results, but none matched your quality threshold of ${(minMatch * 100).toFixed(0)}%.`)
      }
    } catch (error) {
      console.error('Search error:', error)
      toast.error(`Search failed: ${error.message}`)
    } finally {
      setIsLoading(false)
    }
  }

  const handleVisualSearch = async (file, folderPaths = null) => {
    setIsLoading(true)
    setSearchResults([]) // Clear existing results
    
    const formData = new FormData()
    formData.append('file', file)
    if (folderPaths && folderPaths.length > 0) {
      folderPaths.forEach(path => formData.append('folder_paths', path))
    }
    
    try {
      const response = await fetch(`${API_URL}/api/search-image`, {
        method: 'POST',
        body: formData
      })
      
      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Visual search failed')
      }
      
      const results = await response.json()
      setSearchResults(results)
      toast.success(`Found ${results.length} visually similar images!`)
    } catch (error) {
      console.error('Visual search error:', error)
      toast.error(`Visual search failed: ${error.message}`)
    } finally {
      setIsLoading(false)
    }
  }

  const handleSearchSimilar = async (imagePath, folderPaths = null) => {
    setIsLoading(true)
    setSearchResults([]) // Clear existing results
    
    try {
      const response = await fetch(`${API_URL}/api/search-similar`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          image_path: imagePath, 
          top_k: 100,
          folder_paths: folderPaths 
        })
      })
      
      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Similar search failed')
      }
      
      const results = await response.json()
      setSearchResults(results)
      toast.success(`Found ${results.length} similar images!`)
    } catch (error) {
      console.error('Similar search error:', error)
      toast.error(`Similar search failed: ${error.message}`)
    } finally {
      setIsLoading(false)
    }
  }

  const handleIndex = async (folderPath) => {
    setIsLoading(true)
    setIndexProgress(null)
    // Add to selected folders if not already there
    setSelectedFolders(prev => prev.includes(folderPath) ? prev : [...prev, folderPath])

    // Start polling /progress every 500ms
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`${API_URL}/progress`)
        if (res.ok) {
          const data = await res.json()
          setIndexProgress(data)
          // Stop polling once the indexer reports done and is no longer running
          if (!data.is_running && data.phase === 'done') {
            clearInterval(pollRef.current)
            pollRef.current = null
          }
        }
      } catch (_) { /* ignore transient errors */ }
    }, 3000)

    try {
      const response = await fetch(`${API_URL}/index`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ folder_path: folderPath })
      })
      
      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Indexing failed')
      }
      
      const result = await response.json()
      toast.success(`Successfully indexed ${result.images_indexed} images!`)
      fetchStatus()
    } catch (error) {
      console.error('Indexing error:', error)
      toast.error(`Indexing failed: ${error.message}`)
    } finally {
      // Stop polling
      if (pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
      
      // Fetch final progress state one last time to show "Done!"
      try {
        const res = await fetch(`${API_URL}/progress`)
        if (res.ok) {
          const data = await res.json()
          setIndexProgress(data)
        }
      } catch (e) { console.error("Final progress fetch failed", e) }

      setIsLoading(false)
      
      // Keep the "Done!" status visible for 3 seconds, then hide it
      setTimeout(() => {
        setIndexProgress(null)
      }, 3000)
    }
  }

  const fetchStatus = async () => {
    try {
      const response = await fetch(`${API_URL}/status`)
      const data = await response.json()
      setStatus(data)
      if (data.indexed_folders && data.indexed_folders.length > 0) {
        setIndexedFolders(data.indexed_folders)
        // Default to all folders if none set
        setSelectedFolders(prev => prev.length > 0 ? prev : [])
      } else {
        setIndexedFolders([])
      }
    } catch (error) {
      console.error('Status fetch error:', error)
    }
  }

  useEffect(() => {
    fetchStatus()

    // Handle initial search from URL
    const urlParams = new URLSearchParams(window.location.search)
    const q = urlParams.get('q')
    const folders = urlParams.get('folders')?.split(',')
    if (q) {
      handleSearch(q, { skipHistory: true, folderPaths: folders })
    }

    // Handle back/forward navigation
    const handlePopState = (event) => {
      const params = new URLSearchParams(window.location.search)
      const q = params.get('q')
      const folders = params.get('folders')?.split(',')
      if (q) {
        handleSearch(q, { skipHistory: true, folderPaths: folders })
      } else {
        setSearchResults([])
        setSearchQuery('')
      }
    }

    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [])

  // Global Keyboard Shortcuts
  useEffect(() => {
    const handleGlobalKeyDown = (e) => {
      // Don't trigger if user is already typing in an input
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
        if (e.key === 'Escape') {
          e.target.blur()
        }
        return
      }

      if (e.key === '/') {
        e.preventDefault()
        const searchInput = document.querySelector('.search-input')
        if (searchInput) searchInput.focus()
      } else if (e.key === 'Escape') {
        // Just blur any active input, don't reset state
      }
    }

    window.addEventListener('keydown', handleGlobalKeyDown)
    return () => window.removeEventListener('keydown', handleGlobalKeyDown)
  }, [])

  useEffect(() => {
    document.title = 'Sightline | Local Image Intelligence'
  }, [])

  const handleDragOver = (e) => {
    e.preventDefault()
    if (status?.indexed && !isLoading) {
      setIsDragging(true)
    }
  }

  const handleDragLeave = (e) => {
    e.preventDefault()
    setIsDragging(false)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setIsDragging(false)
    
    if (!status?.indexed || isLoading) return

    const file = e.dataTransfer.files[0]
    if (file && file.type.startsWith('image/')) {
      handleVisualSearch(file, selectedFolders)
    } else {
      toast.error('Please drop a valid image file')
    }
  }

  const handleStopIndexing = async () => {
    try {
      const response = await fetch(`${API_URL}/api/stop-indexing`, {
        method: 'POST'
      })
      if (!response.ok) throw new Error('Failed to stop indexing')
      toast.info('Stopping indexing...')
    } catch (error) {
      toast.error(error.message)
    }
  }

  const handleRemoveFolder = async (folderPath) => {
    try {
      const response = await fetch(`${API_URL}/api/remove-folder`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ folder_path: folderPath })
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Failed to remove folder')
      }

      const result = await response.json()
      toast.success(result.message)
      
      // Update local state
      setIndexedFolders(prev => prev.filter(f => f !== folderPath))
      setSelectedFolders(prev => prev.filter(f => f !== folderPath))
    } catch (error) {
      console.error('Remove folder error:', error)
      toast.error(`Failed to remove folder: ${error.message}`)
    }
  }

  return (
    <div 
      className={`app ${isDragging ? 'dragging' : ''}`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {isDragging && (
        <div className="drop-overlay">
          <div className="drop-message">
            <p>Drop image to search for similar ones</p>
          </div>
        </div>
      )}
      <header className="header">
        <div className="header-container">
          <div className="brand-section">
            <div className="logo-wrapper">
              <Eye size={32} strokeWidth={2.5} />
            </div>
            <div className="title-text">
              <h1>Sightline</h1>
              <p className="subtitle">Local Image Intelligence</p>
            </div>
          </div>

          <div className="stats-section">
            <div className="stat-pill">
              <span className="stat-label">Folders</span>
              <span className="stat-value">{status?.indexed_folders?.length || 0}</span>
            </div>
            <div className="stat-pill">
              <span className="stat-label">Images</span>
              <span className="stat-value">{(status?.num_images || 0).toLocaleString()}</span>
            </div>
            <div className="status-indicator">
              <div className={`status-dot ${indexProgress?.is_running ? 'busy' : 'ready'}`} />
              <span className="status-text">
                {indexProgress?.is_running ? 'Indexing...' : 'System Ready'}
              </span>
            </div>
          </div>
        </div>
      </header>

      <main className="main">
        <IndexControls 
          onIndex={handleIndex} 
          disabled={isLoading} 
          indexProgress={indexProgress} 
          indexedFolders={indexedFolders}
          selectedFolders={selectedFolders}
          onSelectFolders={setSelectedFolders}
          onRemoveFolder={handleRemoveFolder}
          onStop={handleStopIndexing}
        />
        
        <div className="search-section">
          <SearchBar 
            onSearch={handleSearch} 
            disabled={isLoading || !status?.indexed} 
            initialQuery={searchQuery}
            selectedFolders={selectedFolders}
          />
          
          {isLoading && (
            <div className="loading">
              <div className="spinner"></div>
              <p>Processing...</p>
            </div>
          )}
          
          {!isLoading && searchResults.length > 0 && (
            <ImageGallery 
              results={searchResults} 
              apiUrl={API_URL} 
              onSearchSimilar={(path) => handleSearchSimilar(path, selectedFolders)}
            />
          )}
          
          {!isLoading && searchResults.length === 0 && status?.indexed && (
            <div className="empty-state">
              <p>Enter a search query to find images</p>
            </div>
          )}
        </div>
      </main>
      <Toaster theme="dark" richColors closeButton position="top-right" />
    </div>
  )
}

export default App
