"use client";

import { useMemo, useState } from "react";

import type { ImpactBreakdown, Issue } from "@/lib/api-client";
import {
  GH_COLORS,
  type FileHeatCell,
  buildHeatmapCells,
} from "@/lib/heatmap-data";

export type { FileHeatCell, HeatStatus } from "@/lib/heatmap-data";
export { buildHeatmapCells } from "@/lib/heatmap-data";

const ROWS = 7;
const CELL = 12;
const GAP = 3;
const MIN_COLS = 26;
const ROW_LABELS = ["py", "js", "ts", "jsx", "tsx", "·", "·"];

function topFolder(path: string): string {
  const parts = path.split("/");
  return parts.length > 1 ? parts[0] : "root";
}

function buildGrid(cells: FileHeatCell[]): (FileHeatCell | null)[][] {
  const cols = Math.max(MIN_COLS, Math.ceil(cells.length / ROWS));
  const grid: (FileHeatCell | null)[][] = Array.from({ length: cols }, () =>
    Array.from({ length: ROWS }, () => null),
  );
  cells.forEach((cell, idx) => {
    const col = Math.floor(idx / ROWS);
    const row = idx % ROWS;
    if (col < cols) grid[col][row] = cell;
  });
  return grid;
}

function buildColumnHeaders(grid: (FileHeatCell | null)[][]): { col: number; label: string }[] {
  const headers: { col: number; label: string }[] = [];
  let prev = "";
  grid.forEach((column, col) => {
    const first = column.find((c) => c !== null);
    if (!first) return;
    const folder = topFolder(first.path);
    if (folder !== prev) {
      headers.push({ col, label: folder });
      prev = folder;
    }
  });
  return headers;
}

function tooltipText(cell: FileHeatCell): string {
  const name = cell.path.split("/").pop() ?? cell.path;
  if (cell.status === "healthy") return `${name} — sorun yok (sağlıklı)`;
  const parts: string[] = [];
  if (cell.highCount) parts.push(`${cell.highCount} kritik`);
  if (cell.mediumCount) parts.push(`${cell.mediumCount} orta`);
  if (cell.lowCount) parts.push(`${cell.lowCount} düşük`);
  const kind =
    cell.status === "critical" ? "Kritik Performans / Güvenlik Hatası" : "Verimlilik Uyarısı";
  return `${cell.path} — ${parts.join(", ")} ${kind} (${cell.wasteSummary})`;
}

export function CodeHealthHeatmap({
  issues,
  impacts,
  scannedFiles,
}: {
  issues: Issue[];
  impacts: ImpactBreakdown[];
  scannedFiles?: string[];
}) {
  const cells = useMemo(
    () => buildHeatmapCells(issues, impacts, scannedFiles),
    [issues, impacts, scannedFiles],
  );
  const grid = useMemo(() => buildGrid(cells), [cells]);
  const colHeaders = useMemo(() => buildColumnHeaders(grid), [grid]);
  const cols = grid.length;

  const stats = useMemo(() => {
    const s = { healthy: 0, warning: 0, critical: 0, issues: 0 };
    for (const c of cells) {
      s[c.status] += 1;
      s.issues += c.issueCount;
    }
    return s;
  }, [cells]);

  const [hovered, setHovered] = useState<FileHeatCell | null>(null);
  const [tipPos, setTipPos] = useState({ x: 0, y: 0 });

  if (cells.length === 0) {
    return (
      <div className="text-sm text-muted italic py-4">
        Isı haritası için taranan kaynak dosya bulunamadı.
      </div>
    );
  }

  const gridWidth = cols * CELL + (cols - 1) * GAP;
  const labelCol = 28;

  return (
    <div className="relative w-full" onMouseLeave={() => setHovered(null)}>
      {/* Stats bar */}
      <div className="flex flex-wrap items-baseline justify-between gap-2 mb-4">
        <div className="flex items-center gap-3 text-sm">
          <span className="font-semibold text-foreground">{cells.length} dosya</span>
          <span className="text-muted">tarandı</span>
          <div className="flex items-center gap-1">
            <span className="inline-block h-2 w-2 rounded-sm" style={{ background: GH_COLORS.healthy }} />
            <span className="text-[var(--good)]">{stats.healthy}</span>
          </div>
          {stats.warning > 0 && (
            <div className="flex items-center gap-1">
              <span className="inline-block h-2 w-2 rounded-sm" style={{ background: GH_COLORS.warn3 }} />
              <span className="text-[var(--warn)]">{stats.warning}</span>
            </div>
          )}
          {stats.critical > 0 && (
            <div className="flex items-center gap-1">
              <span className="inline-block h-2 w-2 rounded-sm" style={{ background: GH_COLORS.critical }} />
              <span className="text-[var(--bad-hot)]">{stats.critical}</span>
            </div>
          )}
        </div>
        <span className="text-xs text-muted mono">{stats.issues} toplam bulgu</span>
      </div>

      {/* Heatmap Grid */}
      <div className="overflow-x-auto pb-1">
        <div style={{ minWidth: labelCol + gridWidth + 8 }}>
          {/* Column headers (folder names) */}
          <div
            className="relative h-4 mb-1 text-[10px] text-muted mono"
            style={{ marginLeft: labelCol }}
          >
            {colHeaders.map(({ col, label }) => (
              <span
                key={`${col}-${label}`}
                className="absolute whitespace-nowrap"
                style={{ left: col * (CELL + GAP) }}
              >
                {label}
              </span>
            ))}
          </div>

          <div className="flex gap-0">
            {/* Row labels */}
            <div
              className="flex flex-col justify-between shrink-0 text-[10px] text-muted leading-none pr-1 mono"
              style={{ width: labelCol, height: ROWS * CELL + (ROWS - 1) * GAP }}
            >
              {ROW_LABELS.map((label, row) => (
                <span key={row} className="flex items-center" style={{ height: CELL }}>
                  {label}
                </span>
              ))}
            </div>

            {/* Grid cells */}
            <div className="flex" style={{ gap: GAP }}>
              {grid.map((column, colIdx) => (
                <div key={colIdx} className="flex flex-col" style={{ gap: GAP }}>
                  {column.map((cell, rowIdx) => {
                    const bg = cell ? cell.color : GH_COLORS.empty;
                    const key = cell?.path ?? `empty-${colIdx}-${rowIdx}`;
                    if (!cell) {
                      return (
                        <span
                          key={key}
                          className="rounded-[3px] shrink-0"
                          style={{
                            width: CELL,
                            height: CELL,
                            backgroundColor: bg,
                            border: '1px solid rgba(34, 49, 77, 0.3)',
                          }}
                          aria-hidden
                        />
                      );
                    }
                    return (
                      <button
                        key={key}
                        type="button"
                        title={tooltipText(cell)}
                        aria-label={tooltipText(cell)}
                        className="heatmap-cell shrink-0 outline-none"
                        style={{
                          width: CELL,
                          height: CELL,
                          backgroundColor: bg,
                          boxShadow: cell.status === 'critical'
                            ? '0 0 6px rgba(255, 0, 85, 0.4)'
                            : cell.status === 'warning'
                            ? '0 0 4px rgba(16, 185, 129, 0.2)'
                            : 'none',
                        }}
                        onMouseEnter={(e) => {
                          setHovered(cell);
                          const r = e.currentTarget.getBoundingClientRect();
                          setTipPos({ x: r.left + r.width / 2, y: r.top });
                        }}
                        onFocus={(e) => {
                          setHovered(cell);
                          const r = e.currentTarget.getBoundingClientRect();
                          setTipPos({ x: r.left + r.width / 2, y: r.top });
                        }}
                        onBlur={() => setHovered(null)}
                      />
                    );
                  })}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Legend */}
      <div className="mt-4 flex flex-wrap items-center justify-end gap-2 text-[10px] text-muted">
        <span>Sağlıklı</span>
        <span className="inline-flex gap-[3px]">
          {[
            GH_COLORS.healthy,
            GH_COLORS.warn1,
            GH_COLORS.warn2,
            GH_COLORS.warn3,
            GH_COLORS.critical,
          ].map((color) => (
            <span
              key={color}
              className="rounded-[3px]"
              style={{
                width: CELL,
                height: CELL,
                backgroundColor: color,
                boxShadow: color === GH_COLORS.critical
                  ? '0 0 4px rgba(255, 0, 85, 0.3)'
                  : 'none',
              }}
            />
          ))}
        </span>
        <span>Kritik Risk</span>
      </div>

      {/* Glassmorphic Floating Tooltip */}
      {hovered && (
        <div
          className="fixed z-50 pointer-events-none max-w-sm tooltip-glass -translate-x-1/2 -translate-y-full"
          style={{ left: tipPos.x, top: tipPos.y - 10 }}
          role="tooltip"
        >
          {/* Status indicator line */}
          <div
            className="absolute top-0 left-3 right-3 h-px"
            style={{
              background: hovered.status === 'critical'
                ? 'linear-gradient(90deg, transparent, #FF0055, transparent)'
                : hovered.status === 'warning'
                ? 'linear-gradient(90deg, transparent, #D97706, transparent)'
                : 'linear-gradient(90deg, transparent, #10B981, transparent)',
            }}
          />

          <p className="font-semibold mono text-[11px] text-[var(--foreground)] truncate">{hovered.path}</p>

          <div className="mt-2 flex flex-wrap gap-2">
            {hovered.highCount > 0 && (
              <span className="badge-high text-[10px] px-1.5 py-0.5 rounded-md font-medium">
                {hovered.highCount} kritik
              </span>
            )}
            {hovered.mediumCount > 0 && (
              <span className="badge-medium text-[10px] px-1.5 py-0.5 rounded-md font-medium">
                {hovered.mediumCount} orta
              </span>
            )}
            {hovered.lowCount > 0 && (
              <span className="badge-low text-[10px] px-1.5 py-0.5 rounded-md font-medium">
                {hovered.lowCount} düşük
              </span>
            )}
            {hovered.status === "healthy" && (
              <span className="badge-low text-[10px] px-1.5 py-0.5 rounded-md font-medium">
                ✓ Sağlıklı
              </span>
            )}
          </div>

          <p className="mt-1.5 text-[10px] text-muted">{hovered.wasteSummary}</p>
        </div>
      )}
    </div>
  );
}
