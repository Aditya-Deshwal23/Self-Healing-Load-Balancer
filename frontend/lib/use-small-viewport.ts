"use client";

import { useEffect, useState } from "react";

export function useSmallViewport() {
  const [smallViewport, setSmallViewport] = useState(false);

  useEffect(() => {
    const query = window.matchMedia("(max-width: 767px)");
    const syncViewport = () => setSmallViewport(query.matches);
    syncViewport();
    query.addEventListener("change", syncViewport);
    return () => query.removeEventListener("change", syncViewport);
  }, []);

  return smallViewport;
}
