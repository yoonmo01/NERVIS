import { Suspense, useCallback, useMemo, useRef, useEffect, useState } from 'react'
import { Canvas } from '@react-three/fiber'
import { createPortal } from 'react-dom'
import SchematicBrain, { BrainBloom, BrainOrbit, clearBrainModel } from './SchematicBrain.tsx'
import { displayColor, maskBoundary } from './brainVisual.ts'
import { SceneBoundary } from '../../components/CoreScene.tsx'
import type { SlicePlane, StageData } from './stageData.ts'
import { signalStrength } from './analysisModel.ts'
import { cameraPresets } from './hologramModel.ts'
import type { CameraView } from './hologramModel.ts'
import type { Region } from './api.ts'
import { maskOverlay } from '../../components/model.ts'

export function SliceCanvas({ plane, region, regions, label, values = [] }: { plane: SlicePlane; region?: number; regions: Region[]; label: string; values?: number[] }) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const overlays = useMemo(() => regions.map(item => {
    const w = plane.t1.naturalWidth, h = plane.t1.naturalHeight, color = displayColor(item)
    return [maskOverlay(plane.maskPixels, new Map([[item.label_id, color]])), maskBoundary(plane.maskPixels, w, h, item.label_id, color)].map(rgba => {
      const layer = document.createElement('canvas'); layer.width = w; layer.height = h
      layer.getContext('2d')?.putImageData(new ImageData(rgba, w, h), 0, 0)
      return layer
    })
  }), [plane, regions])
  useEffect(() => {
    const target = canvas.current, context = target?.getContext('2d')
    if (!target || !context) return
    const bounds = region === 0 ? plane.cloud.boundsA : region === 1 ? plane.cloud.boundsB : null
    if (region !== undefined && !bounds) { context.clearRect(0, 0, target.width, target.height); return }
    const padding = 38, w = plane.t1.naturalWidth, h = plane.t1.naturalHeight
    const x = bounds ? Math.max(0, bounds.x - padding) : 0, y = bounds ? Math.max(0, bounds.y - padding) : 0
    const width = bounds ? Math.min(w - x, bounds.width + padding * 2) : w, height = bounds ? Math.min(h - y, bounds.height + padding * 2) : h
    target.width = width; target.height = height
    context.drawImage(plane.t1, x, y, width, height, 0, 0, width, height)
    for (const column of region === undefined ? regions.map((_, i) => i) : [region]) {
      context.globalAlpha = .65 + signalStrength(values[column] ?? 0) * .35
      context.drawImage(overlays[column][0], x, y, width, height, 0, 0, width, height)
      context.globalAlpha = 1; context.shadowColor = `rgb(${displayColor(regions[column]).join(',')})`; context.shadowBlur = 6
      context.drawImage(overlays[column][1], x, y, width, height, 0, 0, width, height)
      context.shadowBlur = 0
    }
  }, [plane, region, regions, overlays, values])
  return <canvas ref={canvas} role="img" aria-label={label} />
}

export default function BrainStage({ data, sample, active, reduced, onReady: reportReady, onError, toolbarTarget }: {
  data: StageData; sample: number; active: boolean; reduced: boolean; onReady: () => void; onError: () => void; toolbarTarget: HTMLDivElement | null;
}) {
  const regionIds = data.comparison.regions.map(region => region.label_id)
  const selectionKey = regionIds.join(',')
  const suggestedView = 'oblique' as const
  const [view, setView] = useState<CameraView>(suggestedView), [revision, setRevision] = useState(0), [manual, setManual] = useState(false), [ready, setReady] = useState(false)
  const onManual = useCallback(() => setManual(true), [])
  const onHome = useCallback(() => { setView('oblique'); setManual(false); setRevision(value => value + 1) }, [])
  const [settled, setSettled] = useState(false)
  useEffect(() => {
    setView(suggestedView); setManual(false); setSettled(false); setRevision(value => value + 1)
  }, [selectionKey, suggestedView])
  const onSettled = useCallback(() => setSettled(true), [])
  const onReady = useCallback(() => setReady(true), [])
  useEffect(() => { if (ready && settled) reportReady() }, [ready, settled, reportReady])
  // Failed useLoader entries persist; clear them so an explicit retry can reload.
  const failed = useCallback(() => { clearBrainModel(); onError() }, [onError])
  return <div className="spatial-stage" role="group" aria-label="회전 가능한 일반 뇌 모형 · 선택 영역은 개략 위치" aria-busy={!ready}>
    <div className="scan-reticle" aria-hidden="true" />
    <SceneBoundary onError={failed}><Canvas orthographic camera={{ position: [...cameraPresets.oblique.position], zoom: 100, near: .1, far: 100 }} dpr={[1, 1.5]} frameloop={active ? 'always' : 'demand'}
      resize={{ debounce: 0, offsetSize: true }} gl={{ alpha: true, antialias: true }}>
      <BrainOrbit view={view} revision={revision} active={active} reduced={reduced} onManual={onManual} onHome={onHome} onSettled={onSettled} />
      <BrainBloom />
      <Suspense fallback={null}><SchematicBrain data={data} sample={sample} onReady={onReady} /></Suspense>
    </Canvas>
    {!ready && <span className="brain-loading" role="status">3D 모형 준비 중</span>}
    </SceneBoundary>
    {toolbarTarget && createPortal(<div className="brain-orbit-tools"><span>드래그 회전 · Q/E 기울기 · 휠 확대</span><div role="group" aria-label="뇌 시점">{(Object.keys(cameraPresets) as CameraView[]).map(key => <button key={key} aria-pressed={!manual && view === key} onClick={() => { setView(key); setManual(false); setRevision(value => value + 1) }}>{cameraPresets[key].label}</button>)}</div></div>, toolbarTarget)}
  </div>
}
