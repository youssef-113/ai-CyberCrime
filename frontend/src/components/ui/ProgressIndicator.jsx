import clsx from 'clsx'

export function ProgressBar({ value = 0, max = 100, label, showValue = true, className }) {
  const percentage = Math.min(Math.max((value / max) * 100, 0), 100)

  return (
    <div className={clsx('w-full', className)}>
      {(label || showValue) && (
        <div className="flex items-center justify-between mb-1.5">
          {label && <span className="text-sm text-neutral-300">{label}</span>}
          {showValue && <span className="text-sm font-mono text-neutral-400">{Math.round(percentage)}%</span>}
        </div>
      )}
      <div className="w-full h-2 bg-neutral-800 rounded-full overflow-hidden" role="progressbar" aria-valuenow={value} aria-valuemin={0} aria-valuemax={max}>
        <div
          className="h-full bg-primary rounded-full transition-all duration-500 ease-out"
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  )
}

export function PipelineProgress({ steps, currentStep, className }) {
  return (
    <div className={clsx('w-full', className)}>
      <div className="flex items-center justify-between">
        {steps.map((step, index) => {
          const isActive = index === currentStep
          const isCompleted = index < currentStep
          return (
            <div key={step} className="flex items-center flex-1 last:flex-none">
              <div className="flex flex-col items-center">
                <div
                  className={clsx(
                    'w-8 h-8 rounded-full flex items-center justify-center text-xs font-semibold transition-all duration-300',
                    isCompleted && 'bg-primary text-white',
                    isActive && 'bg-primary/20 text-primary border-2 border-primary',
                    !isActive && !isCompleted && 'bg-neutral-800 text-neutral-500 border border-neutral-700'
                  )}
                >
                  {isCompleted ? '✓' : index + 1}
                </div>
                <span className={clsx(
                  'text-xs mt-1.5 whitespace-nowrap',
                  isActive ? 'text-primary font-medium' : 'text-neutral-500'
                )}>
                  {step}
                </span>
              </div>
              {index < steps.length - 1 && (
                <div className={clsx(
                  'flex-1 h-0.5 mx-2 transition-colors duration-300',
                  isCompleted ? 'bg-primary' : 'bg-neutral-800'
                )} />
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

export function Spinner({ size = 'md', className }) {
  const sizes = { sm: 'w-4 h-4', md: 'w-8 h-8', lg: 'w-12 h-12' }
  return (
    <svg className={clsx('animate-spin text-primary', sizes[size], className)} viewBox="0 0 24 24" fill="none">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  )
}
