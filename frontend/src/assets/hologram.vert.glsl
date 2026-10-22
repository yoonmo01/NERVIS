// Three.js ShaderMaterial reference. GLTFLoader lowercases custom attribute names.
attribute float _nervis_ridge;
attribute float _nervis_edge;
attribute float _nervis_context;
attribute float _nervis_micro;
varying float holoMicro;
varying vec3 holoNormal;
varying vec3 holoView;
varying vec3 holoMasks;
void main() {
  vec4 p = modelViewMatrix * vec4(position, 1.0);
  holoNormal = normalize(normalMatrix * normal);
  holoView = isOrthographic ? vec3(0.0, 0.0, 1.0) : -p.xyz;
  holoMasks = vec3(_nervis_ridge, _nervis_edge, _nervis_context);
  holoMicro = _nervis_micro;
  gl_Position = projectionMatrix * p;
}
