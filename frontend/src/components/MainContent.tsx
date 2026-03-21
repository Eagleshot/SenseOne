import React, { useState } from "react";

import { motion } from "framer-motion";
import { Copy, Pencil, Save, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { DESCRIPTION_MAX_LENGTH } from "@/contexts/appContextUtils";

import { HeroImage } from "./HeroImage";
import { WeatherDetail } from "./WeatherDetail";
import { SensorHistoryPanel } from "./SensorHistoryPanel";
import { WebsiteSettingsPanel } from "./WebsiteSettingsPanel";
import { InteractiveMap } from "./InteractiveMap";
import { useApp } from "@/contexts/useApp";

export const MainContent: React.FC = () => {
  const {
    activeWebcam,
    isAuthenticated,
    description,
    descriptionDraft,
    setDraftDescription,
    isDescriptionEditing,
    startDescriptionEdit,
    cancelDescriptionEdit,
    saveDescription,
    isDescriptionSaving,
    descriptionError,
    isStationConfigLoading,
  } = useApp();
  const [cameraIdCopied, setCameraIdCopied] = useState(false);

  const handleCopyCameraId = async () => {
    if (!activeWebcam.id) return;

    try {
      await navigator.clipboard.writeText(activeWebcam.id);
      setCameraIdCopied(true);
      window.setTimeout(() => setCameraIdCopied(false), 1500);
    } catch {
      setCameraIdCopied(false);
    }
  };

  const showDescriptionSection = Boolean(description) || isAuthenticated;

  return (
    <div className="flex-1">
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.4 }}
        className="mx-auto max-w-6xl space-y-[2.625rem] p-4 md:p-6 lg:p-8"
      >
        <HeroImage />
        {showDescriptionSection && (
          <section className="space-y-3">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0 flex-1">
                {isDescriptionEditing ? (
                  <div className="space-y-3">
                    <Textarea
                      value={descriptionDraft}
                      onChange={(event) => setDraftDescription(event.target.value)}
                      placeholder="Add a short description for this station."
                      disabled={isDescriptionSaving || isStationConfigLoading}
                      maxLength={DESCRIPTION_MAX_LENGTH}
                      className="min-h-[116px] resize-y"
                    />
                    <div className="flex flex-wrap items-center gap-2">
                      <Button
                        type="button"
                        size="sm"
                        onClick={() => void saveDescription()}
                        disabled={isDescriptionSaving || isStationConfigLoading}
                        className="gap-2"
                      >
                        <Save className="h-4 w-4" />
                        {isDescriptionSaving ? "Saving..." : "Save"}
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={cancelDescriptionEdit}
                        disabled={isDescriptionSaving}
                        className="gap-2"
                      >
                        <X className="h-4 w-4" />
                        Cancel
                      </Button>
                      <p className="text-xs text-muted-foreground">
                        {descriptionDraft.length}/{DESCRIPTION_MAX_LENGTH} characters. Saved to this station&apos;s config file.
                      </p>
                    </div>
                  </div>
                ) : description ? (
                  <p className="text-sm leading-relaxed text-muted-foreground whitespace-pre-wrap [overflow-wrap:anywhere]">
                    {description}
                  </p>
                ) : (
                  <p className="text-sm italic leading-relaxed text-muted-foreground">
                    No description yet. Add one for this station.
                  </p>
                )}
                {descriptionError && <p className="pt-1 text-xs text-destructive">{descriptionError}</p>}
              </div>
              {isAuthenticated && !isDescriptionEditing && (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={startDescriptionEdit}
                  disabled={isStationConfigLoading}
                  className="shrink-0 gap-2 self-start"
                >
                  <Pencil className="h-4 w-4" />
                  {description ? "Edit description" : "Add description"}
                </Button>
              )}
            </div>
          </section>
        )}
        <WeatherDetail />
        <SensorHistoryPanel />
        {isAuthenticated && <WebsiteSettingsPanel />}
        <InteractiveMap />

        <footer className="border-t border-border py-8">
          <div className="grid gap-2 text-xs text-muted-foreground md:grid-cols-3 md:items-center">
            <p className="text-center md:text-left">&copy; Eagleshot. All rights reserved.</p>
            <p className="text-center">
              Engineered by{" "}
              <a
                href="https://www.eagleshot.ch"
                target="_blank"
                rel="noopener noreferrer"
                className="underline underline-offset-4 hover:text-foreground"
              >
                Eagleshot
              </a>{" "}
              in Switzerland 🇨🇭
            </p>
            <div className="flex items-center justify-center gap-2 md:justify-end">
              {activeWebcam.id && (
                <>
                  <p>{`Camera ID: ${activeWebcam.id}`}</p>
                  <button
                    type="button"
                    onClick={() => void handleCopyCameraId()}
                    className="inline-flex items-center gap-1 underline underline-offset-4 hover:text-foreground"
                    aria-label={`Copy camera ID ${activeWebcam.id}`}
                  >
                    <Copy className="h-3 w-3" />
                    {cameraIdCopied ? "Copied" : "Copy"}
                  </button>
                </>
              )}
            </div>
          </div>
        </footer>
      </motion.div>
    </div>
  );
};
