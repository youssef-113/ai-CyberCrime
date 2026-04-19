import clsx from 'clsx'

const variants = {
  default: 'perspective-card',
  elevated: 'perspective-card-elevated',
  glass: 'perspective-card-glass',
}

function Card({ variant = 'default', className, children, ...props }) {
  return (
    <div className={clsx(variants[variant], className)} {...props}>
      {children}
    </div>
  )
}

export function CardHeader({ className, children }) {
  return (
    <div className={clsx('px-6 py-4 border-b border-neutral-800', className)}>
      {children}
    </div>
  )
}

export function CardBody({ className, children }) {
  return (
    <div className={clsx('px-6 py-4', className)}>
      {children}
    </div>
  )
}

export { Card }
export default Card

export function CardFooter({ className, children }) {
  return (
    <div className={clsx('px-6 py-4 border-t border-neutral-800', className)}>
      {children}
    </div>
  )
}
