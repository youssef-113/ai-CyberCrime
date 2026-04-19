import clsx from 'clsx'

const variants = {
  primary: 'badge-primary',
  success: 'badge-success',
  warning: 'badge-warning',
  danger: 'badge-danger',
  neutral: 'badge-neutral',
}

export default function Badge({ variant = 'neutral', className, children, ...props }) {
  return (
    <span className={clsx(variants[variant], className)} {...props}>
      {children}
    </span>
  )
}
