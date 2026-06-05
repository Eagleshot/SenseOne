const sanitizeFileName = (value: string) =>
  value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "") || "chart";

const inlineSvgStyles = (source: Element, target: Element) => {
  const computedStyle = getComputedStyle(source);
  Array.from(computedStyle).forEach((property) => {
    if (target instanceof SVGElement) {
      target.style.setProperty(property, computedStyle.getPropertyValue(property));
    }
  });

  const sourceChildren = Array.from(source.children);
  const targetChildren = Array.from(target.children);
  sourceChildren.forEach((child, index) => {
    const targetChild = targetChildren[index];
    if (targetChild) {
      inlineSvgStyles(child, targetChild);
    }
  });
};

// Serialize a live SVG element to a standalone, style-inlined <img>, so it can be
// drawn onto a canvas. `color` resolves the SVG's `currentColor` (e.g. lucide
// icon strokes); `fontFamily` keeps any embedded text on-brand.
const rasterizeSvg = (
  svg: SVGSVGElement,
  width: number,
  height: number,
  { color, fontFamily }: { color?: string; fontFamily?: string }
): Promise<{ image: HTMLImageElement; revoke: () => void }> => {
  const clone = svg.cloneNode(true) as SVGSVGElement;
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  clone.setAttribute("xmlns:xlink", "http://www.w3.org/1999/xlink");
  clone.setAttribute("width", `${width}`);
  clone.setAttribute("height", `${height}`);
  if (!clone.getAttribute("viewBox")) {
    clone.setAttribute("viewBox", `0 0 ${width} ${height}`);
  }
  inlineSvgStyles(svg, clone);
  if (color) clone.style.color = color;
  if (fontFamily) clone.style.fontFamily = fontFamily;

  const markup = new XMLSerializer().serializeToString(clone);
  const blob = new Blob([markup], { type: "image/svg+xml;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const revoke = () => URL.revokeObjectURL(url);

  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve({ image, revoke });
    image.onerror = () => {
      revoke();
      reject(new Error("Unable to export chart image."));
    };
    image.src = url;
  });
};

const ICON_SIZE = 20; // matches the in-app h-5 w-5 header icon

export const exportChartAsImage = async (
  container: HTMLDivElement,
  { title, subtitle, icon }: { title: string; subtitle?: string; icon?: SVGSVGElement | null }
) => {
  const svg = container.querySelector("svg");
  if (!svg) return;
  const rect = svg.getBoundingClientRect();
  if (!rect.width || !rect.height) return;

  const computedContainerStyle = getComputedStyle(container);
  const fontFamily = computedContainerStyle.fontFamily || "sans-serif";
  const foregroundColor = computedContainerStyle.color || "#111827";
  const width = Math.ceil(rect.width);
  const chartHeight = Math.ceil(rect.height);

  const chart = await rasterizeSvg(svg, width, chartHeight, { color: foregroundColor, fontFamily });

  // The header icon, in its on-screen (muted) colour. Falls back to title-only
  // if it can't be rendered.
  let iconImage: { image: HTMLImageElement; revoke: () => void } | null = null;
  if (icon) {
    try {
      iconImage = await rasterizeSvg(icon, ICON_SIZE, ICON_SIZE, { color: getComputedStyle(icon).color });
    } catch {
      iconImage = null;
    }
  }

  try {
    const scale = 2;
    const hasSubtitle = Boolean(subtitle?.trim());
    const titleBlockHeight = hasSubtitle ? 72 : 56;
    const exportHeight = chartHeight + titleBlockHeight;

    const canvas = document.createElement("canvas");
    canvas.width = Math.ceil(width * scale);
    canvas.height = Math.ceil(exportHeight * scale);
    const context = canvas.getContext("2d");
    if (!context) throw new Error("Unable to export chart image.");

    context.scale(scale, scale);
    // Transparent background — no fill, so the exported PNG keeps an alpha channel.

    // Header, mirroring the in-app heading: icon + bold title.
    const titleX = iconImage ? 16 + ICON_SIZE + 8 : 16;
    if (iconImage) {
      context.drawImage(iconImage.image, 16, 18, ICON_SIZE, ICON_SIZE);
    }
    context.fillStyle = foregroundColor;
    context.font = `700 24px ${fontFamily}`; // text-2xl / font-bold
    context.textBaseline = "top";
    context.fillText(title, titleX, 16);

    if (hasSubtitle && subtitle) {
      context.globalAlpha = 0.72;
      context.fillStyle = foregroundColor;
      context.font = `400 12px ${fontFamily}`;
      context.fillText(subtitle, titleX, 44);
      context.globalAlpha = 1;
    }

    context.drawImage(chart.image, 0, titleBlockHeight, width, chartHeight);

    const link = document.createElement("a");
    link.href = canvas.toDataURL("image/png");
    link.download = `${sanitizeFileName(title)}.png`;
    link.click();
  } finally {
    chart.revoke();
    iconImage?.revoke();
  }
};
