import React from 'react'
import { Brain, Type } from 'lucide-react'
import './MatchScore.css'

function MatchScore({ semanticScore, textScore, score, compact = false }) {
  // Normalize scores for display (0-100 range)
  const aiVal = Math.round(semanticScore * 100)
  const ocrVal = Math.round(textScore * 100)
  
  // Calculate weights based on the hybrid logic in the backend
  // Simplified for display: showing raw scores proportionally
  const total = aiVal + ocrVal
  const aiWeight = total > 0 ? (aiVal / total) * 100 : 100
  const ocrWeight = total > 0 ? (ocrVal / total) * 100 : 0

  if (compact) {
    return (
      <div 
        className="match-score-pill" 
        data-tooltip={`AI Similarity: ${aiVal}% • Text Match: ${ocrVal}%`}
      >
        <div className="pill-bg">
          <div 
            className="score-segment ai" 
            style={{ width: `${aiWeight}%` }}
          />
          <div 
            className="score-segment ocr" 
            style={{ width: `${ocrWeight}%` }}
          />
        </div>
        <span className="pill-value">{Math.round(score * 100)}%</span>
      </div>
    )
  }

  return (
    <div className="match-score-detailed">
      <div className="score-header">
        <span className="total-label">Total Match</span>
        <span className="total-value">{Math.round(score * 100)}%</span>
      </div>
      
      <div className="score-breakdown">
        <div className="score-item">
          <div className="score-info">
            <span className="label"><Brain size={14} /> AI Similarity</span>
            <span className="value">{aiVal}%</span>
          </div>
          <div className="progress-bg">
            <div className="progress-fill ai" style={{ width: `${aiVal}%` }} />
          </div>
        </div>

        <div className="score-item">
          <div className="score-info">
            <span className="label"><Type size={14} /> Text Match</span>
            <span className="value">{ocrVal}%</span>
          </div>
          <div className="progress-bg">
            <div className="progress-fill ocr" style={{ width: `${ocrVal}%` }} />
          </div>
        </div>
      </div>
    </div>
  )
}

export default MatchScore
