#version 330 core
in vec4 v_col;
out vec4 o;
void main() { o = vec4(v_col.rgb * v_col.a, 0.0); }
