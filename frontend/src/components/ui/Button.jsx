import { forwardRef } from 'react'
import clsx from 'clsx'

const baseStyles = 'inline-flex items-center justify-center gap-2'

const variants = {
  primary: 'btn-primary',
  secondary: 'btn-secondary',
  outline: 'btn-outline',
  danger: 'btn-danger',
  ghost: 'btn-ghost',
}

const sizes = {
  sm: 'btn-sm',
  md: '',
  lg: 'btn-lg',
  icon: 'btn-icon',
}

const Button = forwardRef(function Button(
  { variant = 'primary', size = 'md', className, children, loading, disabled, ...props },
  ref
) {
  return (
    <button
      ref={ref}
      className={clsx(baseStyles, variants[variant], sizes[size], loading && 'opacity-70 cursor-wait', className)}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? (
        <>
          <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          {children}
        </>
      ) : (
        children
      )}
    </button>
  )
})

export default Button
