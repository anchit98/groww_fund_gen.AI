import React, { useEffect, useMemo, useRef, useState } from 'react'
import { Info, Link, Loader2, Send } from 'lucide-react'
import Logo from './Logo'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001').replace(/\/+$/, '')
const MAX_QUERY_LENGTH = 2000
const STATUS_REQUEST_TIMEOUT_MS = 10000
const QUERY_REQUEST_TIMEOUT_MS = 120000
const WELCOME_MESSAGE =
  "Hello! I'm your Groww Fund Gyaan.AI assistant. I can help you understand mutual funds, analyze performance, and clarify tax implications. How can I assist you with your investments today?"
const FALLBACK_SUGGESTIONS = [
  'What is the benchmark index for Quant ELSS Tax Saver Fund?',
  'What is the expense ratio of Quant Flexi Cap Fund?',
]

const fetchJsonWithTimeout = async (url, options = {}, timeoutMs = STATUS_REQUEST_TIMEOUT_MS) => {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const res = await fetch(url, { ...options, signal: controller.signal })
    const data = await res.json().catch(() => ({}))
    return { res, data }
  } finally {
    clearTimeout(timeoutId)
  }
}

const isValidGrowwFundUrl = (value) => {
  const pattern = /^https?:\/\/(?:www\.)?groww\.in\/mutual-funds\/[a-z0-9-]+\/?$/i
  return pattern.test((value || '').trim())
}

const parseBackendTimestamp = (value) => {
  if (typeof value !== 'string' || !value.trim()) return null
  const date = new Date(value.trim())
  if (Number.isNaN(date.getTime())) return null
  return date
}

const normalizeFundUrl = (value) => {
  if (typeof value !== 'string') return ''
  const trimmed = value.trim()
  if (!trimmed) return ''
  return trimmed.replace(/\/+$/, '').toLowerCase()
}

const toTitleCaseWords = (text) =>
  text
    .split(' ')
    .filter(Boolean)
    .map((word) => (word.toLowerCase() === 'elss' ? 'ELSS' : word.charAt(0).toUpperCase() + word.slice(1)))
    .join(' ')

const fullFundNameFromUrl = (url) => {
  try {
    const parsed = new URL(url)
    const segments = parsed.pathname.split('/').filter(Boolean)
    const mfIndex = segments.findIndex((s) => s === 'mutual-funds')
    const slug = mfIndex >= 0 && segments[mfIndex + 1] ? segments[mfIndex + 1] : segments[segments.length - 1]
    if (!slug) return ''
    const cleaned = decodeURIComponent(slug)
      .replace(/\.(html|htm)$/i, '')
      .replace(/[-_]+/g, ' ')
      .replace(/\s+/g, ' ')
      .trim()
    return cleaned ? toTitleCaseWords(cleaned) : ''
  } catch {
    return ''
  }
}

const deriveDisplayFundName = (name, url) => {
  const fromUrl = fullFundNameFromUrl(url)
  if (fromUrl) return fromUrl
  if (typeof name === 'string' && name.trim()) return name.trim()
  return 'Unknown Scheme'
}

const ChatPanel = ({ isDarkMode, chatTabs, setChatTabs, activeTabId }) => {
  const [input, setInput] = useState('')
  const [fundUrlInput, setFundUrlInput] = useState('')
  const [showIngestBox, setShowIngestBox] = useState(false)
  const [loading, setLoading] = useState(false)
  const [ingestingUrl, setIngestingUrl] = useState(false)
  const [warning, setWarning] = useState('')
  const [errorBanner, setErrorBanner] = useState('')
  const [suggestions, setSuggestions] = useState(FALLBACK_SUGGESTIONS)
  const [ingestedFunds, setIngestedFunds] = useState([])
  const [lastSuccessfulScrapeAt, setLastSuccessfulScrapeAt] = useState(null)
  const [localIngestionStartedAt, setLocalIngestionStartedAt] = useState(null)
  const [localElapsedSeconds, setLocalElapsedSeconds] = useState(0)
  const [ingestionStatus, setIngestionStatus] = useState({
    status: 'idle',
    running: false,
    elapsed_seconds: null,
    exit_code: null,
    target_url: null,
  })
  const scrollRef = useRef(null)

  const activeTab = chatTabs.find((tab) => tab.id === activeTabId) || chatTabs[0]
  const messages = activeTab?.messages || []
  const showExamples = useMemo(() => messages.length <= 1 && !loading, [messages.length, loading])
  const uniqueIngestedFunds = useMemo(() => {
    const deduped = new Map()
    for (const fund of ingestedFunds) {
      const normalizedUrl = normalizeFundUrl(fund?.url)
      if (!normalizedUrl || !isValidGrowwFundUrl(normalizedUrl)) continue
      if (!deduped.has(normalizedUrl)) {
        deduped.set(normalizedUrl, {
          name: deriveDisplayFundName(fund?.name, normalizedUrl),
          url: normalizedUrl,
        })
      }
    }
    return Array.from(deduped.values())
  }, [ingestedFunds])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, loading])

  useEffect(() => {
    setInput('')
    setWarning('')
    setErrorBanner('')
  }, [activeTabId])

  useEffect(() => {
    let active = true
    const loadIngestedFunds = async () => {
      try {
        const { res, data } = await fetchJsonWithTimeout(`${API_BASE_URL}/ingested-funds`)
        if (!active || !res.ok) return
        const funds = Array.isArray(data.funds) ? data.funds : []
        setIngestedFunds(
          funds
            .map((fund) => ({
              url: typeof fund?.url === 'string' ? fund.url.trim() : '',
              name: deriveDisplayFundName(fund?.name, typeof fund?.url === 'string' ? fund.url.trim() : ''),
            }))
            .filter((fund) => fund.url)
        )
      } catch {
        // no-op
      }
    }
    loadIngestedFunds()
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    let active = true
    let timer = null
    const pollIngestion = async () => {
      let nextDelay = 30000
      try {
        const { res, data } = await fetchJsonWithTimeout(`${API_BASE_URL}/ingest-status`)
        if (res.ok && active) {
          const running = Boolean(data.running)
          if (!running) {
            setLocalIngestionStartedAt(null)
            setLocalElapsedSeconds(0)
          }
          setIngestionStatus({
            status: data.status || 'idle',
            running,
            elapsed_seconds: typeof data.elapsed_seconds === 'number' ? Math.max(0, Math.floor(data.elapsed_seconds)) : null,
            exit_code: typeof data.exit_code === 'number' ? data.exit_code : null,
            target_url: typeof data.target_url === 'string' && data.target_url.trim() ? data.target_url.trim() : null,
          })
          nextDelay = running ? 2500 : 30000
        }
      } catch {
        nextDelay = 45000
      } finally {
        if (active) timer = setTimeout(pollIngestion, nextDelay)
      }
    }
    pollIngestion()
    return () => {
      active = false
      if (timer) clearTimeout(timer)
    }
  }, [])

  useEffect(() => {
    if (!ingestionStatus.running || !localIngestionStartedAt) return
    const tick = () => {
      const seconds = Math.max(0, Math.floor((Date.now() - localIngestionStartedAt) / 1000))
      setLocalElapsedSeconds(seconds)
    }
    tick()
    const timer = setInterval(tick, 1000)
    return () => clearInterval(timer)
  }, [ingestionStatus.running, localIngestionStartedAt])

  useEffect(() => {
    let active = true
    let timer = null
    const pollScrapeStatus = async () => {
      let nextDelay = 60000
      try {
        const { res, data } = await fetchJsonWithTimeout(`${API_BASE_URL}/scrape-status`)
        if (res.ok && active) {
          const value =
            typeof data.last_successful_scrape_at === 'string'
              ? data.last_successful_scrape_at
              : typeof data.last_updated === 'string'
                ? data.last_updated
                : typeof data.timestamp === 'string'
                  ? data.timestamp
                  : null
          setLastSuccessfulScrapeAt(value)
        }
      } catch {
        nextDelay = 90000
      } finally {
        if (active) timer = setTimeout(pollScrapeStatus, nextDelay)
      }
    }
    pollScrapeStatus()
    return () => {
      active = false
      if (timer) clearTimeout(timer)
    }
  }, [])

  const appendMessage = (msg) => {
    setChatTabs((tabs) =>
      tabs.map((tab) => (tab.id === activeTabId ? { ...tab, messages: [...tab.messages, msg] } : tab))
    )
  }

  const sendMessage = async (value) => {
    const query = (value ?? input).trim()
    if (!query || loading) return
    if (query.length > MAX_QUERY_LENGTH) {
      const msg = `Your question is too long (${query.length} chars). Please keep it within ${MAX_QUERY_LENGTH} characters.`
      setWarning(msg)
      setErrorBanner(msg)
      return
    }

    setWarning('')
    setErrorBanner('')
    appendMessage({ role: 'user', content: query })
    setInput('')
    setLoading(true)
    try {
      const { res, data } = await fetchJsonWithTimeout(
        `${API_BASE_URL}/query`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query }),
        },
        QUERY_REQUEST_TIMEOUT_MS
      )
      if (!res.ok) throw new Error(data.detail || 'Backend request failed')
      appendMessage({
        role: 'assistant',
        content: data.response || 'information unavailable.',
        citations: Array.isArray(data.citations) ? data.citations : [],
      })
    } catch (e) {
      const isAbort = e instanceof DOMException && e.name === 'AbortError'
      const msg = isAbort
        ? 'The backend is taking longer than expected (possible cold start). Please retry in a few seconds.'
        : "I'm unable to reach the backend right now. Please check that your API server is running and VITE_API_BASE_URL is configured."
      appendMessage({ role: 'assistant', content: msg })
      setErrorBanner(isAbort ? 'Backend request timed out. Please retry.' : 'Source unavailable. Backend connection failed.')
    } finally {
      setLoading(false)
    }
  }

  const handleAddFundUrl = async () => {
    const url = fundUrlInput.trim()
    if (!url || ingestingUrl || ingestionStatus.running) return
    if (!isValidGrowwFundUrl(url)) {
      const msg = 'Please enter a valid Groww mutual fund URL: https://groww.in/mutual-funds/<scheme-slug>'
      appendMessage({ role: 'assistant', content: msg })
      setErrorBanner(msg)
      return
    }

    setIngestingUrl(true)
    setErrorBanner('')
    try {
      const { res, data } = await fetchJsonWithTimeout(`${API_BASE_URL}/ingest-url`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      })
      if (!res.ok) throw new Error(data.detail || 'Failed to start ingestion')
      appendMessage({ role: 'assistant', content: data.message || 'Ingestion started.' })
      setFundUrlInput('')
      const startTs = Date.now()
      setLocalIngestionStartedAt(startTs)
      setLocalElapsedSeconds(0)
      setIngestionStatus((prev) => ({
        ...prev,
        status: 'running',
        running: true,
        elapsed_seconds: 0,
        exit_code: null,
        target_url: data.normalized_url || url,
      }))
      if (data.normalized_url) {
        setIngestedFunds((prev) => {
          if (prev.some((fund) => normalizeFundUrl(fund.url) === normalizeFundUrl(data.normalized_url))) {
            return prev
          }
          return [
            ...prev,
            {
              name: deriveDisplayFundName(data.scheme_name, data.normalized_url),
              url: data.normalized_url,
            },
          ]
        })
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Could not start ingestion.'
      appendMessage({ role: 'assistant', content: msg })
      setErrorBanner(msg)
    } finally {
      setIngestingUrl(false)
    }
  }

  const formattedLastScrape = (() => {
    if (!lastSuccessfulScrapeAt) return null
    const dt = parseBackendTimestamp(lastSuccessfulScrapeAt)
    if (!dt) return null
    return dt.toLocaleString('en-IN', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: true,
    })
  })()

  const statusStyles = {
    idle: 'bg-slate-100 text-slate-600 dark:bg-ink-700 dark:text-slate-300',
    running: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
    completed: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300',
    failed: 'bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300',
  }
  const statusLabel = (() => {
    if (ingestionStatus.status === 'running') return 'Ingestion in progress'
    if (ingestionStatus.status === 'completed') return 'Last ingestion completed'
    if (ingestionStatus.status === 'failed') return 'Last ingestion failed'
    return 'No ingestion running'
  })()
  const displayedElapsedSeconds =
    ingestionStatus.status === 'running'
      ? (typeof ingestionStatus.elapsed_seconds === 'number' ? ingestionStatus.elapsed_seconds : localElapsedSeconds)
      : null
  const formatElapsed = (seconds) => {
    if (typeof seconds !== 'number' || Number.isNaN(seconds) || seconds < 0) return null
    const totalSeconds = Math.floor(seconds)
    const mins = Math.floor(totalSeconds / 60)
    const secs = totalSeconds % 60
    return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
  }
  const runningTimerLabel = formatElapsed(displayedElapsedSeconds)

  return (
    <main className="flex-1 min-h-0 flex flex-col bg-slate-50 dark:bg-ink-950 min-w-0">
      <div className="sticky top-0 z-10 border-b border-amber-200 dark:border-amber-900/30 bg-amber-50/95 dark:bg-amber-950/40 backdrop-blur px-6 py-2">
        <p className="text-[11.5px] text-amber-800 dark:text-amber-200 text-center">
          Disclaimer: Facts-only assistant for Groww mutual fund pages. No investment advice.
        </p>
      </div>

      {errorBanner && (
        <div className="border-b border-rose-200 dark:border-rose-900/30 bg-rose-50 dark:bg-rose-950/30 px-6 py-2">
          <p className="text-[11.5px] text-rose-700 dark:text-rose-300 text-center">{errorBanner}</p>
        </div>
      )}

      <div ref={scrollRef} className={`flex-1 min-h-0 overflow-y-auto ${isDarkMode ? 'stripe-pattern' : 'stripe-pattern-light'}`}>
        <div className="max-w-3xl mx-auto px-6 py-8 space-y-6">
          {messages.map((msg, idx) => (
            <Message key={idx} msg={msg} />
          ))}

          {loading && (
            <div className="flex items-start gap-3">
              <Logo size={36} />
              <div className="px-4 py-3 rounded-2xl bg-white dark:bg-ink-800/80 border border-slate-200 dark:border-ink-700/60 flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin text-teal-accent" />
                <span className="text-sm text-slate-500 dark:text-slate-400">Thinking...</span>
              </div>
            </div>
          )}

          {showExamples && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-4">
              {suggestions.map((q) => (
                <button
                  key={q}
                  onClick={() => sendMessage(q)}
                  className="text-left px-5 py-4 rounded-xl bg-white dark:bg-ink-800/70 border border-slate-200 dark:border-ink-700/60 text-[13.5px] text-slate-700 dark:text-slate-200 hover:border-teal-accent/50 hover:bg-slate-50 dark:hover:bg-ink-700/60 transition-all"
                >
                  {q}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="px-6 pt-3 pb-5 bg-slate-50 dark:bg-ink-950">
        <div className="max-w-3xl mx-auto">
          {showIngestBox && (
            <div className="mb-3 p-3 rounded-xl bg-white dark:bg-ink-800/80 border border-slate-200 dark:border-ink-700/60">
              <div className="mb-2 flex items-center justify-between gap-2">
                <p className="text-[12px] font-semibold text-slate-700 dark:text-slate-200">Add Groww mutual fund URL</p>
                <div className="relative flex items-center gap-2 group">
                  <span className={`text-[11px] font-semibold px-2 py-1 rounded-full ${statusStyles[ingestionStatus.status] || statusStyles.idle}`}>
                    {statusLabel}
                    {runningTimerLabel ? ` (${runningTimerLabel})` : ''}
                  </span>
                  <button
                    type="button"
                    className="inline-flex items-center gap-1 px-2 py-1 rounded-full border border-slate-200 dark:border-ink-700/60 text-[11px] font-semibold text-slate-600 dark:text-slate-300 hover:border-teal-accent/50 hover:text-slate-800 dark:hover:text-slate-100 transition-colors"
                    aria-label="Show ingested funds"
                    title="Show ingested funds"
                  >
                    <Info className="w-3.5 h-3.5" />
                    {uniqueIngestedFunds.length}
                  </button>
                  <div className="pointer-events-none absolute right-0 bottom-[calc(100%+8px)] z-20 w-72 p-3 rounded-xl bg-white dark:bg-ink-900 border border-slate-200 dark:border-ink-700/60 shadow-lg opacity-0 translate-y-1 transition-all duration-150 group-hover:opacity-100 group-hover:translate-y-0 group-hover:pointer-events-auto">
                    <p className="text-[12px] font-semibold text-slate-800 dark:text-slate-100 mb-2">
                      Ingested Funds ({uniqueIngestedFunds.length})
                    </p>
                    {uniqueIngestedFunds.length === 0 ? (
                      <p className="text-[11px] text-slate-500 dark:text-slate-400">No funds listed yet.</p>
                    ) : (
                      <div className="max-h-[112px] overflow-y-auto pr-1 space-y-1.5">
                        {uniqueIngestedFunds.map((fund) => (
                          <p key={fund.url} className="text-[11px] text-slate-600 dark:text-slate-300 truncate" title={fund.url}>
                            {fund.name}
                          </p>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="url"
                  value={fundUrlInput}
                  onChange={(e) => setFundUrlInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleAddFundUrl()}
                  placeholder="https://groww.in/mutual-funds/<scheme-slug>"
                  className="flex-1 bg-transparent outline-none text-sm text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 px-2 py-2 rounded-lg border border-slate-200 dark:border-ink-700/60"
                  disabled={ingestionStatus.running}
                />
                <button
                  type="button"
                  onClick={handleAddFundUrl}
                  disabled={!fundUrlInput.trim() || ingestingUrl || ingestionStatus.running}
                  className="px-3 py-2 rounded-lg text-xs font-semibold bg-teal-accent hover:bg-teal-400 disabled:opacity-50 text-ink-950 transition-colors"
                >
                  {ingestingUrl ? 'Adding...' : 'Add URL'}
                </button>
              </div>
            </div>
          )}

          <div className="flex items-center gap-2 bg-white dark:bg-ink-800/80 border border-slate-200 dark:border-ink-700/60 rounded-full pl-2 pr-2 py-2 shadow-sm focus-within:border-teal-accent/60 transition-colors">
            <button
              type="button"
              onClick={() => setShowIngestBox((v) => !v)}
              className="shrink-0 inline-flex items-center justify-center w-8 h-8 rounded-full bg-amber-400 text-amber-950 hover:bg-amber-300 transition-colors shadow-sm"
              aria-label={showIngestBox ? 'Hide ingest URL box' : 'Show ingest URL box'}
              title={showIngestBox ? 'Hide ingest URL box' : 'Show ingest URL box'}
            >
              <Link className="w-3.5 h-3.5" />
            </button>
            <input
              type="text"
              value={input}
              onChange={(e) => {
                const next = e.target.value
                setInput(next)
                setWarning(
                  next.length > MAX_QUERY_LENGTH
                    ? `Maximum ${MAX_QUERY_LENGTH} characters allowed (current: ${next.length}).`
                    : ''
                )
              }}
              onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
              placeholder="Ask factual questions about ingested mutual funds..."
              className="flex-1 bg-transparent outline-none text-sm text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 px-1"
            />
            <button
              onClick={() => sendMessage()}
              disabled={!input.trim() || loading}
              aria-label="Send"
              className="w-10 h-10 rounded-full flex items-center justify-center bg-teal-accent hover:bg-teal-400 disabled:opacity-50 disabled:hover:bg-teal-accent text-ink-950 transition-all active:scale-95"
            >
              <Send className="w-4 h-4" strokeWidth={2.5} />
            </button>
          </div>
          {warning && <p className="mt-2 text-[11px] text-rose-600 dark:text-rose-400 text-center">{warning}</p>}
          <p className="text-center text-[11.5px] text-slate-500 dark:text-slate-500 mt-3">
            Groww Fund Gyaan.AI can make mistakes. Verify important information.
          </p>
          <p className="text-center text-[11px] text-slate-500 dark:text-slate-500 mt-1">
            Last Updated: {formattedLastScrape || 'Not available yet'}
          </p>
        </div>
      </div>
    </main>
  )
}

const Message = ({ msg }) => {
  const citations = Array.isArray(msg.citations) ? msg.citations : []
  const content = typeof msg.content === 'string' ? msg.content : ''
  const citationLineMatch = content.match(/Citation:\s*(https?:\/\/\S+)/i)
  const citationFromContent = citationLineMatch ? citationLineMatch[1] : null

  const toTitleCase = (value) =>
    value
      .split(' ')
      .filter(Boolean)
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ')

  const inferFundNameFromUrl = (url) => {
    try {
      const parsed = new URL(url)
      const segments = parsed.pathname.split('/').filter(Boolean)
      if (segments.length === 0) return null
      let slug = segments[segments.length - 1]
      const mfIndex = segments.findIndex((s) => s === 'mutual-funds')
      if (mfIndex >= 0 && segments[mfIndex + 1]) slug = segments[mfIndex + 1]
      const cleaned = decodeURIComponent(slug)
        .replace(/\.(html|htm)$/i, '')
        .replace(/[-_]+/g, ' ')
        .replace(/\s+/g, ' ')
        .trim()
      return cleaned ? toTitleCase(cleaned) : null
    } catch {
      return null
    }
  }

  const linkItems = citations
    .map((c) => {
      const url = typeof c === 'string' ? c : c?.url
      if (typeof url !== 'string' || url.length === 0) return null
      const explicitLabel = typeof c === 'object' ? c.label || c.title || c.scheme_name || c.fund_name : null
      const label = explicitLabel || inferFundNameFromUrl(url) || 'Source'
      return { url, label }
    })
    .filter(Boolean)

  if (citationFromContent && !linkItems.some((item) => item.url === citationFromContent)) {
    linkItems.push({
      url: citationFromContent,
      label: inferFundNameFromUrl(citationFromContent) || 'Source',
    })
  }

  if (msg.role === 'assistant') {
    return (
      <div className="flex items-start gap-3">
        <div className="shrink-0 mt-0.5">
          <Logo size={36} />
        </div>
        <div className="flex-1 max-w-[85%]">
          <div className="px-4 py-3 rounded-2xl bg-white dark:bg-ink-800/80 border border-slate-200 dark:border-ink-700/60 text-[13.5px] leading-relaxed text-slate-700 dark:text-slate-200">
            <p className="whitespace-pre-wrap">{msg.content}</p>
            {linkItems.length > 0 && (
              <p className="mt-3 text-[12px] text-slate-500 dark:text-slate-400">
                Sources:{' '}
                {linkItems.map((item, i) => (
                  <React.Fragment key={`${item.url}-${i}`}>
                    {item.url.startsWith('http') ? (
                      <a href={item.url} target="_blank" rel="noreferrer" className="text-teal-accent hover:underline">
                        {item.label}
                      </a>
                    ) : (
                      <span className="text-teal-accent">{item.url}</span>
                    )}
                    {i < linkItems.length - 1 ? ', ' : ''}
                  </React.Fragment>
                ))}
              </p>
            )}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex justify-end">
      <div className="max-w-[80%] px-4 py-3 rounded-2xl bg-teal-accent text-ink-950 text-[13.5px] leading-relaxed font-medium">
        {msg.content}
      </div>
    </div>
  )
}

export default ChatPanel
