import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { Link, type LinkProps } from 'react-router-dom'
import { cn } from '../../lib/cn'

export type ButtonVariant = 'primary' | 'secondary' | 'ghost'
export type ButtonSize = 'sm' | 'md' | 'lg'

const baseClasses =
  'inline-flex select-none items-center justify-center gap-2 rounded-lg font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/50 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60'

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    'bg-[linear-gradient(180deg,#5589D9_0%,#4D83D6_100%)] text-white shadow-[0_1px_2px_rgba(49,95,173,0.18)] hover:-translate-y-px hover:bg-[linear-gradient(180deg,#4A7ECC_0%,#3F72BE_100%)] hover:shadow-[0_5px_14px_rgba(49,95,173,0.24)] active:translate-y-0 active:scale-[0.985] active:shadow-none',
  secondary:
    'border border-brand-600/40 bg-white text-brand-600 hover:-translate-y-px hover:border-brand-600 hover:bg-brand-50 hover:shadow-[0_4px_12px_rgba(77,131,214,0.16)] active:translate-y-0 active:scale-[0.985] active:shadow-none',
  ghost: 'text-ink-soft hover:bg-mist hover:text-ink active:scale-[0.985]',
}

const sizeClasses: Record<ButtonSize, string> = {
  sm: 'h-8 px-3 text-sm',
  md: 'h-10 px-4 text-sm',
  lg: 'h-12 px-6 text-base',
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  children: ReactNode
}

export function Button({
  variant = 'primary',
  size = 'md',
  className,
  type = 'button',
  children,
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      className={cn(baseClasses, variantClasses[variant], sizeClasses[size], className)}
      {...rest}
    >
      {children}
    </button>
  )
}

interface ButtonLinkProps extends LinkProps {
  variant?: ButtonVariant
  size?: ButtonSize
  children: ReactNode
}

export function ButtonLink({
  variant = 'primary',
  size = 'md',
  className,
  children,
  ...rest
}: ButtonLinkProps) {
  return (
    <Link
      className={cn(baseClasses, variantClasses[variant], sizeClasses[size], className)}
      {...rest}
    >
      {children}
    </Link>
  )
}
