import { Component, useMemo, useRef } from 'react'
import type { ReactNode, RefObject } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { AdditiveBlending, Color, DoubleSide, Group, LineBasicMaterial, MeshBasicMaterial, PointsMaterial, RGBAFormat, SpriteMaterial } from 'three'
import { coreMotion, coreStateColors, makeCoreGeometry } from './model.ts'
import type { CoreState } from './model.ts'

function Core({ level, reduced, state, dense }: { level: RefObject<number>; reduced: boolean; state: CoreState; dense: boolean }) {
  const geometry = useMemo(() => makeCoreGeometry(dense), [dense])
  const shell = useRef<Group>(null)
  const inner = useRef<Group>(null)
  const bands = useRef<Group>(null)
  const panels = useRef<MeshBasicMaterial>(null)
  const outline = useRef<LineBasicMaterial>(null)
  const glow = useRef<SpriteMaterial>(null)
  const dust = useRef<PointsMaterial>(null)
  const envelope = useRef(0)
  const rotationTime = useRef(0)
  const color = useMemo(() => new Color(coreStateColors[state]), [state])
  const tones = useMemo(() => ({
    panels: new Color(state === 'processing' ? '#c94d00' : '#198cff'),
    outline: new Color(state === 'processing' ? '#ff7800' : '#4ebdff'),
    dust: new Color(state === 'processing' ? '#ff8c23' : '#7acbff'),
    accent: new Color(state === 'processing' ? '#ff981f' : coreStateColors[state]),
    highlight: new Color(state === 'processing' ? '#ffd7a3' : coreStateColors[state]),
  }), [state])
  useFrame(({ pointer }, delta) => {
    if (!shell.current || !inner.current || !bands.current) return
    envelope.current += ((reduced ? 0 : level.current) - envelope.current) * Math.min(delta * 12, 1)
    rotationTime.current += reduced ? 0 : delta * (state === 'processing' ? 1.6 : state === 'analyzing' ? 1.25 : state === 'error' ? .4 : 1)
    const motion = coreMotion(rotationTime.current, envelope.current, reduced, state)
    const scale = shell.current.scale.x + (motion.scale - shell.current.scale.x) * Math.min(delta * 9, 1)
    shell.current.scale.setScalar(scale)
    shell.current.rotation.set(0.25 + (reduced ? 0 : pointer.y * 0.03), motion.shellY, 0.12)
    inner.current.rotation.set(0.7, motion.innerY, 0.3)
    bands.current.rotation.set(0.5, 0.35, motion.bandZ)
    for (const group of [inner.current, bands.current]) group.traverse(object => {
      if ('material' in object) {
        const material = object.material as MeshBasicMaterial
        material.color?.lerp(object.userData.coreHighlight ? tones.highlight : group === bands.current ? tones.accent : color, reduced ? 1 : Math.min(delta * 4, 1))
      }
    })
    const blend = reduced ? 1 : Math.min(delta * 4, 1)
    if (panels.current) { panels.current.opacity = motion.panels; panels.current.color.lerp(tones.panels, blend) }
    if (outline.current) outline.current.color.lerp(tones.outline, blend)
    if (glow.current) { glow.current.opacity = Math.min(1, motion.glow); glow.current.color.lerp(color, reduced ? 1 : Math.min(delta * 4, 1)) }
    if (dust.current) { dust.current.opacity = motion.dust; dust.current.color.lerp(tones.dust, blend) }
  })
  return <group ref={shell}>
    <mesh>
      <bufferGeometry><bufferAttribute attach="attributes-position" args={[geometry.panels, 3]} /></bufferGeometry>
      <meshBasicMaterial ref={panels} color="#198cff" side={DoubleSide} transparent opacity={0.16} blending={AdditiveBlending} depthWrite={false} />
    </mesh>
    <lineSegments>
      <bufferGeometry><bufferAttribute attach="attributes-position" args={[geometry.shell, 3]} /></bufferGeometry>
      <lineBasicMaterial ref={outline} color="#4ebdff" transparent opacity={0.58} blending={AdditiveBlending} depthWrite={false} />
    </lineSegments>
    <group ref={bands}>
      {[0, 1, 2].map(i => <mesh key={i} rotation={[i * 0.8 + 0.2, i * 0.55, i * 0.7]}>
        <torusGeometry args={[1.35 + i * 0.14, 0.008, 4, 144, Math.PI * (1.35 + i * 0.15)]} />
        <meshBasicMaterial color={i === 1 ? '#8ddcff' : '#238fff'} transparent opacity={0.68} blending={AdditiveBlending} depthWrite={false} />
      </mesh>)}
    </group>
    <group ref={inner}>
      <lineSegments>
        <bufferGeometry><bufferAttribute attach="attributes-position" args={[geometry.inner, 3]} /></bufferGeometry>
        <lineBasicMaterial color="#75caff" transparent opacity={0.72} blending={AdditiveBlending} depthWrite={false} />
      </lineSegments>
      <mesh rotation={[0.7, 0.2, 0.4]}>
        <icosahedronGeometry args={[0.45, 1]} />
        <meshBasicMaterial color="#68c9ff" wireframe transparent opacity={0.5} blending={AdditiveBlending} depthWrite={false} />
      </mesh>
      <mesh userData={{ coreHighlight: true }}>
        <icosahedronGeometry args={[0.16, 1]} />
        <meshBasicMaterial color="#b7eaff" transparent opacity={0.8} blending={AdditiveBlending} depthWrite={false} />
      </mesh>
    </group>
    <sprite scale={[2.2, 2.2, 1]}>
      <spriteMaterial ref={glow} color="#299fff" transparent opacity={0.65} blending={AdditiveBlending} depthWrite={false}>
        <dataTexture attach="map" args={[geometry.glow, 64, 64, RGBAFormat]} needsUpdate />
      </spriteMaterial>
    </sprite>
    <points>
      <bufferGeometry><bufferAttribute attach="attributes-position" args={[geometry.particles, 3]} /></bufferGeometry>
      <pointsMaterial ref={dust} size={0.014} color="#7acbff" transparent opacity={0.62} blending={AdditiveBlending} depthWrite={false} />
    </points>
  </group>
}

export class SceneBoundary extends Component<{ children: ReactNode; onError?: () => void }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  componentDidCatch() { this.props.onError?.() }
  render() {
    if (this.state.failed) return <div className="webgl-fallback" role="status">3D 모형 또는 그래픽 화면을 불러오지 못했습니다.<br />새로고침 후 다시 확인해 주세요.</div>
    return this.props.children
  }
}

export default function CoreScene({ level, reduced, state, dense = false }: { level: RefObject<number>; reduced: boolean; state: CoreState; dense?: boolean }) {
  return <SceneBoundary>
    {/* Measure layout size so the entrance scale does not shrink the canvas twice. */}
    <Canvas camera={{ position: [0, 0, 5.8], fov: 43 }} dpr={[1, 1.5]} resize={{ debounce: 0, offsetSize: true }}
      gl={{ alpha: true, antialias: true, powerPreference: 'high-performance' }}
      fallback={<div className="webgl-fallback">WebGL을 사용할 수 없습니다.</div>}>
      <Core level={level} reduced={reduced} state={state} dense={dense} />
    </Canvas>
  </SceneBoundary>
}
