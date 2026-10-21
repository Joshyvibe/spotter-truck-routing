/** The map's truck marker: Material "local_shipping" glyph on a white disc, drawn once. */
import type { Map as MapLibreMap } from 'maplibre-gl';

import { theme } from '../theme';

export const TRUCK_ICON = 'truck';

// Material Icons "local_shipping" (Apache 2.0), 24 × 24 viewBox.
const TRUCK_PATH =
  'M20 8h-3V4H3c-1.1 0-2 .9-2 2v11h2c0 1.66 1.34 3 3 3s3-1.34 3-3h6c0 1.66 1.34 3 3 3s3-1.34 3-3h2v-5l-3-4zM6 18.5c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5zm13.5-9 1.96 2.5H17V9.5h2.5zm-1.5 9c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5z';

const SIZE = 64; // pixels; registered at pixelRatio 2, so 32 CSS px on the map

function drawTruck(): ImageData | null {
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = SIZE;
  const ctx = canvas.getContext('2d');
  if (!ctx) return null;
  const color = theme.palette.primary.main;
  ctx.beginPath();
  ctx.arc(SIZE / 2, SIZE / 2, SIZE / 2 - 3, 0, Math.PI * 2);
  ctx.fillStyle = '#FFFFFF';
  ctx.fill();
  ctx.lineWidth = 4;
  ctx.strokeStyle = color;
  ctx.stroke();
  ctx.save();
  ctx.translate(SIZE * 0.2, SIZE * 0.2);
  ctx.scale((SIZE * 0.6) / 24, (SIZE * 0.6) / 24);
  ctx.fillStyle = color;
  ctx.fill(new Path2D(TRUCK_PATH));
  ctx.restore();
  return ctx.getImageData(0, 0, SIZE, SIZE);
}

/** Register the icon once per map (safe to call again, e.g. after a style reload). */
export function addTruckIcon(map: MapLibreMap): void {
  if (map.hasImage(TRUCK_ICON)) return;
  const img = drawTruck();
  if (img) map.addImage(TRUCK_ICON, img, { pixelRatio: 2 });
}
