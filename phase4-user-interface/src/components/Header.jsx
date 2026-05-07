import React from 'react'
import { Sun, Moon, Plus, X } from 'lucide-react'
import Logo from './Logo'

const Header = ({ toggleTheme, isDarkMode, chatTabs, activeTabId, setActiveTabId, onCreateTab, onCloseTab }) => {
  return (
    <header className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-ink-800/60 bg-white dark:bg-ink-950">
      <div className="flex items-center gap-4 min-w-0">
        <div className="flex items-center gap-2.5 shrink-0">
          <Logo size={32} />
          <span className="text-base font-bold tracking-tight text-slate-900 dark:text-white">
            Groww Fund Gyaan.AI
          </span>
        </div>

        <div className="flex items-center gap-2 overflow-x-auto min-w-0">
          {chatTabs.map((tab) => {
            const active = tab.id === activeTabId
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTabId(tab.id)}
                className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold border transition-colors ${
                  active
                    ? 'bg-slate-900 text-white dark:bg-teal-accent dark:text-ink-950 border-slate-900 dark:border-teal-accent'
                    : 'bg-white dark:bg-ink-900 text-slate-600 dark:text-slate-300 border-slate-200 dark:border-ink-700 hover:border-teal-accent/50'
                }`}
              >
                <span>{tab.title}</span>
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

      <div className="flex justify-end shrink-0">
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

