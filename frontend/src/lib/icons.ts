/**
 * Vessel glyph atlas for deck.gl IconLayer.
 *
 * Shape = declared ship type (shared/encoding/display_encoding.json),
 * color = suspicion (applied via mask tinting). Shapes are drawn white on a
 * canvas once at module init; directional shapes (triangle, chevron) point
 * NORTH so `getAngle = -cog` rotates them to course-over-ground.
 */

export const ICON_SIZE = 64;

const SHAPES = [
  "triangle",
  "square",
  "diamond",
  "pentagon",
  "cross",
  "shield",
  "hexagon",
  "chevron",
  "circle",
] as const;

export type ShapeKey = (typeof SHAPES)[number];

export const ROTATABLE = new Set<string>(["triangle", "chevron"]);

export interface IconMapping {
  [key: string]: { x: number; y: number; width: number; height: number; mask: boolean };
}

function drawShape(ctx: CanvasRenderingContext2D, shape: ShapeKey, ox: number): void {
  const s = ICON_SIZE;
  const c = ox + s / 2;
  const m = s / 2;
  ctx.fillStyle = "#ffffff";
  ctx.beginPath();
  switch (shape) {
    case "triangle": // kite pointing up (north) — reads as a vessel with heading
      ctx.moveTo(c, m - 26);
      ctx.lineTo(c + 17, m + 24);
      ctx.lineTo(c, m + 14);
      ctx.lineTo(c - 17, m + 24);
      break;
    case "square":
      ctx.rect(c - 17, m - 17, 34, 34);
      break;
    case "diamond":
      ctx.moveTo(c, m - 24);
      ctx.lineTo(c + 24, m);
      ctx.lineTo(c, m + 24);
      ctx.lineTo(c - 24, m);
      break;
    case "pentagon": {
      for (let i = 0; i < 5; i++) {
        const a = -Math.PI / 2 + (i * 2 * Math.PI) / 5;
        const x = c + 23 * Math.cos(a);
        const y = m + 23 * Math.sin(a);
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
      }
      break;
    }
    case "cross":
      ctx.moveTo(c - 7, m - 24);
      ctx.lineTo(c + 7, m - 24);
      ctx.lineTo(c + 7, m - 7);
      ctx.lineTo(c + 24, m - 7);
      ctx.lineTo(c + 24, m + 7);
      ctx.lineTo(c + 7, m + 7);
      ctx.lineTo(c + 7, m + 24);
      ctx.lineTo(c - 7, m + 24);
      ctx.lineTo(c - 7, m + 7);
      ctx.lineTo(c - 24, m + 7);
      ctx.lineTo(c - 24, m - 7);
      ctx.lineTo(c - 7, m - 7);
      break;
    case "shield":
      ctx.moveTo(c, m - 24);
      ctx.lineTo(c + 19, m - 16);
      ctx.lineTo(c + 19, m + 2);
      ctx.bezierCurveTo(c + 19, m + 14, c + 10, m + 21, c, m + 25);
      ctx.bezierCurveTo(c - 10, m + 21, c - 19, m + 14, c - 19, m + 2);
      ctx.lineTo(c - 19, m - 16);
      break;
    case "hexagon": {
      for (let i = 0; i < 6; i++) {
        const a = -Math.PI / 2 + (i * Math.PI) / 3;
        const x = c + 23 * Math.cos(a);
        const y = m + 23 * Math.sin(a);
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
      }
      break;
    }
    case "chevron": // band pointing up (north)
      ctx.moveTo(c - 22, m + 18);
      ctx.lineTo(c, m - 4);
      ctx.lineTo(c + 22, m + 18);
      ctx.lineTo(c + 22, m + 2);
      ctx.lineTo(c, m - 20);
      ctx.lineTo(c - 22, m + 2);
      break;
    case "circle":
      ctx.arc(c, m, 20, 0, Math.PI * 2);
      break;
  }
  ctx.closePath();
  ctx.fill();
}

let cached: { atlas: string; mapping: IconMapping } | null = null;

export function buildIconAtlas(): { atlas: string; mapping: IconMapping } {
  if (cached) return cached;
  const canvas = document.createElement("canvas");
  canvas.width = ICON_SIZE * SHAPES.length;
  canvas.height = ICON_SIZE;
  const ctx = canvas.getContext("2d")!;
  const mapping: IconMapping = {};
  SHAPES.forEach((shape, i) => {
    drawShape(ctx, shape, i * ICON_SIZE);
    mapping[shape] = { x: i * ICON_SIZE, y: 0, width: ICON_SIZE, height: ICON_SIZE, mask: true };
  });
  cached = { atlas: canvas.toDataURL("image/png"), mapping };
  return cached;
}
