import React, { useState, useEffect } from 'react'
import Header from './components/Header'
import Sidebar from './components/Sidebar'
import ChatPanel from './components/ChatPanel'

function App() {
  const [isDarkMode, setIsDarkMode] = useState(true)
  const [chatTabs, setChatTabs] = useState([
    {
      id: 'chat-1',
      title: 'Chat 1',
      messages: [
        {
          role: 'assistant',
          content:
            "Hello! I'm your Groww Fund Gyaan.AI assistant. I can help you understand mutual funds, analyze performance, and clarify tax implications. How can I assist you with your investments today?",
        },
      ],
    },
  ])
  const [activeTabId, setActiveTabId] = useState('chat-1')
  const [tabCounter, setTabCounter] = useState(1)

  useEffect(() => {
    document.documentElement.classList.toggle('dark', isDarkMode)
  }, [isDarkMode])

  const createChatTab = () => {
    const next = tabCounter + 1
    const id = `chat-${next}`
    setTabCounter(next)
    setChatTabs((tabs) => [
      ...tabs,
      {
        id,
        title: `Chat ${next}`,
        messages: [
          {
            role: 'assistant',
            content:
              "Hello! I'm your Groww Fund Gyaan.AI assistant. I can help you understand mutual funds, analyze performance, and clarify tax implications. How can I assist you with your investments today?",
          },
        ],
      },
    ])
    setActiveTabId(id)
  }

  const closeTab = (tabId) => {
    if (chatTabs.length === 1) return
    const idx = chatTabs.findIndex((t) => t.id === tabId)
    const nextTabs = chatTabs.filter((t) => t.id !== tabId)
    setChatTabs(nextTabs)
    if (activeTabId === tabId) {
      const fallback = nextTabs[Math.max(0, idx - 1)] || nextTabs[0]
      setActiveTabId(fallback.id)
    }
  }

  return (
    <div className="h-screen min-h-0 flex flex-col bg-white dark:bg-ink-950 text-slate-900 dark:text-slate-100 overflow-hidden">
      <Header
        toggleTheme={() => setIsDarkMode(!isDarkMode)}
        isDarkMode={isDarkMode}
        chatTabs={chatTabs}
        activeTabId={activeTabId}
        setActiveTabId={setActiveTabId}
        onCreateTab={createChatTab}
        onCloseTab={closeTab}
      />
      <div className="flex-1 min-h-0 flex overflow-hidden">
        <Sidebar />
        <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
          <ChatPanel
            isDarkMode={isDarkMode}
            chatTabs={chatTabs}
            setChatTabs={setChatTabs}
            activeTabId={activeTabId}
          />
        </div>
      </div>
    </div>
  )
}

export default App

