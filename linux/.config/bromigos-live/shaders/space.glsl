// The Drift, procedurally: parallax stars, ship lanes and debris (density from
// real network traffic), a wireframe gas giant whose terminator follows local
// time of day, and the relay beam that runs only while the lab is all green.
// Needs rain.glsl (palette, hashes, seg_dist) included first.

uniform vec4 u_space;        // stars on, smoothed traffic level 0..1 (<0 = traffic off), beam on, health (0 ok, 1 amber, 2 red)
uniform vec4 u_lane[7];      // per lane, from live/traffic.py: x px along the lane, busy (decided per crossing), -, -
uniform vec4 u_space_rect;   // sky region x y w h (px)
uniform vec4 u_planet;       // cx, cy, R, on
uniform vec4 u_sun;          // sun angle (rad, from local time), spin, tilt, -
uniform vec4 u_beam;         // x0, y0, angle (rad, screen), pulse speed

vec3 health_tint(vec3 c) {
    if (u_space.w < 0.5) return c;
    vec3 t = u_space.w < 1.5 ? AMBER : DANGER;
    float l = max(c.r, max(c.g, c.b));
    return mix(c, t * l, 0.55);
}

float stars(vec2 px) {
    float acc = 0.0;
    for (int k = 0; k < 3; k++) {
        float sc = 7.0 + float(k) * 9.0;                 // cell size: far layers denser
        float cell = 40.0 + float(k) * 34.0;
        vec2 drift = vec2(u_time * (0.6 + float(k) * 1.4), u_time * 0.15 * float(k));
        vec2 q = (px + drift) / cell;
        vec2 ci = floor(q);
        float h = hash2(ci + float(k) * 17.3);
        if (h < 0.55) continue;
        vec2 sp = (ci + vec2(hash2(ci + 3.1), hash2(ci + 7.7))) * cell - drift;
        float d = length(px - sp);
        float mag = (h - 0.55) / 0.45;
        float tw = 0.75 + 0.25 * sin(u_time * (1.0 + hash2(ci) * 3.0) + h * 40.0);
        float sz = 0.6 + float(k) * 0.35 + mag * 0.5;
        acc += exp(-d * d / (sz * sz)) * (0.25 + 0.75 * mag) * tw * (0.45 + 0.3 * float(k));
        sc += 0.0;
    }
    return acc;
}

// one small wireframe hauler, nose to +x, in a 44x14 px box
float ship_dist(vec2 p, float kind) {
    float d = 1e3;
    d = min(d, seg_dist(p, vec2(-22.0, 0.0), vec2(16.0, 0.0)));
    d = min(d, seg_dist(p, vec2(16.0, 0.0), vec2(22.0, 0.0)));
    d = min(d, seg_dist(p, vec2(-22.0, -5.0), vec2(8.0, -5.0)));
    d = min(d, seg_dist(p, vec2(-22.0, 5.0), vec2(8.0, 5.0)));
    d = min(d, seg_dist(p, vec2(8.0, -5.0), vec2(16.0, 0.0)));
    d = min(d, seg_dist(p, vec2(8.0, 5.0), vec2(16.0, 0.0)));
    d = min(d, seg_dist(p, vec2(-22.0, -5.0), vec2(-22.0, 5.0)));
    if (kind > 0.5) {                                   // container ribs
        d = min(d, seg_dist(p, vec2(-12.0, -5.0), vec2(-12.0, 5.0)));
        d = min(d, seg_dist(p, vec2(-2.0, -5.0), vec2(-2.0, 5.0)));
    } else {                                            // fins
        d = min(d, seg_dist(p, vec2(-16.0, -5.0), vec2(-20.0, -10.0)));
        d = min(d, seg_dist(p, vec2(-16.0, 5.0), vec2(-20.0, 10.0)));
    }
    return d;
}

vec3 traffic(vec2 px) {
    vec4 r = u_space_rect;
    if (px.x < r.x || px.y < r.y || px.x > r.x + r.z || px.y > r.y + r.w) return vec3(0.0);
    vec3 acc = vec3(0.0);
    float lvl = u_space.y;
    if (lvl < 0.0) return acc;
    for (int k = 0; k < 7; k++) {
        float fk = float(k);
        float ly = r.y + r.w * (0.08 + 0.84 * hash1(fk * 7.13 + 1.0));
        if (abs(px.y - ly) > 16.0) continue;
        // position and occupancy come from the CPU (live/traffic.py): a lane's ship is decided
        // once per crossing and runs edge to edge, so it never pops in or out mid-screen
        if (u_lane[k].y < 0.5) continue;
        float dir = hash1(fk * 5.1) > 0.5 ? 1.0 : -1.0;
        float x = u_lane[k].x;
        float sx = dir > 0.0 ? r.x + x : r.x + r.z - x;
        float sc = 0.7 + 0.5 * hash1(fk * 2.3);
        vec2 p = (px - vec2(sx, ly)) / sc;
        p.x *= dir;
        float d = ship_dist(p, step(0.5, hash1(fk * 9.9)));
        float line = clamp(1.0 - d * sc, 0.0, 1.0);
        float eng = exp(-dot(p + vec2(25.0, 0.0), p + vec2(25.0, 0.0)) / 6.0)
                  * smoothstep(0.0, 40.0, min(x, r.z - x) + 22.0);   // the engine glow comes up over the first 40 px
        float trail = (p.x < -22.0 && abs(p.y) < 1.5) ? exp((p.x + 22.0) / 40.0) * 0.25 : 0.0;
        float blink = step(0.85, fract(u_time * 0.9 + fk * 0.3)) * exp(-dot(p - vec2(22.0, 0.0), p - vec2(22.0, 0.0)) / 2.0);
        acc += SOFT * line * 0.65 + AMBER * (eng * 0.9 + trail) + DANGER * blink * 1.2;
    }
    // debris: slow tumbling flecks, density from traffic
    vec2 q = (px + vec2(u_time * 9.0, -u_time * 3.0)) / 26.0;
    vec2 ci = floor(q);
    float h = hash2(ci * 1.31 + 5.0);
    float th = 0.06 + 0.22 * lvl;                    // lvl is a ~25 s average: flecks fade, never blink
    float keep = 1.0 - smoothstep(th - 0.025, th, h);
    if (keep > 0.0) {
        vec2 c0 = (ci + 0.5) * 26.0 - vec2(u_time * 9.0, -u_time * 3.0);
        float a = u_time * (0.5 + h * 6.0) + h * 30.0;
        vec2 dv = vec2(cos(a), sin(a)) * 2.5;
        float d = seg_dist(px, c0 - dv, c0 + dv);
        acc += DIM * clamp(1.0 - d, 0.0, 1.0) * 0.8 * keep;
    }
    return acc;
}

// returns colour; cover = how much the disc hides what is behind it
vec3 planet(vec2 px, out float cover) {
    cover = 0.0;
    if (u_planet.w < 0.5) return vec3(0.0);
    vec2 q = (px - u_planet.xy) / u_planet.z;
    float r2 = dot(q, q);
    float R = u_planet.z;
    vec3 col = vec3(0.0);
    // the sun direction: local hour around the planet's axis
    vec3 sun = normalize(vec3(sin(u_sun.x), 0.25, -cos(u_sun.x)));
    if (r2 < 1.0) {
        float z = sqrt(1.0 - r2);
        vec3 n = vec3(q.x, -q.y, z);
        float ct = cos(u_sun.z), st = sin(u_sun.z);         // axial tilt
        vec3 m = vec3(n.x * ct - n.y * st, n.x * st + n.y * ct, n.z);
        float lat = asin(clamp(m.y, -1.0, 1.0));
        float lon = atan(m.x, m.z) + u_time * u_sun.y;
        float px_per_rad = R * max(z, 0.08);
        float dl = abs(fract(lat / 0.2618 + 0.5) - 0.5) * 0.2618 * R;       // 15 deg bands
        float dn = abs(fract(lon / 0.3491 + 0.5) - 0.5) * 0.3491 * px_per_rad * cos(lat);
        float grid = max(clamp(1.0 - dl, 0.0, 1.0), clamp(1.0 - dn, 0.0, 1.0) * 0.8);
        // storm bands: denser faint lines near the equator
        float band = exp(-pow(lat * 3.2, 2.0)) * clamp(1.0 - abs(fract(lat / 0.05 + 0.5) - 0.5) * 0.05 * R, 0.0, 1.0) * 0.35;
        float light = dot(n, sun);
        float day = smoothstep(-0.05, 0.25, light);
        float term = exp(-light * light / 0.0016);
        col = PHOS * (grid * (0.12 + 0.75 * day) + band * day) * 0.85;
        col += AMBER * term * (0.35 + grid * 0.8);
        col += DIM * pow(1.0 - z, 3.0) * (0.25 + 0.75 * day) * 0.9;         // limb
        col += vec3(0.0, 0.02, 0.0) * day;
        cover = smoothstep(1.0, 0.985, sqrt(r2));
    }
    // atmosphere: a thin rim halo, brighter on the day side
    float rr = sqrt(r2);
    float side = dot(normalize(vec3(q.x, -q.y, 0.0001)), sun);
    float halo = exp(-pow((rr - 1.0) * R / 5.0, 2.0)) * (0.35 + 0.65 * smoothstep(-0.3, 0.6, side));
    halo += exp(-max(rr - 1.0, 0.0) * R / 40.0) * step(1.0, rr) * 0.06;
    col += SOFT * halo * 0.55;
    // a ring system, tilted: two thin ellipses, hidden behind the disc
    vec2 e = q;
    float ca = cos(-0.32), sa = sin(-0.32);
    e = vec2(ca * e.x - sa * e.y, sa * e.x + ca * e.y);
    for (int i = 0; i < 2; i++) {
        float rad = 1.55 + 0.18 * float(i);
        float k = length(vec2(e.x, e.y / 0.16)) - rad;
        float d = abs(k) * R * 0.16;
        float behind = (e.y < 0.0 && r2 < 1.0) ? 0.0 : 1.0;
        col += DIM * clamp(1.2 - d, 0.0, 1.0) * behind * (0.9 - 0.3 * float(i));
    }
    return col;
}

vec3 relay_beam(vec2 px) {
    if (u_space.z < 0.5) return vec3(0.0);
    vec2 o = u_beam.xy;
    vec2 dir = vec2(cos(u_beam.z), sin(u_beam.z));
    vec2 d = px - o;
    float along = dot(d, dir);
    if (along < 0.0) return vec3(0.0);
    float off = abs(d.x * dir.y - d.y * dir.x);
    float core = clamp(1.0 - off, 0.0, 1.0) * 0.35 + exp(-off * off / 30.0) * 0.08;
    float fade = exp(-along / 1400.0);
    float pulse = 0.0;
    for (int i = 0; i < 3; i++) {
        float p = fract(u_time * u_beam.w + float(i) / 3.0) * 1600.0;
        pulse += exp(-pow(along - p, 2.0) / 900.0) * exp(-off * off / 6.0);
    }
    return SOFT * (core + pulse * 0.9) * fade;
}
