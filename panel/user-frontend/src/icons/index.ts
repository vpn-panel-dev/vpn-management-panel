import { h } from 'vue'

export const DownloadIcon = () =>
  h(
    'svg',
    {
      viewBox: '0 0 24 24',
      fill: 'none',
      stroke: 'currentColor',
      strokeWidth: 2,
      strokeLinecap: 'round' as const,
      strokeLinejoin: 'round' as const,
    },
    [
      h('path', { d: 'M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4' }),
      h('polyline', { points: '7 10 12 15 17 10' }),
      h('line', { x1: 12, y1: 15, x2: 12, y2: 3 }),
    ],
  )

export const CopyIcon = () =>
  h(
    'svg',
    {
      viewBox: '0 0 24 24',
      fill: 'none',
      stroke: 'currentColor',
      strokeWidth: 2.2,
      strokeLinecap: 'round' as const,
      strokeLinejoin: 'round' as const,
    },
    [
      h('rect', { x: 9, y: 9, width: 13, height: 13, rx: 2 }),
      h('path', { d: 'M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1' }),
    ],
  )

export const CheckIcon = () =>
  h(
    'svg',
    {
      viewBox: '0 0 24 24',
      fill: 'none',
      stroke: 'currentColor',
      strokeWidth: 2.5,
      strokeLinecap: 'round' as const,
      strokeLinejoin: 'round' as const,
    },
    [h('polyline', { points: '20 6 9 17 4 12' })],
  )

export const QrIcon = () =>
  h('svg', { viewBox: '0 0 24 24', fill: 'currentColor' }, [
    h('path', {
      d: 'M3 3h7v7H3V3zm2 2v3h3V5H5zM14 3h7v7h-7V3zm2 2v3h3V5h-3zM3 14h7v7H3v-7zm2 2v3h3v-3H5zM16 14h2v2h-2v-2zm2 2h2v2h-2v-2zm-2 2h2v2h-2v-2zm2 2h2v-2h-2v2zm2-4h-2v2h2v-2zm-4-2h-2v2h2v-2z',
    }),
  ])

export const ShieldIcon = () =>
  h('svg', { viewBox: '0 0 24 24', fill: 'white' }, [
    h('path', {
      d: 'M12 1L3 5v6c0 5.25 3.9 10.15 9 11.35C17.1 21.15 21 16.25 21 11V5L12 1zm0 2.18 7 3.12V11c0 4.07-2.98 7.86-7 9.14C7.98 18.86 5 15.07 5 11V6.3l7-3.12z',
    }),
  ])

export const ErrorCircleIcon = () =>
  h(
    'svg',
    {
      viewBox: '0 0 24 24',
      fill: 'none',
      stroke: 'currentColor',
      strokeWidth: 2.2,
      strokeLinecap: 'round' as const,
      strokeLinejoin: 'round' as const,
    },
    [
      h('circle', { cx: 12, cy: 12, r: 10 }),
      h('line', { x1: 15, y1: 9, x2: 9, y2: 15 }),
      h('line', { x1: 9, y1: 9, x2: 15, y2: 15 }),
    ],
  )

export const InfoCircleIcon = () =>
  h(
    'svg',
    {
      viewBox: '0 0 24 24',
      fill: 'none',
      stroke: 'currentColor',
      strokeWidth: 2,
      strokeLinecap: 'round' as const,
      strokeLinejoin: 'round' as const,
    },
    [
      h('circle', { cx: 12, cy: 12, r: 10 }),
      h('line', { x1: 12, y1: 8, x2: 12, y2: 12 }),
      h('line', { x1: 12, y1: 16, x2: 12.01, y2: 16 }),
    ],
  )

export const EyeIcon = () =>
  h(
    'svg',
    {
      viewBox: '0 0 24 24',
      fill: 'none',
      stroke: 'currentColor',
      strokeWidth: 2,
      strokeLinecap: 'round' as const,
      strokeLinejoin: 'round' as const,
    },
    [h('path', { d: 'M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z' }), h('circle', { cx: 12, cy: 12, r: 3 })],
  )

export const MonitorIcon = () =>
  h(
    'svg',
    {
      viewBox: '0 0 24 24',
      fill: 'none',
      stroke: 'currentColor',
      strokeWidth: 2,
      strokeLinecap: 'round' as const,
      strokeLinejoin: 'round' as const,
    },
    [h('rect', { x: 2, y: 3, width: 20, height: 14, rx: 2 }), h('path', { d: 'M8 21h8M12 17v4' })],
  )

export const ShieldTabIcon = () =>
  h(
    'svg',
    {
      viewBox: '0 0 24 24',
      fill: 'none',
      stroke: 'currentColor',
      strokeWidth: 2,
      strokeLinecap: 'round' as const,
      strokeLinejoin: 'round' as const,
    },
    [h('path', { d: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z' })],
  )