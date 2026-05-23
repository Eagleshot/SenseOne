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

export const exportChartAsImage = async (
  container: HTMLDivElement,
  { title, subtitle }: { title: string; subtitle?: string }
) => {
  const svg = container.querySelector("svg");
  if (!svg) return;
  const rect = svg.getBoundingClientRect();
  if (!rect.width || !rect.height) return;

  const serializer = new XMLSerializer();
  const svgClone = svg.cloneNode(true) as SVGSVGElement;
  svgClone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  svgClone.setAttribute("xmlns:xlink", "http://www.w3.org/1999/xlink");
  svgClone.setAttribute("width", `${Math.ceil(rect.width)}`);
  svgClone.setAttribute("height", `${Math.ceil(rect.height)}`);
  if (!svgClone.getAttribute("viewBox")) {
    svgClone.setAttribute("viewBox", `0 0 ${Math.ceil(rect.width)} ${Math.ceil(rect.height)}`);
  }

  const computedContainerStyle = getComputedStyle(container);
  inlineSvgStyles(svg, svgClone);
  svgClone.style.fontFamily = computedContainerStyle.fontFamily;
  svgClone.style.color = computedContainerStyle.color;

  const svgMarkup = serializer.serializeToString(svgClone);
  const svgBlob = new Blob([svgMarkup], { type: "image/svg+xml;charset=utf-8" });
  const svgUrl = URL.createObjectURL(svgBlob);

  try {
    await new Promise<void>((resolve, reject) => {
      const image = new Image();
      image.onload = () => {
        const scale = 2;
        const hasSubtitle = Boolean(subtitle?.trim());
        const titleBlockHeight = 72;
        const exportHeight = rect.height + titleBlockHeight;
        const canvas = document.createElement("canvas");
        canvas.width = Math.ceil(rect.width * scale);
        canvas.height = Math.ceil(exportHeight * scale);
        const context = canvas.getContext("2d");
        if (!context) {
          reject(new Error("Unable to export chart image."));
          return;
        }

        context.scale(scale, scale);
        const backgroundColor = getComputedStyle(container).backgroundColor || "#ffffff";
        const foregroundColor = computedContainerStyle.color || "#111827";
        context.fillStyle = backgroundColor;
        context.fillRect(0, 0, rect.width, exportHeight);

        context.fillStyle = foregroundColor;
        context.font = `600 20px ${computedContainerStyle.fontFamily || "sans-serif"}`;
        context.textBaseline = "top";
        context.fillText(title, 16, 14);

        if (hasSubtitle && subtitle) {
          context.globalAlpha = 0.72;
          context.fillStyle = foregroundColor;
          context.font = `400 12px ${computedContainerStyle.fontFamily || "sans-serif"}`;
          context.fillText(subtitle, 16, 40);
          context.globalAlpha = 1;
        }

        context.drawImage(image, 0, titleBlockHeight, rect.width, rect.height);

        const link = document.createElement("a");
        link.href = canvas.toDataURL("image/png");
        link.download = `${sanitizeFileName(title)}.png`;
        link.click();
        resolve();
      };
      image.onerror = () => reject(new Error("Unable to export chart image."));
      image.src = svgUrl;
    });
  } finally {
    URL.revokeObjectURL(svgUrl);
  }
};

