import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'

afterEach(() => vi.restoreAllMocks())

describe('TrafficVision shell', () => {
  it('renders the operations overview without real footage', async () => {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      const body = url.includes('/health')
        ? { status: 'healthy', database: 'connected', ffmpeg: true, ffprobe: true, local_only: true }
        : url.includes('/analytics')
          ? { jobs: 0, completed_jobs: 0, total_tracks: 0, real_incidents: 0, plate_reads: 0, plate_success_rate: 0, class_distribution: [], note: '' }
          : []
      return new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } })
    }))
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={client}><MemoryRouter><App/></MemoryRouter></QueryClientProvider>)
    expect(screen.getByRole('heading', { name: 'Traffic operations' })).toBeInTheDocument()
    expect(screen.getByText('Human review is mandatory')).toBeInTheDocument()
    expect(await screen.findByText('Systems operational')).toBeInTheDocument()
  })
})

