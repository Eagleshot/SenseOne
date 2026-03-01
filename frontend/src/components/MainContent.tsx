import React from "react";

import { motion } from "framer-motion";

import { HeroImage } from "./HeroImage";
import { WeatherDetail } from "./WeatherDetail";
import { SensorHistoryPanel } from "./SensorHistoryPanel";
import { WebsiteSettingsPanel } from "./WebsiteSettingsPanel";
import { InteractiveMap } from "./InteractiveMap";
import { useApp } from "@/contexts/AppContext";

export const MainContent: React.FC = () => {
  const { isAuthenticated } = useApp();

  return (
    <div className="flex-1">
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.4 }}
        className="p-4 md:p-6 lg:p-8 space-y-[2.625rem] max-w-6xl mx-auto"
      >
        <HeroImage />
        <WeatherDetail />
        <SensorHistoryPanel />
        {isAuthenticated && <WebsiteSettingsPanel />}
        <InteractiveMap />

        <footer className="border-t border-border py-8 text-center">
          <div className="space-y-2 text-xs text-muted-foreground">
            <p>
              <strong className="font-semibold text-foreground">&copy; Eagleshot</strong>. All rights reserved.
            </p>
            <p>
              Engineered by{" "}
              <a
                href="https://www.eagleshot.ch"
                target="_blank"
                rel="noopener noreferrer"
                className="underline underline-offset-4 hover:text-foreground"
              >
                Eagleshot
              </a>{" "}
              in Switzerland.
            </p>
          </div>
        </footer>
      </motion.div>
    </div>
  );
};

