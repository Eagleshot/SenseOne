import { useEffect, useState } from "react";

export type SidebarState = {
  isSidebarOpen: boolean;
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
};

const isDesktopViewport = () => (typeof window !== "undefined" ? window.innerWidth >= 1024 : true);

export const useSidebarState = (): SidebarState => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(isDesktopViewport);

  useEffect(() => {
    const desktopQuery = window.matchMedia("(min-width: 1024px)");
    const syncSidebarState = (matches: boolean) => {
      setIsSidebarOpen(matches);
    };
    const handleChange = (event: MediaQueryListEvent) => syncSidebarState(event.matches);

    syncSidebarState(desktopQuery.matches);
    desktopQuery.addEventListener("change", handleChange);

    return () => {
      desktopQuery.removeEventListener("change", handleChange);
    };
  }, []);

  return {
    isSidebarOpen,
    toggleSidebar: () => setIsSidebarOpen((currentValue) => !currentValue),
    setSidebarOpen: (open) => setIsSidebarOpen(open),
  };
};
