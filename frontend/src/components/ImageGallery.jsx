import { useState, useEffect, useRef } from 'react'
import ImageLightbox from './ImageLightbox'
import './ImageGallery.css'
import MatchScore from './MatchScore'

const RESULTS_PER_PAGE = 30

function ImageGallery({ results, apiUrl, onSearchSimilar }) {
  const [selectedImageIndex, setSelectedImageIndex] = useState(null)
  const [visibleCount, setVisibleCount] = useState(RESULTS_PER_PAGE)
  const [contextMenu, setContextMenu] = useState(null)
  const loaderRef = useRef(null)

  // Reset visible count when results change
  useEffect(() => {
    setVisibleCount(RESULTS_PER_PAGE)
  }, [results])

  // Infinite Scroll Observer
  useEffect(() => {
    const observer = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting && visibleCount < results.length) {
        setVisibleCount(prev => Math.min(prev + RESULTS_PER_PAGE, results.length))
      }
    }, { threshold: 1.0 })

    if (loaderRef.current) observer.observe(loaderRef.current)
    return () => observer.disconnect()
  }, [visibleCount, results.length])

  // Close context menu on click elsewhere
  useEffect(() => {
    const handleClick = () => setContextMenu(null)
    window.addEventListener('click', handleClick)
    return () => window.removeEventListener('click', handleClick)
  }, [])

  const handleNext = () => {
    if (selectedImageIndex !== null && selectedImageIndex < results.length - 1) {
      setSelectedImageIndex(selectedImageIndex + 1)
    }
  }

  const handlePrev = () => {
    if (selectedImageIndex !== null && selectedImageIndex > 0) {
      setSelectedImageIndex(selectedImageIndex - 1)
    }
  }

  const handleContextMenu = (e, index) => {
    e.preventDefault()
    setContextMenu({
      x: e.clientX,
      y: e.clientY,
      index
    })
  }

  const handleCopyPath = (path) => {
    navigator.clipboard.writeText(path)
    toast.success('Path copied to clipboard!')
    setContextMenu(null)
  }

  const handleShowInFolder = async (path) => {
    try {
      const response = await fetch(`${apiUrl}/api/show-in-folder`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path })
      })
      if (!response.ok) throw new Error('Failed to open folder')
    } catch (err) {
      toast.error('Failed to open folder')
    }
    setContextMenu(null)
  }

  const visibleResults = results.slice(0, visibleCount)

  return (
    <div className="image-gallery">
      <div className="results-header">
        <h2>Results ({results.length})</h2>
      </div>
      <div className="gallery-grid">
        {visibleResults.map((result, index) => (
          <div 
            key={index} 
            className="gallery-item"
            onClick={() => setSelectedImageIndex(index)}
            onContextMenu={(e) => handleContextMenu(e, index)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === 'Enter' && setSelectedImageIndex(index)}
            aria-label={`View details for ${result.image_path}`}
          >
            <img
              src={`${apiUrl}/image?path=${encodeURIComponent(result.image_path)}`}
              alt={`Result ${index + 1}`}
              loading="lazy"
            />
            <div className="image-info">
              <MatchScore 
                semanticScore={result.semantic_score} 
                textScore={result.text_score} 
                score={result.score}
                compact={true} 
              />
              <span className="filename" data-tooltip={result.image_path}>
                {result.image_path.split(/[/\\]/).pop()}
              </span>
            </div>
          </div>
        ))}
      </div>

      {contextMenu && (
        <div 
          className="custom-context-menu"
          style={{ top: contextMenu.y, left: contextMenu.x }}
          onClick={(e) => e.stopPropagation()}
        >
          <button onClick={() => handleCopyPath(results[contextMenu.index].image_path)}>
            Copy Path
          </button>
          <button onClick={() => handleShowInFolder(results[contextMenu.index].image_path)}>
            Show in Folder
          </button>
          <button onClick={() => {
            onSearchSimilar(results[contextMenu.index].image_path)
            setContextMenu(null)
          }}>
            Find Similar
          </button>
        </div>
      )}

      {visibleCount < results.length && (
        <div ref={loaderRef} className="loader-trigger">
          <div className="spinner small"></div>
          <span>Loading more images...</span>
        </div>
      )}

      <ImageLightbox 
        isOpen={selectedImageIndex !== null} 
        onClose={() => setSelectedImageIndex(null)} 
        image={selectedImageIndex !== null ? results[selectedImageIndex] : null}
        apiUrl={apiUrl}
        onSearchSimilar={onSearchSimilar}
        onNext={handleNext}
        onPrev={handlePrev}
        hasPrevious={selectedImageIndex > 0}
        hasNext={selectedImageIndex !== null && selectedImageIndex < results.length - 1}
      />
    </div>
  )
}

export default ImageGallery
