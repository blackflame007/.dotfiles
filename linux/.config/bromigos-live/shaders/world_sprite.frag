#version 330 core
in vec2 v_uv;
in float v_y0;
in vec2 v_q;
flat in vec4 v_a1, v_a2, v_a3, v_a4;
out vec4 o;
uniform sampler2D u_atlas;
uniform vec4 u_grade;
uniform float u_flash;
uniform vec3 u_lift;
uniform float u_time;
uniform vec3 u_water;             // the water's colour, for what is under the surface
uniform vec4 u_fog;               // surface y px, fog distance px, on, how much of it reaches actors
uniform vec3 u_fogcol;
void main() {
    vec2 uv = v_uv;
    bool refl = v_a2.w > 0.5;
    if (refl) uv.x += sin(v_y0 * 0.09 + u_time * 1.7) * 0.012 * (v_a1.z - v_a1.x);
    uv = clamp(uv, min(v_a1.xy, v_a1.zw), max(v_a1.xy, v_a1.zw));
    vec4 s = texture(u_atlas, uv);
    bool emissive = v_a4.w > 0.5;                    // an emissive mask: light, not lit by the hour
    vec3 c = emissive ? v_a3.rgb * s.a * v_a4.z
                      : (mix(s.rgb, v_a3.rgb * dot(s.rgb, vec3(0.3, 0.59, 0.11)) * 1.7, v_a3.a) * u_grade.rgb + u_lift * s.a)
                        * v_a4.z * (1.0 + u_flash);     // a tint keeps the art's light and shade (glow loops on black too)
    float m = v_a2.y;                                // the instance's alpha (premultiplied art)
    if (v_a2.z > 0.0) {
        float under = v_y0 - v_a2.z;                 // > 0 below the water line
        if (refl) {
            m *= smoothstep(1.5, -1.5, under) * v_a4.x * exp(-max(-under, 0.0) / 160.0);
            c *= 0.6;
        } else {
            float sub = smoothstep(-1.0, 3.0, under);
            c = mix(c, u_water * s.a, sub * 0.8);
            m *= mix(1.0, 0.12, sub);
        }
    }
    if (v_a4.y > 0.5 && u_fog.z > 0.5) {
        float f = 1.0 - exp(-max(v_y0 - u_fog.x, 0.0) / u_fog.y);
        c = mix(c, u_fogcol * s.a, f * u_fog.w);
    }
    o = vec4(c * m, s.a * m);
}
