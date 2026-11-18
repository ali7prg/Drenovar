// Shared constants derived from the delivered modules (never redefined independently).
import {access, fog} from './vendor.mjs';

export const MIN_HALL_LEVEL_EXPORT = access.MIN_HALL_LEVEL; // 3, from adventure-access.mjs
export const FOG_GRID = Object.freeze({
  columns: fog.FOG_SPEC.columns,
  rows: fog.FOG_SPEC.rows,
  cellSize: fog.FOG_SPEC.cellSize,
  origin: Object.freeze({x: fog.FOG_SPEC.minX, z: fog.FOG_SPEC.minZ}),
});
