import { useState, useRef, useEffect, useCallback } from 'react';
import { AlertTriangle, CheckCircle2 } from 'lucide-react';
import { cn } from '../lib/utils';

interface HoldToConfirmButtonProps {
  onConfirm: () => void | Promise<void>;
  holdDurationMs?: number;
  children: React.ReactNode;
  confirmText?: string;
  className?: string;
  disabled?: boolean;
}

export function HoldToConfirmButton({
  onConfirm,
  holdDurationMs = 1500,
  children,
  confirmText = 'Confirmed — Action Dispatched',
  className,
  disabled = false,
}: HoldToConfirmButtonProps) {
  const [progress, setProgress] = useState(0); // 0 to 100
  const [isHolding, setIsHolding] = useState(false);
  const [isCompleted, setIsCompleted] = useState(false);

  const startTimeRef = useRef<number | null>(null);
  const animFrameRef = useRef<number | null>(null);

  const cancelHold = useCallback(() => {
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    }
    startTimeRef.current = null;
    setIsHolding(false);
    setProgress(0);
  }, []);

  const triggerConfirm = useCallback(async () => {
    setIsCompleted(true);
    setProgress(100);
    setIsHolding(false);
    try {
      await onConfirm();
    } finally {
      setTimeout(() => {
        setIsCompleted(false);
        setProgress(0);
      }, 1800);
    }
  }, [onConfirm]);

  const updateProgress = useCallback(() => {
    function step() {
      if (!startTimeRef.current) return;
      const elapsed = performance.now() - startTimeRef.current;
      const pct = Math.min(100, (elapsed / holdDurationMs) * 100);
      setProgress(pct);

      if (pct >= 100) {
        triggerConfirm();
      } else {
        animFrameRef.current = requestAnimationFrame(step);
      }
    }

    animFrameRef.current = requestAnimationFrame(step);
  }, [holdDurationMs, triggerConfirm]);

  const startHold = () => {
    if (disabled || isCompleted) return;
    setIsHolding(true);
    startTimeRef.current = performance.now();
    updateProgress();
  };

  useEffect(() => {
    return () => {
      if (animFrameRef.current) {
        cancelAnimationFrame(animFrameRef.current);
      }
    };
  }, []);

  return (
    <button
      type="button"
      onMouseDown={startHold}
      onMouseUp={cancelHold}
      onMouseLeave={cancelHold}
      onTouchStart={startHold}
      onTouchEnd={cancelHold}
      onContextMenu={(e) => e.preventDefault()}
      disabled={disabled || isCompleted}
      className={cn(
        'relative group overflow-hidden select-none rounded-lg px-4 py-2 text-xs font-mono font-semibold transition-all duration-200 border',
        'border-red-500/40 bg-red-950/20 text-red-300 hover:border-red-500/80 hover:bg-red-950/40',
        'active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer',
        isHolding && 'ring-1 ring-red-500/60 shadow-[0_0_15px_rgba(220,38,38,0.3)]',
        isCompleted && 'border-emerald-500/80 bg-emerald-950/40 text-emerald-300 ring-1 ring-emerald-500/50',
        className
      )}
    >
      {/* Animated Fill Bar Layer */}
      <div
        className={cn(
          'absolute top-0 bottom-0 left-0 bg-red-600/40 transition-none pointer-events-none',
          isCompleted && 'bg-emerald-600/40'
        )}
        style={{ width: `${progress}%` }}
      />

      {/* Button Content */}
      <div className="relative z-10 flex items-center justify-center gap-2">
        {isCompleted ? (
          <>
            <CheckCircle2 size={13} className="text-emerald-400" />
            <span>{confirmText}</span>
          </>
        ) : (
          <>
            <AlertTriangle
              size={13}
              className={cn(
                'text-red-400 transition-transform',
                isHolding && 'scale-110 animate-bounce'
              )}
            />
            <span>{children}</span>
            <span className="text-[10px] text-red-400/80 font-mono tracking-wider ml-1">
              {isHolding ? `[Hold: ${Math.round(progress)}%]` : '[Hold 1.5s]'}
            </span>
          </>
        )}
      </div>
    </button>
  );
}

export default HoldToConfirmButton;
