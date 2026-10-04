// Shared by the instanced primitives: screen/space projection and reveal easing.
uniform vec2 u_res;
uniform float u_time;
uniform float u_fade;
uniform mat3 u_rot[4];
uniform vec4 u_ctr[4];      // x, y, scale, perspective (0 = flat)
uniform vec4 u_part[32];    // intensity, heat 0..1, selected, unused
uniform vec4 u_partoff[32]; // per-part model offset (explode), xyz

vec3 project(vec3 p, float space) {
    int s = int(space + 0.5);
    if (s == 0) return vec3(p.xy, 0.0);
    vec3 v = u_rot[s] * p;
    float k = u_ctr[s].w > 0.0 ? u_ctr[s].w / (u_ctr[s].w + v.z) : 1.0;
    return vec3(u_ctr[s].xy + v.xy * u_ctr[s].z * k, v.z);
}

vec4 to_clip(vec2 px) {
    return vec4(px.x / u_res.x * 2.0 - 1.0, 1.0 - px.y / u_res.y * 2.0, 0.0, 1.0);
}

// 0 before t0, eases to 1 over dur seconds; t0 <= 0 means "always shown".
float reveal(float t0, float dur) {
    if (t0 <= 0.0) return 1.0;
    float f = clamp((u_time - t0) / dur, 0.0, 1.0);
    return 1.0 - pow(1.0 - f, 3.0);
}

vec2 corner(int i) {   // two triangles: 0..5 -> unit quad corners
    const vec2 c[6] = vec2[6](vec2(0,0), vec2(1,0), vec2(1,1), vec2(0,0), vec2(1,1), vec2(0,1));
    return c[i];
}

// Heat ramp for part glow: phosphor -> amber -> danger.
vec3 heat(vec3 base, float h) {
    vec3 amber = vec3(0.831, 0.686, 0.216);
    vec3 danger = vec3(1.0, 0.463, 0.435);
    if (h <= 0.0) return base;
    return h < 0.5 ? mix(base, amber, h * 2.0) : mix(amber, danger, (h - 0.5) * 2.0);
}

float depth_fade(float z, float space) {
    if (space < 0.5) return 1.0;
    return mix(1.0, 0.28, smoothstep(-1.0, 1.0, z));
}
