import React, { useState } from 'react'
import {
  GraduationCap,
  Lightbulb,
  Calculator,
  PieChart,
  ShieldAlert,
  Layers,
  Folder,
} from 'lucide-react'

const wisdomItems = [
  {
    icon: Lightbulb,
    iconColor: 'text-amber-500',
    title: 'Power of Compounding',
    desc:
      'Starting early allows your returns to generate their own returns. Even small amounts grow significantly over 10+ years.',
  },
  {
    icon: Calculator,
    iconColor: 'text-cyan-500',
    title: 'Tax Saving with ELSS',
    desc:
      'ELSS mutual funds offer tax deductions up to ₹1.5L under Section 80C, with the shortest lock-in period of 3 years.',
  },
  {
    icon: PieChart,
    iconColor: 'text-purple-500',
    title: 'Diversification',
    desc:
      "Don't put all your eggs in one basket. Spreading investments across different asset classes reduces overall risk.",
  },
  {
    icon: ShieldAlert,
    iconColor: 'text-red-500',
    title: 'Risk Management',
    desc:
      'Understand your risk tolerance before investing. Use tools like Stop-Loss and diversification to protect your capital.',
  },
  {
    icon: Layers,
    iconColor: 'text-emerald-500',
    title: 'Asset Allocation',
    desc:
      'Distribute your investments across equity, debt, and gold based on your age and financial objectives.',
  },
  {
    icon: Folder,
    iconColor: 'text-orange-500',
    title: 'Long-term Goals',
    desc:
      'Define clear financial goals like retirement, home purchase, or education to guide your investment strategy.',
  },
  {
    icon: ShieldAlert,
    iconColor: 'text-rose-500',
    title: 'Volatility Discipline',
    desc:
      'Market swings are normal in equity funds. Avoid panic redemptions during short-term corrections to protect long-term returns.',
  },
  {
    icon: PieChart,
    iconColor: 'text-indigo-500',
    title: 'Category Concentration Risk',
    desc:
      'Over-allocating to one fund category (like only small-cap) can increase downside risk. Balance exposure across categories.',
  },
  {
    icon: Calculator,
    iconColor: 'text-sky-500',
    title: 'Expense Ratio Impact',
    desc:
      'Even small differences in expense ratio can materially affect final corpus over years. Prefer cost-efficient funds when comparable.',
  },
  {
    icon: Layers,
    iconColor: 'text-lime-500',
    title: 'Rebalancing Matters',
    desc:
      'Review and rebalance your portfolio periodically so gains in one segment do not unintentionally increase portfolio risk.',
  },
  {
    icon: Lightbulb,
    iconColor: 'text-yellow-500',
    title: 'Match Horizon to Risk',
    desc:
      'Use higher-risk equity funds for longer goals and lower-volatility options for near-term goals to reduce timing risk.',
  },
  {
    icon: GraduationCap,
    iconColor: 'text-cyan-500',
    title: 'Understand Exit Load',
    desc:
      'Some funds charge exit load if redeemed early. Check lock-in and exit conditions before investing to avoid unexpected costs.',
  },
]

const Sidebar = () => {
  return (
    <aside className="w-[280px] shrink-0 border-r border-slate-200 dark:border-ink-800/60 bg-white dark:bg-ink-950 flex flex-col">
      <div className="h-[54px] px-5 flex items-center justify-center border-b border-slate-200 dark:border-ink-800/60 bg-white dark:bg-ink-950">
        <span className="text-[12.5px] font-extrabold tracking-[0.18em] text-slate-800 dark:text-slate-200 uppercase text-center">
          Investment Wisdom
        </span>
      </div>

      <div className="flex-1 overflow-hidden px-4 pt-4 pb-6">
        <div className="wisdom-track wisdom-track-running">
          {[...wisdomItems, ...wisdomItems].map((item, idx) => {
            const Icon = item.icon
            return (
              <div
                key={`${item.title}-${idx}`}
                className="rounded-xl bg-slate-50 dark:bg-ink-900/60 border border-slate-100 dark:border-ink-800/40 p-4 hover:border-slate-200 dark:hover:border-ink-700 transition-colors mb-3"
              >
                <div className="flex items-center gap-2 mb-2">
                  <Icon className={`w-4 h-4 ${item.iconColor}`} strokeWidth={2.2} />
                  <h3 className="text-[13px] font-bold text-slate-900 dark:text-white">
                    {item.title}
                  </h3>
                </div>
                <p className="text-[11.5px] leading-relaxed text-slate-500 dark:text-slate-400">
                  {item.desc}
                </p>
              </div>
            )
          })}
        </div>
      </div>
    </aside>
  )
}

export default Sidebar
