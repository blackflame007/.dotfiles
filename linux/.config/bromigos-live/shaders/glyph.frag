#version 330 core
in vec2 v_uv;
in vec4 v_col;
uniform sampler2D u_atlas;
out vec4 o;
void main() {
    float a = texture(u_atlas, v_uv).a * v_col.a;
    o = vec4(v_col.rgb * a, 0.0);
}
