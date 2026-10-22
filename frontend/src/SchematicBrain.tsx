import { useEffect, useMemo, useRef, useState } from 'react'
import { useFrame, useLoader, useThree } from '@react-three/fiber'
import { AdditiveBlending, BufferAttribute, BufferGeometry, Color, DoubleSide, Mesh, OrthographicCamera, ShaderMaterial, Vector2, Vector3 } from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js'
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js'
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js'
import { OutputPass } from 'three/examples/jsm/postprocessing/OutputPass.js'
import brainUrl from './assets/nervis-hologram-brain.glb?url'
import vertex from './assets/hologram.vert.glsl?raw'
import fragment from './assets/hologram.frag.glsl?raw'
import contract from './assets/hologram-render-contract.json'
import regionMap from './assets/hologram-region-map.json'
import type { StageData } from './stageData.ts'
import { signalStrength } from './analysisModel.ts'
import { cameraPoseBetween, cameraPresets, sampleSurfacePoints } from './hologramModel.ts'

import type { CameraView } from './hologramModel.ts'

const pointVertex = `uniform float size; void main(){vec4 p=modelViewMatrix*vec4(position,1.); gl_Position=projectionMatrix*p; gl_PointSize=clamp(isOrthographic?size:size*5./-p.z,.6,4.);}`
const pointFragment = `uniform vec3 tint; uniform float strength; void main(){float r=length(gl_PointCoord-.5)*2.; if(r>1.)discard; gl_FragColor=vec4(tint*strength,pow(1.-r,1.7)*.25);}`

function Surface({ geometry, id, value }: { geometry: BufferGeometry; id?: number; value: number }) {
  const surface = useRef<ShaderMaterial>(null), dust = useRef<ShaderMaterial>(null)
  const selected = id !== undefined
  const color = selected ? id <= 10 ? contract.colors_linear.left : contract.colors_linear.right : contract.colors_linear.cortex
  const uniforms = useMemo(() => ({ tint: { value: new Color(...color as [number, number, number]) }, strength: { value: 0 }, selected: { value: selected ? 1 : 0 } }), [color, selected])
  const pointUniforms = useMemo(() => ({ tint: { value: new Color(...(selected ? color : [.5, .78, 1]) as [number, number, number]) }, strength: { value: selected ? 1.1 : 2.5 }, size: { value: selected ? 1.2 : .85 } }), [color, selected])
  const particles = useMemo(() => {
    const positions = geometry.getAttribute('position')
    const points = sampleSurfacePoints(positions.array, selected ? 1800 : 8500)
    const result = new BufferGeometry(); result.setAttribute('position', new BufferAttribute(points, 3)); return result
  }, [geometry, selected])
  useEffect(() => () => particles.dispose(), [particles])
  useFrame(() => {
    const strength = signalStrength(value)
    if (surface.current) surface.current.uniforms.strength.value = strength
    if (dust.current) dust.current.uniforms.strength.value = selected ? 1.1 + 2 * strength : 2.5
  })
  return <group>
    <mesh geometry={geometry} renderOrder={selected ? 1 : 0}>
      <shaderMaterial ref={surface} vertexShader={vertex} fragmentShader={fragment} uniforms={uniforms} transparent side={DoubleSide} depthWrite={false} depthTest />
    </mesh>
    <points geometry={particles} renderOrder={2}>
      <shaderMaterial ref={dust} vertexShader={pointVertex} fragmentShader={pointFragment} uniforms={pointUniforms} transparent depthWrite={false} depthTest blending={AdditiveBlending} />
    </points>
  </group>
}

export function BrainBloom() {
  const { gl, scene, camera, size, viewport } = useThree()
  const composer = useMemo(() => {
    const result = new EffectComposer(gl)
    result.addPass(new RenderPass(scene, camera))
    result.addPass(new UnrealBloomPass(new Vector2(1, 1), .28, .35, 1))
    result.addPass(new OutputPass())
    return result
  }, [gl, scene, camera])
  useEffect(() => { composer.setPixelRatio(viewport.dpr); composer.setSize(size.width, size.height) }, [composer, size.width, size.height, viewport.dpr])
  useEffect(() => () => { composer.passes.forEach(pass => pass.dispose()); composer.dispose() }, [composer])
  useFrame((_, delta) => composer.render(delta), 1)
  return null
}

export function BrainOrbit({ view, revision, active, reduced, onManual, onHome, onSettled }: { view: CameraView; revision: number; active: boolean; reduced: boolean; onManual: () => void; onHome: () => void; onSettled: () => void }) {
  const { camera, gl, invalidate, size } = useThree()
  const [orbitFrame, setOrbitFrame] = useState(0)
  const orbit = useRef<OrbitControls | null>(null), fit = useRef(100)
  const transition = useRef<{ from: number[]; up: number[]; zoom: number; elapsed: number } | null>(null)
  useEffect(() => {
    const controls = new OrbitControls(camera, gl.domElement); orbit.current = controls
    controls.enablePan = false; controls.minDistance = 3; controls.maxDistance = 16
    const changed = () => invalidate()
    const manual = () => { transition.current = null; onManual() }
    controls.addEventListener('change', changed); controls.addEventListener('start', manual)
    gl.domElement.tabIndex = 0; gl.domElement.setAttribute('aria-label', '3D 뇌 회전: 방향키, 확대: +와 -, 초기화: Home')
    const keyboard = (event: KeyboardEvent) => {
      if (!controls.enabled || !['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', '+', '-', 'Home'].includes(event.key)) return
      event.preventDefault(); manual()
      if (event.key === 'Home') { onHome(); return
      } else if ((event.key === '+' || event.key === '-') && camera instanceof OrthographicCamera) {
        camera.zoom = Math.max(controls.minZoom, Math.min(controls.maxZoom, camera.zoom * (event.key === '+' ? 1.1 : .9)))
      } else {
        const axis = event.key === 'ArrowLeft' || event.key === 'ArrowRight' ? camera.up : new Vector3(1, 0, 0).applyQuaternion(camera.quaternion)
        camera.position.applyAxisAngle(axis, event.key === 'ArrowLeft' || event.key === 'ArrowUp' ? .12 : -.12)
      }
      camera.updateProjectionMatrix(); controls.update(); invalidate()
    }
    gl.domElement.addEventListener('keydown', keyboard)
    return () => { controls.removeEventListener('change', changed); controls.removeEventListener('start', manual); gl.domElement.removeEventListener('keydown', keyboard); controls.dispose(); orbit.current = null }
  }, [camera, gl, invalidate, onManual, onHome, orbitFrame])
  useEffect(() => {
    if (camera instanceof OrthographicCamera) {
      const next = size.height / contract.camera.vertical_span
      camera.zoom *= next / fit.current; fit.current = next; camera.updateProjectionMatrix()
      if (orbit.current) { orbit.current.minZoom = next * .45; orbit.current.maxZoom = next * 2.5 }
      invalidate()
    }
  }, [camera, size.height, invalidate, orbitFrame])
  useEffect(() => {
    if (orbit.current) orbit.current.enabled = false
    transition.current = { from: camera.position.toArray(), up: camera.up.toArray(), zoom: camera instanceof OrthographicCamera ? camera.zoom : 1, elapsed: reduced ? .9 : 0 }
    invalidate()
  }, [camera, view, revision, reduced, invalidate])
  useEffect(() => { if (orbit.current) orbit.current.enabled = active && !transition.current }, [active, orbitFrame])
  useFrame((_, delta) => {
    const move = transition.current
    if (!move || !active) return
    move.elapsed += Math.min(delta, .1)
    const t = Math.min(1, move.elapsed / .9), eased = t * t * (3 - 2 * t), target = cameraPresets[view]
    const pose = cameraPoseBetween(move.from, target.position, eased, move.up, target.up)
    camera.position.copy(pose.position); camera.up.copy(pose.up)
    if (camera instanceof OrthographicCamera) { camera.zoom = move.zoom + (fit.current - move.zoom) * eased; camera.updateProjectionMatrix() }
    orbit.current?.update(); invalidate()
    if (t === 1) {
      transition.current = null
      // OrbitControls caches camera.up when constructed; rebuild after a preset changes it.
      setOrbitFrame(value => value + 1)
      onSettled()
    }
  })
  return null
}

export function clearBrainModel() { useLoader.clear(GLTFLoader, brainUrl) }

export default function SchematicBrain({ data, sample, onReady }: { data: StageData; sample: number; onReady: () => void }) {
  const gltf = useLoader(GLTFLoader, brainUrl)
  const meshes = useMemo(() => {
    const output: { name: string; id?: number; geometry: BufferGeometry }[] = []
    gltf.scene.updateMatrixWorld(true)
    gltf.scene.traverse(object => {
      if (object instanceof Mesh) output.push({ name: object.name, id: object.userData.label_id, geometry: object.geometry.clone().applyMatrix4(object.matrixWorld) })
    })
    const invalid = output.length !== 22 || regionMap.regions.some(region => !output.some(mesh => mesh.id === region.label_id && region.glb_nodes.includes(mesh.name))) ||
      output.some(mesh => ['_nervis_ridge', '_nervis_edge', '_nervis_context', '_nervis_micro'].some(name => !mesh.geometry.getAttribute(name)))
    if (invalid) { output.forEach(mesh => mesh.geometry.dispose()); throw new Error('홀로그램 모형의 영역·표면 속성을 확인할 수 없습니다.') }
    return output
  }, [gltf])
  useEffect(() => { onReady(); return () => meshes.forEach(mesh => mesh.geometry.dispose()) }, [meshes, onReady])
  return <group>{meshes.map(mesh => {
    const column = data.comparison.regions.findIndex(region => region.label_id === mesh.id)
    if (mesh.id && column < 0) return null
    return <Surface key={mesh.name} geometry={mesh.geometry} id={mesh.id} value={data.comparison.zscore[sample - data.comparison.samples[0]]?.[column] ?? 0} />
  })}</group>
}
