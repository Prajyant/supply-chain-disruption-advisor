import { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';

interface CollapsibleSectionProps {
  title: string;
  icon?: React.ReactNode;
  defaultOpen?: boolean;
  children: React.ReactNode;
  className?: string;
}

export function CollapsibleSection({
  title,
  icon,
  defaultOpen = false,
  children,
  className = '',
}: CollapsibleSectionProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className={`card min-w-0 space-y-3 overflow-hidden ${className}`}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex w-full items-center justify-between gap-3 text-left transition-colors hover:text-white"
      >
        <div className="flex min-w-0 items-center gap-3">
          {icon}
          <span className="text-base font-semibold text-white">{title}</span>
        </div>
        {isOpen ? (
          <ChevronDown className="h-5 w-5 shrink-0 text-slate-400" />
        ) : (
          <ChevronRight className="h-5 w-5 shrink-0 text-slate-400" />
        )}
      </button>
      {isOpen && <div className="space-y-3">{children}</div>}
    </div>
  );
}
