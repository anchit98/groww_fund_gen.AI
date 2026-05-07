import React from 'react'
import { TrendingUp, ShieldCheck, PieChart, Info, ArrowRight } from 'lucide-react'

const QuickActions = () => {
  const actions = [
    {
      title: 'Top Performers',
      description: 'See the highest-yielding Quant funds based on latest NAV data.',
      icon: TrendingUp,
      color: 'bg-green-100 text-green-600 dark:bg-green-900/30 dark:text-green-400',
    },
    {
      title: 'Risk Analysis',
      description: 'Check the riskometer and volatility metrics for all schemes.',
      icon: ShieldCheck,
      color: 'bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400',
    },
    {
      title: 'Portfolio Insights',
      description: 'Examine benchmark indices and category-wise performance.',
      icon: PieChart,
      color: 'bg-purple-100 text-purple-600 dark:bg-purple-900/30 dark:text-purple-400',
    }
  ]

  return (
    <div className="space-y-8 py-8">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold tracking-tight">Quick Insights</h2>
        <button className="text-blue-600 hover:text-blue-700 text-sm font-semibold flex items-center gap-1 transition-colors">
          View All <ArrowRight className="w-4 h-4" />
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        {actions.map((action, idx) => (
          <div 
            key={idx}
            className="group p-8 rounded-[2rem] bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 hover:border-blue-500/50 dark:hover:border-blue-500/50 transition-all duration-500 shadow-sm hover:shadow-2xl cursor-pointer relative overflow-hidden"
          >
            <div className="absolute top-0 right-0 w-24 h-24 bg-gradient-to-br from-blue-500/5 to-transparent rounded-bl-full transition-transform group-hover:scale-150 duration-700"></div>
            
            <div className={`w-14 h-14 rounded-2xl ${action.color} flex items-center justify-center mb-6 transition-all duration-500 group-hover:rotate-6 group-hover:scale-110 shadow-lg shadow-current/10`}>
              <action.icon className="w-7 h-7" />
            </div>
            <h3 className="text-xl font-bold mb-3 group-hover:text-blue-600 transition-colors">{action.title}</h3>
            <p className="text-slate-600 dark:text-slate-400 text-sm leading-relaxed mb-6">
              {action.description}
            </p>
            <div className="flex items-center text-blue-600 dark:text-blue-400 text-xs font-bold uppercase tracking-widest group-hover:gap-2 transition-all">
              Explore Now <ArrowRight className="ml-1 w-4 h-4" />
            </div>
          </div>
        ))}
      </div>
      
      <div className="p-6 rounded-2xl bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900/50 flex items-start gap-4">
        <div className="p-2 bg-amber-100 dark:bg-amber-900/50 rounded-lg">
          <Info className="w-5 h-5 text-amber-600 shrink-0" />
        </div>
        <p className="text-sm text-amber-800 dark:text-amber-200 leading-relaxed">
          <strong className="block mb-1">Factual Disclaimer</strong>
          Fund Gyaan.AI provides factual data retrieved from official mutual fund documents. 
          It does not provide investment advice, buy/sell recommendations, or future performance predictions. 
          Always consult a SEBI-registered financial advisor before investing.
        </p>
      </div>
    </div>
  )
}

export default QuickActions

