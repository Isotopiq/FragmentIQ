import { DependencyList, useEffect, useState } from "react";

export function useAsync<T>(factory: () => Promise<T>, deps: DependencyList) {
  const [data, setData] = useState<T | undefined>();
  const [error, setError] = useState<Error | undefined>();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setLoading(true);
    factory()
      .then((value) => {
        if (active) {
          setData(value);
          setError(undefined);
        }
      })
      .catch((err) => {
        if (active) setError(err instanceof Error ? err : new Error(String(err)));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, deps);

  return { data, error, loading };
}
