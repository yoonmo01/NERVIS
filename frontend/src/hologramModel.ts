import { Quaternion, Vector3 } from 'three'

export const cameraPresets = {
  default: { label: '기본 사선', position: [0, 3.2, 7.333], up: [0, 1, 0] },
  top: { label: '위', position: [0, 8, 0], up: [0, 0, -1] },
  front: { label: '앞', position: [0, 0, 8], up: [0, 1, 0] },
  back: { label: '뒤', position: [0, 0, -8], up: [0, 1, 0] },
  left: { label: '좌측', position: [8, 0, 0], up: [0, 1, 0] },
  right: { label: '우측', position: [-8, 0, 0], up: [0, 1, 0] },
} as const
export type CameraView = keyof typeof cameraPresets

export function cameraPoseBetween(from: readonly number[], to: readonly number[], t: number, fromUp: readonly number[] = [0, 1, 0], toUp: readonly number[] = [0, 1, 0]) {
  const a = new Vector3().fromArray(from), b = new Vector3().fromArray(to)
  if (!a.toArray().concat(b.toArray(), t, ...fromUp, ...toUp).every(Number.isFinite) || !a.lengthSq() || !b.lengthSq() || t < 0 || t > 1) throw new Error('Invalid camera pose')
  const radius = a.length() * (1 - t) + b.length() * t
  a.normalize(); b.normalize()
  const projectUp = (values: readonly number[], direction: Vector3) => {
    const up = new Vector3().fromArray(values).projectOnPlane(direction)
    if (up.lengthSq() < 1e-12) throw new Error('Camera up must not be parallel to its position')
    return up.normalize()
  }
  const startUp = projectUp(fromUp, a), targetUp = projectUp(toUp, b)
  const arc = new Quaternion().setFromUnitVectors(a, b)
  const partial = new Quaternion().slerpQuaternions(new Quaternion(), arc, t)
  const direction = a.clone().applyQuaternion(partial)
  const endUp = startUp.clone().applyQuaternion(arc)
  const roll = Math.atan2(b.dot(endUp.clone().cross(targetUp)), endUp.dot(targetUp))
  const up = startUp.applyQuaternion(partial).applyAxisAngle(direction, roll * t)
  return { position: direction.multiplyScalar(radius), up }

}

export function sampleSurfacePoints(positions: ArrayLike<number>, count: number) {
  if (!positions.length || positions.length % 3 || !Number.isInteger(count) || count < 0 ||
    !Array.from(positions).every(Number.isFinite)) throw new Error('유효한 모형 표면이 필요합니다.')
  const output = new Float32Array(count * 3)
  let seed = 8271
  for (let i = 0; i < count; i++) {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0
    const at = Math.floor(seed / 4294967296 * (positions.length / 3)) * 3
    output.set([positions[at], positions[at + 1], positions[at + 2]], i * 3)
  }
  return output
}
