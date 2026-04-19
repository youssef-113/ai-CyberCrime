import { useState } from 'react'
import clsx from 'clsx'

export default function Tabs({ tabs, defaultTab, className }) {
  const [activeTab, setActiveTab] = useState(defaultTab || tabs[0]?.id)

  const activeContent = tabs.find((t) => t.id === activeTab)?.content

  return (
    <div className={clsx('w-full', className)}>
      <div className="flex border-b border-neutral-800" role="tablist">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            role="tab"
            aria-selected={activeTab === tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={clsx(
              'px-4 py-2.5 text-sm font-medium transition-all duration-200 border-b-2 -mb-px',
              activeTab === tab.id
                ? 'text-primary border-primary'
                : 'text-neutral-400 border-transparent hover:text-neutral-200 hover:border-neutral-600'
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div className="pt-4" role="tabpanel">
        {activeContent}
      </div>
    </div>
  )
}
