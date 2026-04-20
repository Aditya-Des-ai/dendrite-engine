import taichi as ti
import random
ti.init(arch=ti.gpu)

W, H = 200, 200

grid = ti.field(dtype=ti.i32, shape=(W, H))
stick_prob = 0.4
# RGB pixel buffer
pixels = ti.Vector.field(3, dtype=ti.f32, shape=(W, H))

# Temperature field
temperature = ti.field(dtype=ti.f32, shape=(W, H))

# Particle system (ions)
max_particles = 2000
particle_pos = ti.Vector.field(2, dtype=ti.f32, shape=max_particles)
particle_count = ti.field(dtype=ti.i32, shape=())

# SEI thickness
sei_thickness = ti.field(dtype=ti.f32, shape=(W, H))

@ti.func
def get_occlusion(x, y):
    count = 0.0

    for dx in ti.static(range(-1, 2)):
        for dy in ti.static(range(-1, 2)):

            nx = x + dx
            ny = y + dy

            if not (dx == 0 and dy == 0):  # ✅ avoid continue
                if 0 <= nx < W and 0 <= ny < H:
                    count += float(grid[nx, ny])

    return count / 8.0
@ti.func
def is_interface(x, y):
    result = 0

    for dx in ti.static(range(-1, 2)):
        for dy in ti.static(range(-1, 2)):

            nx = x + dx
            ny = y + dy

            if 0 <= nx < W and 0 <= ny < H:
                if grid[nx, ny] == 0:
                    result = 1

    return result
@ti.kernel
def paint():
    for x, y in pixels:

        if grid[x, y] == 1:
            # ===== CRYSTAL =====
            depth = float(y) / H
            occ = get_occlusion(x, y)
            brightness = 1.0 - occ * 0.6

            r = ti.min(depth * depth * 1.5 * brightness, 1.0)
            g = ti.min(depth * 0.9 * brightness, 1.0)
            b = ti.min((1.0 - depth * 0.4) * brightness, 1.0)

            # SEI overlay
            if is_interface(x, y):
                sei = ti.min(sei_thickness[x, y], 1.0)
                r += sei * 0.15
                g += sei * 0.20
                b -= sei * 0.10

            pixels[x, y] = ti.Vector([r, g, b])

        else:
            # ===== ELECTROLYTE =====
            depth = float(y) / H
            bg = 0.015 + depth * 0.025

            temp = temperature[x, y]

            pixels[x, y] = ti.Vector([
                bg * 0.6 + temp * 0.08,
                bg * 0.7 - temp * 0.01,
                bg * 1.8 - temp * 0.12
            ])
@ti.kernel

def paint_ions():
    particle_count[None] = 800

    for i in range(500):
        particle_pos[i] = ti.Vector([
            ti.random() * W,
            ti.random() * H
        ])
    for i in range(particle_count[None]):
        px = int(particle_pos[i][0])
        py = int(particle_pos[i][1])

        for dx in ti.static(range(-3, 4)):
            for dy in ti.static(range(-3, 4)):
                nx = px + dx
                ny = py + dy

                if 0 <= nx < W and 0 <= ny < H:
                    dist = ti.sqrt(float(dx * dx + dy * dy))
                    glow = ti.max(0.0, 0.35 - dist * 0.10)

                    intensity = ti.max(0.0, 0.5 - dist * 0.15)
                    pixels[nx, ny] += ti.Vector([
                        glow * 2.5,
                        glow * 0.1,
                        glow * 0.1
                    ])
@ti.kernel
def init_temperature():
    for x, y in temperature:
        cx = W / 2
        dist = abs(x - cx) / cx
        temperature[x, y] = 1.0 - dist  # hot center, cool edges

@ti.kernel
def init_grid():
    for x, y in grid:
        grid[x, y] = 0

    for x in range(W):
        grid[x, 0] = 1  # anode base
@ti.func
def near_cluster(x, y):
    found = 0

    for dx, dy in ti.static([(1,0), (-1,0), (0,1), (0,-1)]):
        nx = x + dx
        ny = y + dy

        if 0 <= nx < W and 0 <= ny < H:
            if grid[nx, ny] == 1:
                found = 1

    return found
@ti.func
def near_cluster(x, y):
    found = 0
    for dx in ti.static(range(-1, 2)):
        for dy in ti.static(range(-1, 2)):
            if not (dx == 0 and dy == 0):
                nx = x + dx
                ny = y + dy
                if 0 <= nx < W and 0 <= ny < H:
                    if grid[nx, ny] == 1:
                        found = 1
    return found
@ti.kernel
def move_particles():
    for i in range(particle_count[None]):

        # current position
        px = int(particle_pos[i][0])
        py = int(particle_pos[i][1])

        # random movement
        particle_pos[i][0] += ti.random() * 2 - 1
        particle_pos[i][1] += ti.random() * 2 - 1
        particle_pos[i][1] -= 0.1

        # clamp to grid
        particle_pos[i][0] = ti.max(0, ti.min(W - 1, particle_pos[i][0]))
        particle_pos[i][1] = ti.max(0, ti.min(H - 1, particle_pos[i][1]))

        # updated position
        px = int(particle_pos[i][0])
        py = int(particle_pos[i][1])

        # 🔥 THIS IS WHERE YOU ADD IT
        if near_cluster(px, py) == 1:
            if ti.random() < stick_prob:
                grid[px, py] = 1

                # deactivate particle (send it away)
                particle_pos[i] = ti.Vector([
                    ti.random() * W,
                    H - 1   # respawn at top
                ])


gui = ti.GUI("Dendrite Engine", res=(W, H), background_color=0x0a0a12)

init_grid()
init_temperature()
move_particles()
particle_count[None] = 0

while gui.running:

    # 👉 your simulation step goes here
    for _ in range(40):  # simulation speed
        move_particles()
    paint()
    paint_ions()

    gui.set_image(pixels)

    # ===== HUD =====
    gui.text("Dendrite Engine", pos=(0.02, 0.96), color=0x8888CC)
    gui.text("Mode: FAST CHARGE", pos=(0.02, 0.08), color=0x8888CC)
    #print("Particles:", particle_count[None])

    gui.show()
'''For Fast charge mode, we increase the stick pobability to 0.8 and drift to 0.8 too
For Slow charge mode, we decrease the stick pobability to 0.4 and drift to 0.01
'''