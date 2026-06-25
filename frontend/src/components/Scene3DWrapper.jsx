import { Component } from 'react'

export default class Scene3DWrapper extends Component {
  state = { hasError: false }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  componentDidCatch(error) {
    console.warn('Scene3D render error (gracefully degraded):', error.message)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="fixed inset-0 -z-10" style={{ backgroundColor: '#0A0F1C' }}>
          <div className="absolute inset-0 perspective-grid opacity-[0.04]" />
        </div>
      )
    }
    return this.props.children
  }
}
