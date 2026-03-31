import type { InputHTMLAttributes } from "react";

type InputProps = InputHTMLAttributes<HTMLInputElement> & {
  label?: string;
  error?: string;
  className?: string;
};

export function Input({ label, error, className = "", id, ...rest }: InputProps) {
  const inputId = id || (label ? label.toLowerCase().replace(/\s+/g, "-") : undefined);

  return (
    <div className="ui-input-wrap">
      {label ? (
        <label htmlFor={inputId} className="ui-input-label">
          {label}
        </label>
      ) : null}
      <input
        id={inputId}
        className={["ui-input", error ? "ui-input--error" : "", className].filter(Boolean).join(" ")}
        {...rest}
      />
      {error ? <span className="ui-input-error">{error}</span> : null}
    </div>
  );
}
