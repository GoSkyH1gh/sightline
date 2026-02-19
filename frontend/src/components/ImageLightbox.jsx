import React, { useEffect } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { X, Copy, Image as ImageIcon, Folder, Search, ChevronLeft, ChevronRight } from 'lucide-react'
import { toast } from 'sonner'
import './ImageLightbox.css'
import MatchScore from './MatchScore'

function ImageLightbox({ 
  isOpen, 
  onClose, 
  image, 
  apiUrl, 
  onSearchSimilar,
  onNext,
  onPrev,
  hasPrevious,
  hasNext
}) {
  useEffect(() => {
    if (!isOpen) return

    const handleKeyDown = (e) => {
      if (e.key === 'ArrowRight' && hasNext) {
        onNext()
      } else if (e.key === 'ArrowLeft' && hasPrevious) {
        onPrev()
      } else if (e.key === 'Escape') {
        onClose()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, hasNext, hasPrevious, onNext, onPrev, onClose])

  if (!image) return null

  const handleCopyImage = async () => {
    try {
      const imgUrl = `${apiUrl}/image?path=${encodeURIComponent(image.image_path)}`
      const response = await fetch(imgUrl)
      const blob = await response.blob()
      await navigator.clipboard.write([
        new ClipboardItem({
          [blob.type]: blob
        })
      ])
      toast.success('Image copied to clipboard!')
    } catch (err) {
      console.error('Failed to copy image:', err)
      toast.error('Failed to copy image to clipboard')
    }
  }

  const handleShowInFolder = async () => {
    try {
      const response = await fetch(`${apiUrl}/api/show-in-folder`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: image.image_path })
      })
      if (!response.ok) throw new Error('Failed to open folder')
    } catch (err) {
      console.error('Failed to show in folder:', err)
      toast.error('Failed to open folder')
    }
  }

  const handleFindSimilar = () => {
    onSearchSimilar(image.image_path)
    onClose()
  }

  const filename = image.image_path.split(/[/\\]/).pop()

  return (
    <Dialog.Root open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="image-lightbox-overlay" />
        <Dialog.Content className="image-lightbox-content">
          <div className="lightbox-layout">
            <div className="lightbox-image-container">
              {hasPrevious && (
                <button className="nav-btn prev" onClick={onPrev} aria-label="Previous image">
                  <ChevronLeft size={24} />
                </button>
              )}
              
              <img
                src={`${apiUrl}/image?path=${encodeURIComponent(image.image_path)}`}
                alt={filename}
                className="lightbox-image"
              />
              
              {hasNext && (
                <button className="nav-btn next" onClick={onNext} aria-label="Next image">
                  <ChevronRight size={24} />
                </button>
              )}

              <button className="close-btn" onClick={onClose} aria-label="Close">
                <X size={20} />
              </button>
            </div>

            <div className="lightbox-sidebar">
              <div className="lightbox-header">
                <div>
                  <Dialog.Title className="lightbox-title">
                    {filename}
                  </Dialog.Title>
                  <MatchScore 
                    semanticScore={image.semantic_score} 
                    textScore={image.text_score} 
                    score={image.score} 
                  />
                </div>
              </div>

              <div className="lightbox-body">
                <div className="ocr-section">
                  <span className="ocr-label">OCR Detected Text</span>
                  {image.ocr_text && image.ocr_text.trim().length > 0 ? (
                    <div className="ocr-text">
                      {image.ocr_text}
                    </div>
                  ) : (
                    <div className="ocr-empty">
                      No text detected in this image.
                    </div>
                  )}
                </div>

                {image.metadata && (
                  <div className="metadata-section">
                    <span className="ocr-label">Image Information</span>
                    <div className="metadata-grid">
                      {image.metadata.dimensions && (
                        <div className="metadata-item">
                          <span className="meta-key">Dimensions</span>
                          <span className="meta-val">{image.metadata.dimensions}</span>
                        </div>
                      )}
                      {image.metadata.date_taken && (
                        <div className="metadata-item">
                          <span className="meta-key">Date</span>
                          <span className="meta-val">{new Date(image.metadata.date_taken).toLocaleDateString()}</span>
                        </div>
                      )}
                      {image.metadata.camera_model && (
                        <div className="metadata-item">
                          <span className="meta-key">Camera</span>
                          <span className="meta-val">{image.metadata.camera_model}</span>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>

              <div className="lightbox-footer">
                <button className="action-btn primary" onClick={handleCopyImage}>
                  <Copy size={18} />
                  Copy Image
                </button>
                <button className="action-btn secondary" onClick={handleShowInFolder}>
                  <Folder size={18} />
                  Show in Folder
                </button>
                <button className="action-btn primary" onClick={handleFindSimilar}>
                  <Search size={18} />
                  Find Similar
                </button>
              </div>
            </div>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}

export default ImageLightbox
