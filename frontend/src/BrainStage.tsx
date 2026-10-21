import { useMemo, useRef, useEffect } from 'react'
import type { CSSProperties } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { AdditiveBlending, Group, PointsMaterial } from 'three'
import { SceneBoundary } from './CoreScene.tsx'
import type { SlicePlane, StageData } from './stageData.ts'
import { signalStrength } from './analysisModel.ts'
import { regionLabel } from './api.ts'
import type { Region } from './api.ts'
import { maskOverlay } from './model.ts'

function Clouds({ data, sample, reduced, onRegion }: { data: StageData; sample: number; reduced: boolean; onRegion: (id: number) => void }) {
  const group = useRef<Group>(null)
  const a = useRef<PointsMaterial>(null), b = useRef<PointsMaterial>(null)
  const centerIndex = data.planes.indexOf(data.center)
  const centroids = [data.center.cloud.centerA, data.center.cloud.centerB]
  const relation = useMemo(() => {
    const [x, y] = centroids
    if (!x || !y) return new Float32Array()
    const points: number[] = []
    for (let i = 0; i < 40; i++) for (const t of [i / 40, (i + 1) / 40]) {
      points.push(x[0] * (1 - t) + y[0] * t, x[1] * (1 - t) + y[1] * t + Math.sin(t * Math.PI) * .65, .15 + Math.sin(t * Math.PI) * .3)
    }
    return new Float32Array(points)
  }, [data])
  useFrame(({ clock }) => {
    if (group.current) group.current.rotation.set(-.12, reduced ? -.18 : -.18 + Math.sin(clock.elapsedTime * .16) * .12, .025)
    const values = data.comparison.zscore[sample - 1] ?? [0, 0]
    if (a.current) a.current.opacity = .4 + signalStrength(values[0]) * .55
    if (b.current) b.current.opacity = .4 + signalStrength(values[1]) * .55
  })
  return <group ref={group} scale={1.5}>
    {data.planes.map((plane, index) => <group key={plane.record.slice_index} position={[0, 0, (index - centerIndex) * .33]}>
      <points>
        <bufferGeometry><bufferAttribute attach="attributes-position" args={[plane.cloud.tissue, 3]} /><bufferAttribute attach="attributes-color" args={[plane.cloud.colors, 3]} /></bufferGeometry>
        <pointsMaterial size={.018} vertexColors transparent opacity={index === centerIndex ? .62 : .22} depthWrite={false} blending={AdditiveBlending} />
      </points>
      {[plane.cloud.regionA, plane.cloud.regionB].map((points, column) => <points key={column}>
        <bufferGeometry><bufferAttribute attach="attributes-position" args={[points, 3]} /></bufferGeometry>
        <pointsMaterial ref={index === centerIndex ? column ? b : a : undefined} size={index === centerIndex ? .027 : .017}
          color={`rgb(${data.comparison.regions[column].color_rgb.join(',')})`} transparent opacity={index === centerIndex ? .75 : .3} depthWrite={false} blending={AdditiveBlending} />
      </points>)}
    </group>)}
    {!!relation.length && <lineSegments>
      <bufferGeometry><bufferAttribute attach="attributes-position" args={[relation, 3]} /></bufferGeometry>
      <lineBasicMaterial color="#9ddcf2" transparent opacity={.6} depthWrite={false} />
    </lineSegments>}
    {centroids.map((point, column) => point && <mesh key={column} position={[point[0], point[1], .18]} onClick={event => { event.stopPropagation(); onRegion(column) }}>
      <sphereGeometry args={[.055, 12, 8]} /><meshBasicMaterial color={`rgb(${data.comparison.regions[column].color_rgb.join(',')})`} />
    </mesh>)}
  </group>
}

export function SliceCanvas({ plane, region, regions, label }: { plane: SlicePlane; region?: number; regions: Region[]; label: string }) {
  const canvas = useRef<HTMLCanvasElement>(null)
  useEffect(() => {
    const target = canvas.current
    if (!target) return
    const context = target.getContext('2d')
    if (!context) return
    const bounds = region === 0 ? plane.cloud.boundsA : region === 1 ? plane.cloud.boundsB : null
    if (region !== undefined && !bounds) { context.clearRect(0, 0, target.width, target.height); return }
    const padding = 38, w = plane.t1.naturalWidth, h = plane.t1.naturalHeight
    const x = bounds ? Math.max(0, bounds.x - padding) : 0, y = bounds ? Math.max(0, bounds.y - padding) : 0
    const width = bounds ? Math.min(w - x, bounds.width + padding * 2) : w, height = bounds ? Math.min(h - y, bounds.height + padding * 2) : h
    target.width = width; target.height = height
    context.drawImage(plane.t1, x, y, width, height, 0, 0, width, height)
    const overlay = document.createElement('canvas'); overlay.width = w; overlay.height = h
    const overlayContext = overlay.getContext('2d')
    if (!overlayContext) return
    const selected = region === undefined ? [0, 1] : [region]
    const rgba = maskOverlay(plane.maskPixels, new Map(selected.map(column => [regions[column].label_id, regions[column].color_rgb])))
    overlayContext.putImageData(new ImageData(rgba, w, h), 0, 0)
    context.drawImage(overlay, x, y, width, height, 0, 0, width, height)
  }, [plane, region, regions])
  return <canvas ref={canvas} role="img" aria-label={label} />
}

export default function BrainStage({ data, sample, active, reduced, onRegion }: {
  data: StageData; sample: number; active: boolean; reduced: boolean; onRegion: (id: number) => void;
}) {
  return <div className="spatial-stage" role="group" aria-label="실제 제공 MRI 단면의 입자 기반 공간 표현">
    <div className="scan-reticle" aria-hidden="true" />
    <SceneBoundary><Canvas camera={{ position: [0, .05, 5.6], fov: 45 }} dpr={[1, 1.5]} frameloop={active ? 'always' : 'never'}
      resize={{ debounce: 0, offsetSize: true }} gl={{ alpha: true, antialias: true }}>
      <Clouds data={data} sample={sample} reduced={reduced} onRegion={onRegion} />
    </Canvas></SceneBoundary>
    <div className="stage-region-labels">{data.comparison.regions.map((region, column) => <button key={region.label_id} onClick={() => onRegion(column)} style={{ '--roi-color': `rgb(${region.color_rgb.join(',')})` } as CSSProperties}>
      <i />{regionLabel(region)}<span>상세 ↗</span>
    </button>)}</div>
  </div>
}
