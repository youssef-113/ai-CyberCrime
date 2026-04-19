import { forwardRef } from 'react'
import clsx from 'clsx'

const Input = forwardRef(function Input(
  { label, error, success, hint, className, id, ...props },
  ref
) {
  const inputId = id || `input-${label?.replace(/\s+/g, '-').toLowerCase() || Math.random().toString(36).slice(2)}`

  return (
    <div className="w-full">
      {label && (
        <label htmlFor={inputId} className="block text-sm font-medium text-neutral-300 mb-1.5">
          {label}
        </label>
      )}
      <input
        ref={ref}
        id={inputId}
        className={clsx(
          'input-field',
          error && 'input-error',
          success && 'input-success',
          className
        )}
        aria-invalid={!!error}
        aria-describedby={error ? `${inputId}-error` : hint ? `${inputId}-hint` : undefined}
        {...props}
      />
      {error && (
        <p id={`${inputId}-error`} className="mt-1 text-sm text-danger-light" role="alert">
          {error}
        </p>
      )}
      {hint && !error && (
        <p id={`${inputId}-hint`} className="mt-1 text-sm text-neutral-500">
          {hint}
        </p>
      )}
    </div>
  )
})

export default Input
