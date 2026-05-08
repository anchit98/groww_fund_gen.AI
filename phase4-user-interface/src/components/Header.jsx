import React from 'react'
import { Sun, Moon, Plus, X } from 'lucide-react'
import Logo from './Logo'

const Header = ({ toggleTheme, isDarkMode, chatTabs, activeTabId, setActiveTabId, onCreateTab, onCloseTab, onRenameTab }) => {
  const [editingTabId, setEditingTabId] = React.useState(null)
  const [draftTitle, setDraftTitle] = React.useState('')

  const startRename = (tab) => {
    setEditingTabId(tab.id)
    setDraftTitle(tab.title || '')
  }

  const commitRename = () => {
    if (!editingTabId) return
    onRenameTab(editingTabId, draftTitle)
    setEditingTabId(null)
    setDraftTitle('')
  }

  const cancelRename = () => {
    setEditingTabId(null)
    setDraftTitle('')
  }

  return (
    <header className="flex items-start sm:items-center justify-between gap-3 px-3 sm:px-6 py-3 sm:py-4 border-b border-slate-200 dark:border-ink-800/60 bg-white dark:bg-ink-950">
      <div className="flex items-start sm:items-center gap-2 sm:gap-4 min-w-0 flex-1">
        <div className="flex items-center gap-2.5 shrink-0">
          <Logo size={28} />
          <span className="text-sm sm:text-base font-bold tracking-tight text-slate-900 dark:text-white whitespace-nowrap">
            Groww Fund Gyaan.AI
          </span>
        </div>

        <div className="hidden sm:flex items-center gap-1.5 sm:gap-2 overflow-x-auto min-w-0 pb-0.5">
          {chatTabs.map((tab) => {
            const active = tab.id === activeTabId
            const isEditing = editingTabId === tab.id
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTabId(tab.id)}
                onDoubleClick={() => startRename(tab)}
                className={`inline-flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 rounded-full text-[11px] sm:text-xs font-semibold border transition-colors whitespace-nowrap ${
                  active
                    ? 'bg-slate-900 text-white dark:bg-teal-accent dark:text-ink-950 border-slate-900 dark:border-teal-accent'
                    : 'bg-white dark:bg-ink-900 text-slate-600 dark:text-slate-300 border-slate-200 dark:border-ink-700 hover:border-teal-accent/50'
                }`}
              >
                {isEditing ? (
                  <input
                    autoFocus
                    value={draftTitle}
                    onChange={(e) => setDraftTitle(e.target.value)}
                    onClick={(e) => e.stopPropagation()}
                    onBlur={commitRename}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault()
                        commitRename()
                      } else if (e.key === 'Escape') {
                        e.preventDefault()
                        cancelRename()
                      }
                    }}
                    className="w-24 sm:w-28 bg-transparent outline-none border-none text-[11px] sm:text-xs font-semibold"
                    aria-label={`Rename ${tab.title}`}
                  />
                ) : (
                  <span title="Double-click to rename">{tab.title}</span>
                )}
                {chatTabs.length > 1 && (
                  <span
                    role="button"
                    tabIndex={0}
                    onClick={(e) => {
                      e.stopPropagation()
                      onCloseTab(tab.id)
                    }}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        onCloseTab(tab.id)
                      }
                    }}
                    className="opacity-80 hover:opacity-100"
                    aria-label={`Close ${tab.title}`}
                  >
                    <X className="w-3 h-3" />
                  </span>
                )}
              </button>
            )
          })}
          <button
            type="button"
            onClick={onCreateTab}
            className="inline-flex items-center justify-center w-7 h-7 rounded-full text-ink-950 bg-teal-accent hover:bg-teal-400 transition-colors shrink-0"
            aria-label="Add new chat tab"
            title="Add new chat tab"
          >
            <Plus className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="flex justify-end shrink-0 self-start sm:self-auto">
        <button
          onClick={toggleTheme}
          aria-label="Toggle theme"
          className="p-2 rounded-full text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-ink-800/60 transition-colors"
        >
          {isDarkMode ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
        </button>
      </div>
    </header>
  )
}

export default Header

