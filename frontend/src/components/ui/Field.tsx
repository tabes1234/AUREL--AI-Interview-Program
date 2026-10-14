import { useId } from 'react'
import type { ChangeEvent } from 'react'
import { AlertCircle, Check } from 'lucide-react'
import { cn } from '../../lib/cn'

const inputBaseClasses =
  'w-full rounded-lg border bg-white px-3.5 py-2.5 text-sm text-ink placeholder:text-slate-400 transition-colors focus:outline-none focus:ring-2 disabled:cursor-not-allowed disabled:bg-slate-50'

const inputNormalClasses = 'border-slate-300 focus:border-brand-600 focus:ring-brand-600/25'
const inputErrorClasses = 'border-red-400 focus:border-red-500 focus:ring-red-400/25'

function FieldError({ id, message }: { id: string; message: string }) {
  return (
    <p id={id} role="alert" className="mt-1.5 flex items-center gap-1 text-xs text-red-600">
      <AlertCircle className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
      {message}
    </p>
  )
}

interface TextFieldProps {
  label: string
  value: string
  onChange: (value: string) => void
  onBlur?: () => void
  error?: string
  hint?: string
  required?: boolean
  placeholder?: string
  maxLength?: number
}

export function TextField({
  label,
  value,
  onChange,
  onBlur,
  error,
  hint,
  required,
  placeholder,
  maxLength,
}: TextFieldProps) {
  const id = useId()
  const errorId = `${id}-error`
  const hintId = `${id}-hint`
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-ink-strong">
        {label}
        {required ? <span className="ml-1 text-red-500">*</span> : null}
      </label>
      <input
        id={id}
        type="text"
        value={value}
        placeholder={placeholder}
        maxLength={maxLength}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : hint ? hintId : undefined}
        onChange={(event: ChangeEvent<HTMLInputElement>) => onChange(event.target.value)}
        onBlur={onBlur}
        className={cn(inputBaseClasses, error ? inputErrorClasses : inputNormalClasses)}
      />
      {hint && !error ? (
        <p id={hintId} className="mt-1.5 text-xs text-ink-soft">
          {hint}
        </p>
      ) : null}
      {error ? <FieldError id={errorId} message={error} /> : null}
    </div>
  )
}

interface TextAreaFieldProps {
  label: string
  value: string
  onChange: (value: string) => void
  onBlur?: () => void
  error?: string
  hint?: string
  placeholder?: string
  maxLength: number
  rows?: number
}

export function TextAreaField({
  label,
  value,
  onChange,
  onBlur,
  error,
  hint,
  placeholder,
  maxLength,
  rows = 4,
}: TextAreaFieldProps) {
  const id = useId()
  const errorId = `${id}-error`
  const hintId = `${id}-hint`
  const remaining = maxLength - value.length
  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between">
        <label htmlFor={id} className="block text-sm font-medium text-ink-strong">
          {label}
          <span className="ml-1.5 text-xs font-normal text-ink-soft">选填</span>
        </label>
        <span
          className={cn(
            'text-xs',
            remaining < 50 ? 'text-amber-600' : 'text-ink-soft',
          )}
        >
          {value.length}/{maxLength}
        </span>
      </div>
      <textarea
        id={id}
        value={value}
        placeholder={placeholder}
        maxLength={maxLength}
        rows={rows}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : hint ? hintId : undefined}
        onChange={(event: ChangeEvent<HTMLTextAreaElement>) => onChange(event.target.value)}
        onBlur={onBlur}
        className={cn(inputBaseClasses, 'resize-none', error ? inputErrorClasses : inputNormalClasses)}
      />
      {hint && !error ? (
        <p id={hintId} className="mt-1.5 text-xs text-ink-soft">
          {hint}
        </p>
      ) : null}
      {error ? <FieldError id={errorId} message={error} /> : null}
    </div>
  )
}

export interface RadioOption {
  value: string
  label: string
  description?: string
}

interface RadioCardGroupProps {
  legend: string
  name: string
  options: RadioOption[]
  value: string
  onChange: (value: string) => void
  error?: string
  columns?: 2 | 3
}

export function RadioCardGroup({
  legend,
  name,
  options,
  value,
  onChange,
  error,
  columns = 3,
}: RadioCardGroupProps) {
  const errorId = `${name}-error`
  return (
    <fieldset aria-describedby={error ? errorId : undefined}>
      <legend className="mb-2.5 flex items-center gap-2 text-sm font-semibold tracking-wide text-ink-strong">
        <span
          aria-hidden="true"
          className="h-3.5 w-1 shrink-0 rounded-full bg-gradient-to-b from-brand-500 to-brand-300"
        />
        {legend}
      </legend>
      <div
        className={cn(
          'grid gap-3',
          columns === 2 ? 'grid-cols-2' : 'grid-cols-1 sm:grid-cols-3',
        )}
      >
        {options.map((option) => {
          const selected = value === option.value
          return (
            <label
              key={option.value}
              className={cn(
                'group relative flex cursor-pointer flex-col rounded-xl border p-4 transition-all duration-200',
                selected
                  ? 'border-brand-500 bg-gradient-to-br from-brand-50 via-white to-brand-50/60 shadow-[0_2px_10px_rgba(77,131,214,0.12)] ring-1 ring-brand-500/25'
                  : 'border-line bg-white hover:-translate-y-0.5 hover:border-brand-400/70 hover:shadow-[0_2px_8px_rgba(49,95,173,0.08)]',
              )}
            >
              <input
                type="radio"
                name={name}
                value={option.value}
                checked={selected}
                onChange={() => onChange(option.value)}
                className="peer sr-only"
              />
              <span
                className={cn(
                  'pr-7 text-sm font-semibold transition-colors',
                  selected ? 'text-brand-700' : 'text-ink-strong group-hover:text-brand-700',
                )}
              >
                {option.label}
              </span>
              {option.description ? (
                <span
                  className={cn(
                    'mt-1 text-xs leading-relaxed transition-colors',
                    selected ? 'text-brand-700/75' : 'text-ink-soft',
                  )}
                >
                  {option.description}
                </span>
              ) : null}
              <span
                aria-hidden="true"
                className={cn(
                  'absolute right-3.5 top-3.5 flex h-4 w-4 items-center justify-center rounded-full border transition-all duration-200',
                  selected
                    ? 'border-brand-600 bg-brand-600'
                    : 'border-slate-300 bg-white group-hover:border-brand-400',
                )}
              >
                {selected ? <Check className="h-2.5 w-2.5 text-white" strokeWidth={3.5} /> : null}
              </span>
            </label>
          )
        })}
      </div>
      {error ? <FieldError id={errorId} message={error} /> : null}
    </fieldset>
  )
}
