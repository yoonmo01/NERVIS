// Porting reference, not a browser-validated implementation. Linear RGB uniforms.
// selected=0 for cortex, 1 for a selected ROI. Unselected ROI meshes must be hidden.
uniform vec3 tint;
uniform float selected;
uniform float strength;
varying vec3 holoNormal;
varying vec3 holoView;
varying vec3 holoMasks;
varying float holoMicro;
void main() {
  vec3 n = normalize(holoNormal);
  float rim = pow(1.0 - abs(dot(n, normalize(holoView))), 2.25);
  float ridge = clamp(holoMasks.x, 0.0, 1.0);
  float edge = clamp(holoMasks.y, 0.0, 1.0);
  float border = pow(1.0 - edge, 2.0);
  float pattern = 1.7 * rim + .22 * ridge + selected * .9 * border;
  vec3 edgeColor = mix(vec3(.65, .88, 1.0), min(vec3(1.0), tint * .3 + .5), selected);
  vec3 color = mix(tint, edgeColor, rim * .65);
  float gain = mix(1.0, .8 + 1.2 * clamp(strength, 0.0, 1.0), selected);
  float emission = (mix(.10, .45, selected) + pattern * mix(2.2, 2.6, selected)) * gain;
  emission *= .48 + 1.45 * clamp(holoMicro, 0.0, 1.0);
  float alpha = mix(.018, .10, selected) + pattern * mix(.22, .26, selected);
  alpha *= mix(1.0, .2 + .8 * edge, selected);
  alpha *= gl_FrontFacing ? 1.0 : mix(.35, .55, selected);
  alpha *= mix(clamp(holoMasks.z, 0.0, 1.0), 1.0, selected);
  alpha *= .8 + .65 * clamp(holoMicro, 0.0, 1.0);
  float diffuse = .15 + .85 * max(0.0, dot(n, normalize(vec3(.4, .6, 1.0))));
  gl_FragColor = vec4(color * emission * mix(.90, .84, selected) + tint * diffuse * mix(.10, .16, selected), clamp(alpha, 0.0, 1.0));
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}
