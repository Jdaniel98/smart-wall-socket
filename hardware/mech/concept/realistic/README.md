# Concept renders with generic components

Visual models only. The parts are generic shapes of the right size and the placement is illustrative: this is **not** the PCB layout and must not be used for clearances or manufacture.

- `exploded.png`: exploded view, ray-traced (Blender Cycles).
- `board.png`: rear board, top face.
- `lineart.png`: pad drawing of the same placement.

Regenerate: `python3 ../concept.py` (writes the base meshes), then `python3 scene.py exploded 56`, `python3 scene.py board 56` and `python3 lineart.py`. Needs `pip install build123d bpy pillow`. Paths in the scripts point at `/tmp/render` and `/tmp/rt`.
