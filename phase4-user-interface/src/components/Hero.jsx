import React from 'react'
import { Search, ArrowRight } from 'lucide-react'

const Hero = ({ onSearch }) => {
  return (
    <div className="relative py-16 md:py-24 overflow-hidden rounded-[2.5rem] bg-slate-900 shadow-2xl">
      {/* Background patterns */}
      <div className="absolute inset-0 bg-gradient-to-br from-blue-600/20 via-transparent to-indigo-600/20"></div>
      <div className="absolute top-0 right-0 -translate-y-1/2 translate-x-1/4 w-[30rem] h-[30rem] bg-blue-500/10 rounded-full blur-[100px]"></div>
      <div className="absolute bottom-0 left-0 translate-y-1/2 -translate-x-1/4 w-[20rem] h-[20rem] bg-indigo-500/10 rounded-full blur-[80px]"></div>
      
      <div className="relative z-10 flex flex-col items-center text-center max-w-4xl mx-auto px-6">
        <h1 className="text-4xl md:text-6xl font-black text-white mb-6 tracking-tight">
          Welcome back, <br/>
          <span className="bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-indigo-400">
            Quant Enthusiast!
          </span>
        </h1>
        <p className="text-lg md:text-xl text-slate-300 mb-10 max-w-2xl leading-relaxed">
          Your AI-powered companion for data-backed mutual fund insights. 
          Get instant, source-verified answers about Quant schemes.
        </p>
        
        <div className="w-full max-w-2xl relative group">
          <div className="absolute -inset-1 bg-gradient-to-r from-blue-500 to-indigo-500 rounded-[1.5rem] blur opacity-25 group-focus-within:opacity-50 transition duration-500"></div>
          <div className="relative flex items-center bg-white dark:bg-slate-900 rounded-[1.25rem] shadow-2xl overflow-hidden border border-slate-200 dark:border-slate-800 transition-all duration-300">
            <div className="flex items-center justify-center pl-6 text-slate-400">
              <Search className="w-6 h-6" />
            </div>
            <input 
              type="text" 
              placeholder="Ask anything about Quant mutual funds..."
              className="w-full py-6 px-4 bg-transparent outline-none text-slate-900 dark:text-white placeholder-slate-400 text-lg"
              onKeyDown={(e) => e.key === 'Enter' && onSearch()}
            />
            <div className="pr-3">
              <button 
                onClick={onSearch}
                className="flex items-center gap-2 px-6 py-3 bg-blue-600 hover:bg-blue-700 transition-all rounded-xl text-white font-bold shadow-lg active:scale-95"
              >
                Ask Assistant
                <ArrowRight className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
        
        <div className="mt-10 flex flex-wrap justify-center gap-3">
          <span className="text-slate-500 text-sm font-medium mr-2 self-center">Try asking:</span>
          {['Latest NAV of Small Cap', 'What is Exit Load?', 'ELSS Lock-in Period'].map((tag) => (
            <button 
              key={tag}
              onClick={onSearch}
              className="px-4 py-2 text-sm bg-slate-800/50 hover:bg-slate-800 border border-slate-700 rounded-xl text-slate-300 transition-all"
            >
              {tag}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

export default Hero
