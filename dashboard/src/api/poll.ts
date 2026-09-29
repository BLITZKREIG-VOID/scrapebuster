import { useState, useEffect, useRef, useCallback } from 'react';

interface CacheEntry<T> {
  data: T;
  timestamp: Date;
}

// Global in-memory SWR cache map
const memoryCache = new Map<string, CacheEntry<unknown>>();

// Global listeners for network partition notifications
type NetworkListener = (isUnreachable: boolean, lastSnapshotTime: Date | null) => void;
const networkListeners = new Set<NetworkListener>();

let globalUnreachable = false;
let globalLastSnapshot: Date | null = null;

function notifyNetworkStatus(unreachable: boolean, lastSnapshot: Date | null) {
  globalUnreachable = unreachable;
  if (lastSnapshot) globalLastSnapshot = lastSnapshot;
  networkListeners.forEach((listener) => listener(globalUnreachable, globalLastSnapshot));
}

export function subscribeNetworkStatus(listener: NetworkListener) {
  networkListeners.add(listener);
  listener(globalUnreachable, globalLastSnapshot);
  return () => {
    networkListeners.delete(listener);
  };
}

export interface UsePollOptions {
  cacheKey?: string;
  intervalMs?: number;
}

export function usePoll<T>(
  fn: () => Promise<T>,
  intervalMsOrOptions: number | UsePollOptions = 1000
) {
  const options: UsePollOptions =
    typeof intervalMsOrOptions === 'number'
      ? { intervalMs: intervalMsOrOptions }
      : intervalMsOrOptions;

  const intervalMs = options.intervalMs ?? 1000;
  const cacheKey = options.cacheKey || fn.name || 'default_endpoint';

  // Read from SWR in-memory cache synchronously on initialization to eliminate layout shifts
  const cached = memoryCache.get(cacheKey) as CacheEntry<T> | undefined;

  const [data, setData] = useState<T | null>(cached ? cached.data : null);
  const [error, setError] = useState<Error | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(cached ? cached.timestamp : null);
  const [isLoading, setIsLoading] = useState<boolean>(!cached);

  const savedFn = useRef(fn);
  useEffect(() => {
    savedFn.current = fn;
  }, [fn]);

  // Optimistic updater for active operator actions
  const mutate = useCallback(
    (optimisticData: T | null | ((prev: T | null) => T | null)) => {
      setData((prev) => {
        const nextVal =
          typeof optimisticData === 'function'
            ? (optimisticData as (p: T | null) => T | null)(prev)
            : optimisticData;
        if (nextVal !== null) {
          memoryCache.set(cacheKey, { data: nextVal, timestamp: new Date() });
        }
        return nextVal;
      });
    },
    [cacheKey]
  );

  useEffect(() => {
    let timeoutId: number;
    let isMounted = true;

    const executePoll = async () => {
      try {
        const result = await savedFn.current();
        if (isMounted) {
          const now = new Date();
          memoryCache.set(cacheKey, { data: result, timestamp: now });
          setData(result);
          setError(null);
          setLastUpdated(now);
          setIsLoading(false);
          notifyNetworkStatus(false, now);
        }
      } catch (err) {
        if (isMounted) {
          const formattedErr = err instanceof Error ? err : new Error(String(err));
          setError(formattedErr);
          setIsLoading(false);
          const cachedEntry = memoryCache.get(cacheKey);
          notifyNetworkStatus(true, cachedEntry ? cachedEntry.timestamp : null);
        }
      } finally {
        if (isMounted) {
          timeoutId = window.setTimeout(executePoll, intervalMs);
        }
      }
    };

    executePoll();

    return () => {
      isMounted = false;
      window.clearTimeout(timeoutId);
    };
  }, [cacheKey, intervalMs]);

  return {
    data,
    error,
    lastUpdated,
    isLoading,
    isCached: Boolean(cached),
    mutate,
  };
}
