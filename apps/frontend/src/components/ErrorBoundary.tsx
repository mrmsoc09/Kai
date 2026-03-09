import React from 'react'

type Props = { children: React.ReactNode }
type State = { hasError: boolean; message: string }

export default class ErrorBoundary extends React.Component<Props, State> {
  state: State = { hasError: false, message: '' }

  static getDerivedStateFromError(error: unknown): State {
    const message = error instanceof Error ? error.message : String(error)
    return { hasError: true, message }
  }

  componentDidCatch(error: unknown, info: React.ErrorInfo) {
    console.error('[K1 ErrorBoundary]', error, info.componentStack)
  }

  render() {
    if (!this.state.hasError) return this.props.children
    return (
      <div style={{
        padding: '3rem',
        textAlign: 'center',
        fontFamily: "'JetBrains Mono', monospace",
        background: '#0B0C0D',
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
      }}>
        <div style={{ color: '#D97706', fontSize: '2rem', fontWeight: 700, marginBottom: 12 }}>
          Runtime Error
        </div>
        <div style={{
          color: '#8FAF9B',
          maxWidth: 500,
          background: '#0f1117',
          border: '1px solid #355E3B',
          borderRadius: 6,
          padding: '1rem 1.25rem',
          fontFamily: 'monospace',
          fontSize: '0.8rem',
          textAlign: 'left',
          wordBreak: 'break-word',
          marginBottom: 20,
        }}>
          {this.state.message || 'An unexpected error occurred.'}
        </div>
        <button
          onClick={() => { this.setState({ hasError: false, message: '' }); window.location.href = '/dashboard' }}
          style={{
            padding: '0.6rem 1.5rem',
            background: '#355E3B',
            color: '#000',
            border: 'none',
            borderRadius: 4,
            fontFamily: 'inherit',
            fontWeight: 700,
            cursor: 'pointer',
          }}
        >
          Return to Dashboard
        </button>
      </div>
    )
  }
}
