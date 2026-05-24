import { lazy, Suspense, useEffect, useState } from "react";

import { motion } from "framer-motion";
import { Copy, Pencil, Save, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { DESCRIPTION_MAX_LENGTH } from "@/api/stations";

import { HeroImage } from "./HeroImage";
import { useApp } from "@/contexts/AppContext";

const WeatherDetail = lazy(() => import("./WeatherDetail").then((module) => ({ default: module.WeatherDetail })));
const SensorHistoryPanel = lazy(() =>
  import("./SensorHistoryPanel").then((module) => ({ default: module.SensorHistoryPanel }))
);
const WebsiteSettingsPanel = lazy(() =>
  import("./WebsiteSettingsPanel").then((module) => ({ default: module.WebsiteSettingsPanel }))
);
const InteractiveMap = lazy(() => import("./InteractiveMap").then((module) => ({ default: module.InteractiveMap })));

const SectionFallback = () => <div className="panel-shell min-h-[10rem] animate-pulse" aria-hidden="true" />;

export const MainContent: React.FC = () => {
  const {
    activeWebcam,
    isAuthenticated,
    description,
    descriptionDraft,
    setDraftDescription,
    saveDescription,
    isDescriptionSaving,
    descriptionError,
    isStationConfigLoading,
  } = useApp();
  const [stationIdCopied, setStationIdCopied] = useState(false);
  const [isEditingDescription, setIsEditingDescription] = useState(false);

  const hasDescriptionChanges = descriptionDraft !== description;

  const handleSaveDescription = async () => {
    const didSave = await saveDescription();
    if (didSave) {
      setIsEditingDescription(false);
    }
  };

  const handleCancelDescription = () => {
    setDraftDescription(description);
    setIsEditingDescription(false);
  };

  const handleStartEdit = () => {
    setDraftDescription(description);
    setIsEditingDescription(true);
  };

  const descriptionButtonsDisabled = isStationConfigLoading || isDescriptionSaving || !hasDescriptionChanges;

  useEffect(() => {
    setIsEditingDescription(false);
  }, [activeWebcam.id]);

  const handleCopyStationId = async () => {
    if (!activeWebcam.id) return;

    try {
      await navigator.clipboard.writeText(activeWebcam.id);
      setStationIdCopied(true);
      window.setTimeout(() => setStationIdCopied(false), 1500);
    } catch {
      setStationIdCopied(false);
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
                {isEditingDescription ? (
                  <div className="space-y-3">
                    <Textarea
                      value={descriptionDraft}
                      onChange={(event) => setDraftDescription(event.target.value.slice(0, DESCRIPTION_MAX_LENGTH))}
                      placeholder="Add a short description for this station."
                      disabled={isDescriptionSaving || isStationConfigLoading}
                      maxLength={DESCRIPTION_MAX_LENGTH}
                      className="min-h-[116px] resize-y"
                    />
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-xs text-muted-foreground">
                        {descriptionDraft.length}/{DESCRIPTION_MAX_LENGTH} characters
                      </p>
                      <div className="flex gap-2">
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={handleCancelDescription}
                          disabled={isStationConfigLoading || isDescriptionSaving}
                          className="btn-panel"
                        >
                          <X className="h-4 w-4" />
                          Cancel
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          onClick={() => void handleSaveDescription()}
                          disabled={descriptionButtonsDisabled}
                          className="btn-panel"
                        >
                          <Save className="h-4 w-4" />
                          Save
                        </Button>
                      </div>
                    </div>
                    {descriptionError && <p className="text-xs text-destructive">{descriptionError}</p>}
                  </div>
                ) : description ? (
                  <p className="text-sm leading-relaxed text-muted-foreground whitespace-pre-wrap [overflow-wrap:anywhere]">
                    {description}
                  </p>
                ) : (
                  <p className="text-sm italic leading-relaxed text-muted-foreground">
                    {isAuthenticated ? "No description yet. Add one for this station." : "No description yet."}
                  </p>
                )}
                {descriptionError && !isEditingDescription && <p className="pt-1 text-xs text-destructive">{descriptionError}</p>}
              </div>
              {isAuthenticated && !isEditingDescription && (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={handleStartEdit}
                  disabled={isStationConfigLoading}
                  className="btn-inline-muted shrink-0 gap-2 self-start"
                >
                  <Pencil className="h-4 w-4" />
                  {description ? "Edit description" : "Add description"}
                </Button>
              )}
            </div>
          </section>
        )}
        <Suspense fallback={<SectionFallback />}>
          <WeatherDetail />
        </Suspense>
        <Suspense fallback={<SectionFallback />}>
          <SensorHistoryPanel />
        </Suspense>
        {isAuthenticated && (
          <Suspense fallback={<SectionFallback />}>
            <WebsiteSettingsPanel />
          </Suspense>
        )}
        <Suspense fallback={<SectionFallback />}>
          <InteractiveMap />
        </Suspense>

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
              in Switzerland &#x1F1E8;&#x1F1ED;
            </p>
            <div className="flex items-center justify-center gap-2 md:justify-end">
              {activeWebcam.id && (
                <>
                  <p>{`Station ID: ${activeWebcam.id}`}</p>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => void handleCopyStationId()}
                    className="btn-inline-muted gap-1 text-xs underline underline-offset-4"
                    aria-label={`Copy station ID ${activeWebcam.id}`}
                  >
                    <Copy className="h-3 w-3" />
                    {stationIdCopied ? "Copied" : "Copy"}
                  </Button>
                </>
              )}
            </div>
          </div>
        </footer>
      </motion.div>
    </div>
  );
};

