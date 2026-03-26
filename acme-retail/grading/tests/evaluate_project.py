#!/usr/bin/env python3
"""
evaluate_project.py  —  Acme Retail Full Retail Day Grading Animation
======================================================================
Location:  acme-retail/grading/tests/evaluate_project.py
Run from:  acme-retail/grading/tests/
Command:   python3 evaluate_project.py
"""

import curses, subprocess, threading, queue, time, sys, os, re, math

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
SUITES = [
    ("Order Fulfillment",    "tests.test_order_fulfillment",    13),
    ("Inventory Management", "tests.test_inventory_management",  7),
    ("Incident Response",    "tests.test_incident_response",     8),
    ("Company Policies",     "tests.test_knowledge_query",        6),
]

VENV_PYTHON = '/workspaces/Solace_Academy_SAM_Dev_Demo/300-Agents/sam/.venv/bin/python3'
DEMO_MODE   = True   # set False to run real tests

# Frame timing configuration
FRAME_DURATION = 0.033  # seconds per frame (change this to adjust visual smoothness)
# 0.22 = 4.5 fps, 0.11 = 9 fps, 0.067 = 15 fps, 0.033 = 30 fps

# Animation playback speed multiplier (independent of frame rate)
# 1.0 = normal speed, 2.0 = 2x speed, 0.5 = half speed
PLAYBACK_SPEED = 4.0

EVQ = queue.Queue()

# ---------------------------------------------------------------------------
# TEST RUNNER
# ---------------------------------------------------------------------------
def run_tests():
    if DEMO_MODE:
        for name, _, checks in SUITES:
            EVQ.put({'type': 'suite_start', 'name': name, 'checks': checks})
            time.sleep(checks * 0.45)  # adjust demo timing proportionally
            EVQ.put({'type': 'suite_done', 'name': name, 'passed': True})
        EVQ.put({'type': 'all_done'})
        return

    grading_dir = os.path.dirname(os.path.abspath(__file__))
    grading_dir = os.path.dirname(grading_dir)
    py = VENV_PYTHON if os.path.exists(VENV_PYTHON) else sys.executable

    for name, module, checks in SUITES:
        EVQ.put({'type': 'suite_start', 'name': name, 'checks': checks})
        try:
            proc = subprocess.run(
                [py, '-m', module, '-v'],
                cwd=grading_dir, capture_output=True, text=True, timeout=300,
            )
            passed = (proc.returncode == 0)
        except Exception:
            passed = False
        EVQ.put({'type': 'suite_done', 'name': name, 'passed': passed})

    EVQ.put({'type': 'all_done'})

# ---------------------------------------------------------------------------
# CANVAS — dimensions set dynamically each frame from terminal size.
# W and H are module-level vars updated in curses_main before each render.
# Minimum canvas size the scenes were designed for:
MIN_CANVAS_WIDTH, MIN_CANVAS_HEIGHT = 72, 16
# Current canvas dimensions (updated per-frame)
canvas_width, canvas_height = MIN_CANVAS_WIDTH, MIN_CANVAS_HEIGHT
# Offset to centre the canvas on screen
canvas_col_offset, canvas_row_offset = 0, 0
# ---------------------------------------------------------------------------

def new_buf():
    return [[(' ', 0)] * canvas_width for _ in range(canvas_height)]

def put(buffer, row, col, text, color_pair=0):
    """Write string into buffer, silently clipping anything out of bounds."""
    if row < 0 or row >= canvas_height:
        return
    for i, ch in enumerate(text):
        c2 = col + i
        if 0 <= c2 < canvas_width:
            buffer[row][c2] = (ch, color_pair)

def hline(buffer, row, col_start, col_end, character, color_pair=0):
    if row < 0 or row >= canvas_height:
        return
    for x in range(max(0, col_start), min(canvas_width, col_end + 1)):
        buffer[row][x] = (character, color_pair)

def clamp(value, min_val, max_val):
    return max(min_val, min(max_val, value))

def render(stdscr, buffer):
    """Blit buffer onto stdscr at (canvas_row_offset, canvas_col_offset) to centre it."""
    for r in range(canvas_height):
        for col in range(canvas_width):
            ch, cp = buffer[r][col]
            try:
                stdscr.addch(r + canvas_row_offset, col + canvas_col_offset,
                             ch, curses.color_pair(cp))
            except curses.error:
                pass

# Color pair numbers
def W_(): return 1   # white
def G():  return 2   # green
def Y():  return 3   # yellow
def R():  return 4   # red
def C():  return 5   # cyan
def B():  return 6   # blue
def D():  return 7   # dim (rendered as white; not black-on-black)

# ---------------------------------------------------------------------------
# SCENE HELPERS — scenes use W/H globals so they scale automatically
# ---------------------------------------------------------------------------

def center_column(width):
    """Return column that centres a block of `width` chars in the canvas."""
    return max(0, (canvas_width - width) // 2)

# ---------------------------------------------------------------------------
# SCENE 0  Night to day, store opens
# ---------------------------------------------------------------------------
def scene0(t):
    """
    Scene 0 timeline (in seconds):
    - 0.0s: Stars visible, moon moving right
    - 3.3s: Sun appears
    - 13.9s: Sun peaks (top-left corner)
    - 15.0s: Scene ends, store fully open
    """
    buffer = new_buf()
    dawn = t / 15  # normalized 0-1 over 15 seconds

    # Calculate when sun reaches peak height
    sun_peak_t = 10

    # Stars
    star_cols = [6, 14, 22, 34, 46, 58, canvas_width-8, canvas_width-2]
    for i, sc in enumerate(star_cols):
        sr = i % 3
        if sc < canvas_width:
            put(buffer, sr, sc, '+', D())

    # Moon (moves right, visible until t=11s or so)
    if dawn < 0.5:
        mx = int(clamp(canvas_width - 8 - t * 4, 2, canvas_width - 8))
        put(buffer, 0, mx, '( )', D())

    # Sun (rises vertically, arcs horizontally from right to center)
    if dawn > 0:  # appears after ~0 seconds
        sy = int(clamp(6 - t * 0.36, 1, 6))
        sx = int(clamp(canvas_width - 12 - t * 0.5, canvas_width//2, canvas_width - 12))
        put(buffer, sy,     sx,     '\\ | /', Y())
        put(buffer, sy + 1, sx - 2, '  --(O)--', Y())
        put(buffer, sy + 2, sx,     '/ | \\', Y())

    # Ground
    ground = canvas_height - 2
    hline(buffer, ground, 0, canvas_width-1, '_', D())
    hline(buffer, ground +1, 0, canvas_width-1, '_', D())

    # Store — centred, roof at row 2, walls all the way to ground
    store_w  = 35
    sx2      = center_column(store_w)
    roof_row = 2
    right_wall = sx2 + store_w - 1

    # Roof
    put(buffer, roof_row,   sx2, ','+'-'*(store_w-2)+'.', W_())
    
    # Windows light up bottom-to-top starting at t=5s
    # Each row lights up with 2-frame intervals (~0.22 seconds per frame, so 2 frames = 0.44s feel)
    # With 4 rows max: times 5s, 5.44s, 5.88s, 6.32s — all complete before scene ends at 15s
    window_start_t = 5.0  # seconds
    row_interval = 0.44  # seconds between each row lighting up
    
    # We need num_win_rows to calculate top_row_light_frame
    inner_w   = store_w - 2
    building_rows_early = ground - (roof_row + 3)
    num_win_rows_early = max(1, (building_rows_early - 2) // 4)
    top_row_light_frame = window_start_t + (num_win_rows_early - 1) * row_interval
    
    # Building name turns green when top row of windows light up (synchronized)
    put(buffer, roof_row+1, sx2, '|       A C M E   R E T A I L     |',
        G() if t >= top_row_light_frame else W_())
    put(buffer, roof_row+2, sx2, '+'+'-'*(store_w-2)+'+', W_())

    # Walls — left and right, full height
    for row in range(roof_row+3, ground):
        put(buffer, row, sx2,        '|', W_())
        put(buffer, row, right_wall, '|', W_())

    # Windows — fill building height dynamically, 2 rows of windows if tall enough
    n_wins    = 4
    win_w     = 3
    win_gap   = 4
    win_span  = n_wins * win_w + (n_wins - 1) * win_gap
    win_off   = 1 + (inner_w - win_span) // 2
    win_cols  = [sx2 + win_off + i*(win_w+win_gap) for i in range(n_wins)]
    win_start = roof_row + 3
    win_block = 4
    num_win_rows = num_win_rows_early
    
    for wr in range(num_win_rows):
        row0 = win_start + wr * win_block
        if row0 + 2 >= ground - 5:
            continue
        
        row_from_bottom = (num_win_rows - 1) - wr
        row_light_frame = window_start_t + row_from_bottom * row_interval
        row_lit = t >= row_light_frame
        
        for wi, wc in enumerate(win_cols):
            if wc + 3 >= right_wall: continue
            cp  = Y() if row_lit else D()
            put(buffer, row0,   wc, '+-+', cp)
            put(buffer, row0+1, wc, '|' + ('#' if row_lit else ' ') + '|', cp)
            put(buffer, row0+2, wc, '+-+', cp)

    # OPEN FOR BUSINESS sign — appears when top row of windows light up
    if t >= top_row_light_frame:
        sign_row = ground - 6
        if sign_row > win_start:
            sign     = '* * OPEN FOR BUSINESS * *'
            sign_col = sx2 + (store_w - len(sign)) // 2
            put(buffer, sign_row, sign_col, sign, G())

    # Door — clean, 4 rows, centred on store, sits at ground
    door_top = ground - 4
    door_col = sx2 + store_w//2 - 3
    if t < top_row_light_frame:
        put(buffer, door_top,   door_col, '[======]', D())
        put(buffer, door_top+1, door_col, '[      ]', D())
        put(buffer, door_top+2, door_col, '[CLOSED]', D())
        put(buffer, door_top+3, door_col, '[      ]', D())
        put(buffer, door_top+4, door_col, '[______]', D())
    else:
        put(buffer, door_top,   door_col, '[======]', G())
        put(buffer, door_top+1, door_col, '[      ]', G())
        put(buffer, door_top+2, door_col, '[ OPEN ]', G())
        put(buffer, door_top+3, door_col, '[      ]', G())
        put(buffer, door_top+4, door_col, '[______]', G())

    hr = 6 + int(t // 5)
    mn = str(int((t % 5) * 12)).zfill(2)
    put(buffer, 0, 0, f' {hr}:{mn} AM ', C())

    return buffer

# ---------------------------------------------------------------------------
# SCENE 1  Same store as scene0 — order board fades in, shoppers arrive
# ---------------------------------------------------------------------------
def scene1(t):
    """
    Scene 1 timeline (in seconds):
    - 0.0s: Order board appears (after 4s delay from scene start = 19s total)
    - 3.0s: First shopper starts appearing
    - 12.0s: Last shopper starts appearing
    - 36.0s: Scene ends
    """
    buffer = new_buf()
    ground = canvas_height - 2

    # Ground
    hline(buffer, ground, 0, canvas_width-1, '_', D())
    hline(buffer, ground +1, 0, canvas_width-1, '_', D())

    
    # Sun at fixed position (same as end of scene0)
    sy = int(clamp(6 - 10 * 0.36, 1, 6))
    sx = int(clamp(canvas_width - 12 - 10 * 0.5, canvas_width//2, canvas_width - 12))
    put(buffer, sy,     sx,     '\\ | /', Y())
    put(buffer, sy + 1, sx - 2, '  --(O)--', Y())
    put(buffer, sy + 2, sx,     '/ | \\', Y())

    # ── Identical store from scene0 ──────────────
    store_w    = 35
    sx2        = center_column(store_w)
    roof_row   = 2
    right_wall = sx2 + store_w - 1

    put(buffer, roof_row,   sx2, ','+'-'*(store_w-2)+'.', W_())
    put(buffer, roof_row+1, sx2, '|       A C M E   R E T A I L     |', G())
    put(buffer, roof_row+2, sx2, '+'+'-'*(store_w-2)+'+', W_())
    for row in range(roof_row+3, ground):
        put(buffer, row, sx2,        '|', W_())
        put(buffer, row, right_wall, '|', W_())

    # Windows — all lit
    inner_w   = store_w - 2
    n_wins, win_w, win_gap = 4, 3, 4
    win_span  = n_wins*win_w + (n_wins-1)*win_gap
    win_off   = 1 + (inner_w - win_span)//2
    win_cols  = [sx2 + win_off + i*(win_w+win_gap) for i in range(n_wins)]
    win_start = roof_row + 3
    win_block = 4
    door_top  = ground - 4
    num_win_rows = max(1, (ground - win_start - 2)//win_block)
    for wr in range(num_win_rows):
        row0 = win_start + wr*win_block
        if row0 + 2 >= door_top - 2: break
        for wc in win_cols:
            if wc+3 >= right_wall: continue
            put(buffer, row0,   wc, '+-+', Y())
            put(buffer, row0+1, wc, '|#|', Y())
            put(buffer, row0+2, wc, '+-+', Y())

    # Sign
    sign_row = door_top - 2
    if sign_row > win_start + 2:
        sign     = '* * OPEN FOR BUSINESS * *'
        sign_col = sx2 + (store_w - len(sign))//2
        put(buffer, sign_row, sign_col, sign, G())

    # Door — open and green throughout scene1
    door_col = sx2 + store_w//2 - 3
    put(buffer, door_top,   door_col, '[======]', G())
    put(buffer, door_top+1, door_col, '[      ]', G())
    put(buffer, door_top+2, door_col, '[ OPEN ]', G())
    put(buffer, door_top+3, door_col, '[      ]', G())
    put(buffer, door_top+4, door_col, '[______]', G())

    # ── Order board — fades in after t=1 seconds ────────────────────────
    if t > 1:
        box_w = 34
        box_x = 2
        put(buffer, 0, box_x, '+' + '-'*box_w + '+', B())
        put(buffer, 1, box_x, '| ORDERS DASHBOARD  10:30 AM ' + ' '*(box_w-27), B())
        put(buffer, 1, box_x + box_w + 1, '|', B())
        put(buffer, 2, box_x, '+' + '-'*box_w + '+', B())
        orows = [
            ('ORD-001', 'Sarah', t > 7),
            ('ORD-002', 'James', t > 16),
            ('ORD-005', 'Lisa ', t > 24),
        ]
        for i, (oid, name, done) in enumerate(orows):
            status = 'VALIDATED' if done else 'pending..'
            st_cp  = G() if done else D()
            line   = f'| {oid}  {name}   '
            put(buffer, 3+i, box_x, line, B())
            put(buffer, 3+i, box_x+len(line), status, st_cp)
            put(buffer, 3+i, box_x + box_w + 1, '|', B())
        confirmed = sum(1 for *_,d in orows if d)
        footer = f'| Confirmed: {confirmed}/3   Pending: {3-confirmed}/3'
        put(buffer, 6, box_x, footer.ljust(box_w), B())
        put(buffer, 6, box_x + box_w + 1, '|', B())
        put(buffer, 7, box_x, '+' + '-'*box_w + '+', B())

    # ── Shoppers walk from left toward the store entrance ─────────────────
    max_x  = sx2 - 2
    shoppers = [
        dict(bx=-2,  spd=3.3, oid='ORD-001', tot='$299', appear_delay=0),
        dict(bx=-22, spd=3.3, oid='ORD-002', tot='$849', appear_delay=1),
        dict(bx=-42, spd=3.3, oid='ORD-005', tot='$549', appear_delay=2),
    ]
    walk = (int(t / 1.2)) % 2  # convert to frame-like cadence based on time
    for s in shoppers:
        sx = int(s['bx'] + t*s['spd'])
        if sx > max_x or sx + 10 < 0:
            continue

        r_head = ground - 2
        r_hand = ground - 1
        r_legs = ground - 0
        cx     = sx + 4
        leg_str = ['|/', '|\\'][walk]

        if r_head >= 0 and 0 <= sx < canvas_width-2:
            put(buffer, r_head, sx, ' o  ', W_())
            put(buffer, r_hand, sx, '/|  ', W_())
        if r_head >= 0 and 0 <= cx < canvas_width-5:
            put(buffer, r_hand, cx-1, '-|___]', Y())
            put(buffer, ground, cx, ' o o ', Y())
        if r_head >= 0 and 0 <= sx < canvas_width-2:
            put(buffer, r_legs, sx, leg_str, W_())

        # Speech bubble — appears after delay
        appear_frame = -s['bx'] / s['spd']
        time_since_appear = t - appear_frame
        if time_since_appear > s['appear_delay'] and sx >= 0 and r_head >= 6:
            bx2 = clamp(sx - 2, 2, sx - 2)
            put(buffer, r_head-5, bx2, '.---------------.', W_())
            put(buffer, r_head-4, bx2, '| '+s['oid']+'  '+s['tot']+' |', G())
            put(buffer, r_head-3, bx2, "'---------------'", W_())

    return buffer

# ---------------------------------------------------------------------------
# SCENE 2  Warehouse + forklift + restock truck
# ---------------------------------------------------------------------------
def scene2(t, state=None):
    """
    Scene 2 timeline (in seconds):
    - 0.0s: Forklift starts at center
    - 10.0s: Forklift reaches left shelf
    - 15.0s: Forklift picks up box, raises forks
    - 20.0s: Forklift lowers forks with box
    - 28.0s: Forklift repositioned toward right
    - 36.0s: Forklift raises box on right shelf
    - 40.0s: Box disappears, forks lower
    - 44.0s: Forklift turns around
    - 52.0s: Scene ends
    
    Truck timeline:
    - 24.0s: Truck appears from right
    - Collision when truck reaches alert box
    - Success window: 1.5 seconds
    """
    buffer = new_buf()
    put(buffer, 0, 0, (' WAREHOUSE WH-A | San Francisco, CA | 65% capacity')[:canvas_width], W_())
    hline(buffer, 1, 0, canvas_width-1, '=', D())

    # Two columns of shelves
    left_col = 1
    right_col = canvas_width - 40
    
    top_row = 2
    mid_row = canvas_height // 2 - 4
    bot_row = canvas_height - 11
    
    # Determine Pro Tablet 12 shelf color based on timeline
    if state.truck_collision_t is None:
        if t < 15:
            tablet_color = Y()
            tablet_qty = ' 8 '
            tablet_status = 'LOW'
            tablet_fill = 2
        else:
            tablet_color = R()
            tablet_qty = ' 0 '
            tablet_status = 'OUT OF STOCK'
            tablet_fill = 0
    else:
        tablet_color = G()
        tablet_qty = '50 '
        tablet_status = 'OK '
        tablet_fill = 10
    
    shelves = [
        (top_row, left_col,  'UltraBook Pro ', '45 ', 'OK ', 9,  G()),
        (top_row, right_col, 'Gaming Laptop ', ' 8 ', 'LOW', 2,  Y()),
        (mid_row, left_col,  'Keyboard RGB  ', '150', 'OK ', 10, G()),
        (mid_row, right_col, '4K Webcam     ', ' 84', 'OK ', 8,  G()),
        (bot_row, left_col,  'Pro Tablet 12 ', tablet_qty, tablet_status, tablet_fill, tablet_color),
        (bot_row, right_col, 'Wireless Mouse', '220', 'OK ', 10, G()),
    ]
    shelf_w = 38
    for sr, sc2, name, qty, st, fill, cp in shelves:
        if sc2 + shelf_w >= canvas_width or sc2 < 0: continue
        
        put(buffer, sr,   sc2, '+-' + '-'*(shelf_w-4) + '-+', cp)
        header = f'| {name:<30} {qty:>4}'
        put(buffer, sr+1, sc2, header, cp)
        put(buffer, sr+1, sc2 + shelf_w - 1, '|', cp)
        status_txt = f'| Status: [{st:^3}]' + ' '*(shelf_w-15)
        put(buffer, sr+2, sc2, status_txt, W_())
        put(buffer, sr+2, sc2 + shelf_w - 1, '|', W_())
        bar = '#'*fill + ' '*(10-fill)
        bar_row = f'| Stock: [{bar}]' + ' '*(shelf_w-16)
        put(buffer, sr+3, sc2, bar_row, cp)
        put(buffer, sr+3, sc2 + shelf_w - 1, '|', cp)
        put(buffer, sr+4, sc2, '|' + '-'*(shelf_w-2) + '|', D())
        put(buffer, sr+5, sc2, '+-' + '-'*(shelf_w-4) + '-+', cp)

    # Forklift journey with complete lifecycle
    floor_r = canvas_height - 3
    shelf_w = 38
    under_shelf_x = left_col + shelf_w
    start_x = canvas_width // 2
    right_deposit_x = right_col
    
    # Expanded timeline for complete forklift lifecycle (in seconds)
    if t < 10:
        # Phase 1: Move from start to left shelf (0-10s)
        progress = t / 10.0
        fx = int(start_x - (start_x - under_shelf_x) * progress)
        carrying = False
        lh = 0
        mirrored = False
    elif t < 15:
        # Phase 2: Raise forks, box appears (10-15s)
        fx = under_shelf_x
        carrying = True
        lh = ((t - 10) / 5.0) * 2
        mirrored = False
    elif t < 20:
        # Phase 3: Lower forks fully (15-20s)
        fx = under_shelf_x
        carrying = True
        lh = max(0, 2 - ((t - 15) / 5.0) * 2)
        mirrored = False
    elif t < 28:
        # Phase 4: Back up, turn around (20-28s)
        progress = (t - 20) / 8.0
        fx = int(under_shelf_x + (start_x - under_shelf_x) * progress)
        carrying = True
        lh = 0
        mirrored = True
    elif t < 36:
        # Phase 5: Move right (28-36s)
        progress = (t - 28) / 8.0
        fx = int(start_x + (right_deposit_x - start_x) * progress)
        carrying = True
        lh = 0
        mirrored = True
    elif t < 40:
        # Phase 6: Raise forks (36-40s)
        fx = right_deposit_x
        carrying = True
        lh = ((t - 36) / 4.0) * 2
        mirrored = True
    elif t < 44:
        # Phase 7: Box disappears, forks lower (40-44s)
        fx = right_deposit_x
        carrying = False
        lh = max(0, 2 - ((t - 40) / 4.0) * 2)
        mirrored = True
    elif t < 52:
        # Phase 8: Turn around, move toward start (44-52s)
        progress = (t - 44) / 8.0
        fx = int(right_deposit_x - (right_deposit_x - start_x) * progress)
        carrying = False
        lh = 0
        mirrored = False
    else:
        # Phase 9: Idle at start (52+s)
        fx = start_x
        carrying = False
        lh = 0
        mirrored = False

    # Cab with forks — mirrored based on direction
    if not mirrored:
        for mr in range(floor_r-3, floor_r):
            put(buffer, mr, fx, '|=|', Y())
        put(buffer, floor_r-2, fx, '|o|~~~|', Y())
        put(buffer, floor_r-1, fx, '|_|~~~|', Y())
        put(buffer, floor_r, fx, 'O O', Y())
        put(buffer, floor_r, fx+4, 'O O', Y())
        fork_row = int((floor_r - 1) - int(lh))
        if fx - 5 >= 0:
            put(buffer, fork_row,   fx-5, '=====', Y())
            put(buffer, fork_row+1, fx-5, '=====', Y())
        if carrying and t >= 15 and fx - 8 >= 0:
            box_row = int(fork_row - 1)
            put(buffer, box_row+2,   fx-8, '+-----+', C())
            put(buffer, box_row+1,   fx-8, '|_____|', C())
            put(buffer, box_row,   fx-8, '|-----|', C())
            put(buffer, box_row-1,   fx-8, '+-----+', C())
    else:
        for mr in range(floor_r-3, floor_r):
            put(buffer, mr, fx+4, '|=|', Y())
        put(buffer, floor_r-2, fx, '|~~~|o|', Y())
        put(buffer, floor_r-1, fx, '|~~~|_|', Y())
        put(buffer, floor_r, fx, 'O O', Y())
        put(buffer, floor_r, fx+4, 'O O', Y())
        fork_row = int((floor_r - 1) - int(lh))
        if fx + 7 < canvas_width:
            put(buffer, fork_row,   fx+7, '=====', Y())
            put(buffer, fork_row+1, fx+7, '=====', Y())
        if carrying and t >= 15 and fx + 10 < canvas_width:
            box_row = int(fork_row - 1)
            put(buffer, box_row+2,   fx+8, '+-----+', C())
            put(buffer, box_row+1,   fx+8, '|_____|', C())
            put(buffer, box_row,     fx+8, '|-----|', C())
            put(buffer, box_row-1,   fx+8, '+-----+', C())

    # Out-of-stock alert and truck collision
    alert_w = min(42, canvas_width - 2)
    alert_col = center_column(alert_w)
    alert_right_edge = alert_col + alert_w
    
    truck_w = 13
    success_duration = 6  # seconds
    truck_speed = 5
    
    # Alert appears at t=20s (after forklift picks up box)
    if t > 20:
        if state.truck_collision_t is None:
            alert_color = R()
            alert_text = '| !! Pro Tablet 12 OUT OF STOCK !!'
            extra_text = '| INC-2026-015 created  >> ESCALATING'
        elif (t - state.truck_collision_t) < success_duration:
            alert_color = G()
            alert_text = '| Pro Tablet 12 back in stock √'
            extra_text = '| Restock shipment received'
        else:
            alert_color = None
        
        if alert_color is not None:
            put(buffer, 14, alert_col, '+' + '-'*alert_w + '+', alert_color)
            put(buffer, 15, alert_col, (alert_text).ljust(alert_w+1) + '|', alert_color)
            put(buffer, 16, alert_col, (extra_text).ljust(alert_w+1) + '|', alert_color)
            put(buffer, 17, alert_col, '+' + '-'*alert_w + '+', alert_color)
    
    # Restock truck appears at t=24s
    if t > 24:
        tx_raw = canvas_width - 5 - (t - 24) * truck_speed
        truck_left_edge = int(tx_raw)
        
        if truck_left_edge <= alert_right_edge and state.truck_collision_t is None:
            state.truck_collision_t = t
        
        if state.truck_collision_t is None:
            tx = int(canvas_width - 5 - (t - 24) * truck_speed)
        elif (t - state.truck_collision_t) < success_duration:
            tx = int(alert_right_edge)
        else:
            time_exiting = t - state.truck_collision_t - success_duration
            tx = int(alert_right_edge + time_exiting * truck_speed)
        
        truck_completely_off_screen = tx >= canvas_width
        if truck_completely_off_screen and state.truck_collision_t is not None:
            if not hasattr(state, 'truck_exit_t'):
                state.truck_exit_t = t
        
        if tx < canvas_width - 2:
            put(buffer, 14, tx, '+===========+', Y())
            put(buffer, 15, tx, '|  RESTOCK  |-\\', Y())
            put(buffer, 16, tx, '|  -------  |--|-|', Y())
            put(buffer, 17, tx, '+--O---------O+--]', Y())
            if tx < canvas_width//2 + 4:
                put(buffer, 14, tx+13, 'ARRIVED!', G())
                put(buffer, 15, tx+13, '+50 units', G())

    # Ground
    ground = canvas_height - 2
    hline(buffer, ground, 0, canvas_width-1, '_', D())

    return buffer

# ---------------------------------------------------------------------------
# SCENE 3  Truck + flat tire + mechanic
# ---------------------------------------------------------------------------
def scene3(t):
    """
    Scene 3 timeline (in seconds):
    - 0.0s: Truck accelerating
    - 20.0s: Tire starts to fail (wobble begins)
    - 24.0s: Tire blows, BANG animation starts
    - ~26.4s: Road freezes
    - 28.0s: Incident message appears (after BANG)
    - 33.0s: Mechanic arrives
    - 60.0s: Repair complete, truck exits
    - 80.0s: Scene ends
    """
    buffer = new_buf()
    put(buffer, 0, 0, (' Highway 101 | ORD-005 Lisa Wang | Chicago IL | 11:45 AM')[:canvas_width], C())
    hline(buffer, 1, 0, canvas_width-1, '=', D())

    # Road scrolling — stops 0.5 seconds after tire blows (t=24s)
    road_freeze_t = 26.4  # ~0.5s after t=24
    if t < road_freeze_t:
        scroll = int(t * 1.5)
    else:
        scroll = int(24 * 1.5)

    # Scrolling scenery
    scenery = [
        (30,  [(2,' /\\ ',D()), (3,'/__\\',D()),(4,'/__\\',D()),(5,'/__\\',D()),(6,' ||',D())]),
        (85,  [(2,' /\\ ',D()), (3,'/__\\',D()),(4,'/__\\',D()),(5,'/__\\',D()),(6,' ||',D())]),
        (100,  [(2,' /\\ ',D()), (3,'/__\\',D()),(4,'/__\\',D()),(5,'/__\\',D()),(6,' ||',D())]),
        (150, [(2,'+===O==O==O==O===+',D()),(3,'||              ||',D()),(4,'||  EDA  RULEZ  ||',D()),(5,'||              ||',D()),(6,'+================+',D()),(7,'   |         |   ',D())])
    ]
    for bx, rows in scenery:
        sx = (bx - scroll % canvas_width + canvas_width*3) % canvas_width
        for dr, ch, cp in rows:
            if sx + len(ch) < canvas_width:  # Check that entire string fits
                put(buffer, dr, sx, ch, cp)

    # Road rows
    road_top = canvas_height - 7
    hline(buffer, road_top,   0, canvas_width-1, '_', D())
    hline(buffer, road_top+1, 0, canvas_width-1, '=', D())
    for x in range(0, canvas_width, 14):
        mx = (x - scroll%14 + 14*4) % canvas_width
        if mx < canvas_width-5:
            put(buffer, road_top+1, mx, '-----', D())
    hline(buffer, road_top+2, 0, canvas_width-1, '=', D())
    hline(buffer, road_top+3, 0, canvas_width-1, '_', D())

    # Truck phases — time-based timeline
    truck_w = 24
    if t < 20:
        # Phase 1: Accelerate to center (0-20s)
        tx = int(clamp(t*3.5, 0, canvas_width//2 - truck_w))
        phase = 'rolling'
    elif t < 24:
        # Phase 2: Wobble as tire fails (20-24s)
        tx = int(canvas_width//2 - truck_w + math.sin((t-20)*3.5)*2)
        phase = 'wobble'
    elif t < 60:
        # Phase 3: Flat tire / skidding / repair (24-60s)
        tx = int(canvas_width//2 - truck_w + 2)
        phase = 'flat'
    else:
        # Phase 4: Repaired and driving off (60+s)
        tx = int(canvas_width//2 - truck_w + 2 + (t-60)*6)
        phase = 'repaired'
    tx = clamp(tx, 0, canvas_width - truck_w - 2) if phase != 'repaired' else tx

    tcl = G() if phase == 'repaired' else Y()
    truck_top = road_top - 4
    put(buffer, truck_top,   tx, '+------------------+  +---+', Y())
    put(buffer, truck_top+1, tx, '|  ACME LOGISTICS  |  |>|__\\', Y())
    put(buffer, truck_top+2, tx, '|  ORD-005  $549   |_ | --===|', Y())
    put(buffer, truck_top+3, tx, '+------------------+--+------|+', tcl)
    tire_ok = phase in ('rolling', 'repaired')
    put(buffer, road_top, tx+2,  '(O)', Y())
    put(buffer, road_top, tx+9, '(O)', Y())
    put(buffer, road_top, tx+16,  '(O)' if tire_ok else '(__)', Y() if tire_ok else R())
    put(buffer, road_top, tx+23, '(O)', Y())

    if phase == 'rolling':
        for p in range(3):
            ex = tx - p*3 - 1
            if ex >= 0:
                put(buffer, truck_top, ex, '~', D())
        put(buffer, truck_top-1, tx+2, '>> cruising... all nominal <<', D())

    # ───── BANG ANIMATION (visible for 2 seconds starting at t=24) ─────
    if phase in ('wobble', 'flat'):
        bang_time = t - 20  # time since wobble started
        
        if bang_time < 8.0:  # BANG visible for 9 seconds (~2 second animation cycle)
            bang_col = tx + truck_w // 2 - 8
            bang_row = truck_top - 12
            
            flash_fast = int(bang_time * 2) % 2  # alternate every 0.5 seconds
            
            put(buffer, bang_row + 4, bang_col, '╔═══════════════╗', R())
            put(buffer, bang_row + 5, bang_col, '║               ║', R() if flash_fast == 0 else Y())
            put(buffer, bang_row + 6, bang_col, '║   *** * ***   ║', R() if flash_fast == 0 else Y())
            put(buffer, bang_row + 7, bang_col, '║ *  B A N G  * ║', R() if flash_fast == 0 else Y())
            put(buffer, bang_row + 8, bang_col, '║   *** * ***   ║', R() if flash_fast == 0 else Y())
            put(buffer, bang_row + 9, bang_col, '║               ║', R() if flash_fast == 0 else Y())
            put(buffer, bang_row + 10, bang_col, '╚═══════════════╝', R())

    # ───── FLAT TIRE PHASE ─────
    if phase == 'flat':
        # Incident alert box — appears after BANG ends (t > 28s)
        if t > 28:
            box_w = 44
            box_col = tx + truck_w // 2 - box_w // 2
            box_top = truck_top - 14
            
            put(buffer, box_top + 5,     box_col, '+' + '-'*box_w + '+', R())
            put(buffer, box_top + 6, box_col, ('| !! SHIPMENT DELAY INCIDENT CREATED !!').ljust(box_w+3) + '|', R())
            put(buffer, box_top + 7, box_col, ('| SHIP-2026-0048  flat tire  Hwy 101').ljust(box_w+3) + '|', R())
            put(buffer, box_top + 8, box_col, ('| INC created  ETA +2d  team notified').ljust(box_w+3) + '|', R())
            put(buffer, box_top + 9, box_col, '+' + '-'*box_w + '+', R())
        
        # Mechanic arrives and fixes (from t > 33s onwards)
        if t > 33:
            mx2 = tx + truck_w - 2
            mf  = int((t / 0.8) % 2)  # convert to time-based frame oscillation
            put(buffer, truck_top+4, mx2, ' o ',             W_())
            put(buffer, truck_top+5, mx2, '/|\\' if mf else '\| ', W_())
            put(buffer, truck_top+6, mx2, ' | ',             W_())
            put(buffer, truck_top+7, mx2, '/ \\ ',             W_())
            if t > 36:
                put(buffer, truck_top+2, mx2+14, ['-','/','|','\\'][int((t-40)*2) % 4], Y())
                put(buffer, truck_top+1, mx2+12, 'fixing', D())

    if phase == 'repaired':
        for p in range(min(int(t-60), 4)):
            ex = tx - p*3
            if ex >= 0:
                put(buffer, truck_top, ex, '~', D())
        
        # Repaired message box
        box_w = 44
        stationary_tx = canvas_width//2 - truck_w
        box_col = stationary_tx + truck_w // 2 - box_w // 2
        box_top = truck_top - 14
        
        put(buffer, box_top + 5,     box_col, '+' + '-'*box_w + '+', G())
        put(buffer, box_top + 6, box_col, ('| >> Tire replaced! Back on the road.').ljust(box_w+3) + '|', G())
        put(buffer, box_top + 7, box_col, ('| SHIP-2026-0048  in_transit  ETA updated').ljust(box_w+3) + '|', G())
        put(buffer, box_top + 8, box_col, ('| Customer notified via SMS + email').ljust(box_w+3) + '|', G())
        put(buffer, box_top + 9, box_col, '+' + '-'*box_w + '+', G())

    return buffer

# ---------------------------------------------------------------------------
# SCENE 4  Command centre
# ---------------------------------------------------------------------------
def scene4(t, suites_done):
    """
    Scene 4 timeline (in seconds):
    - 0.0s: Command center displayed
    - 10.0s: Tests completing
    - 35.0s: Scene ends
    """
    buffer = new_buf()
    title = '[ ACME COMMAND CENTER  |  SAM v1.18.9 ]'
    put(buffer, 0, center_column(len(title)), title, W_())
    hline(buffer, 1, 0, canvas_width-1, '=', W_())

    # Desktop Monitor Frame
    monitor_content_w = 80
    monitor_total_w   = monitor_content_w + 4
    monitor_x         = center_column(monitor_total_w)
    monitor_y         = 2
    
    put(buffer, monitor_y, monitor_x, '╔' + '═'*(monitor_content_w + 2) + '╗', D())
    put(buffer, monitor_y + 1, monitor_x, '║' + ' '*(monitor_content_w + 2) + '║', D())
    
    screen_y = monitor_y + 2
    screen_x = monitor_x + 1
    
    # Header bar
    put(buffer, screen_y, screen_x, '┌' + '─'*(monitor_content_w) + '┐', B())
    hdr = 'SOLACE AGENT MESH  --  AGENT STATUS MONITOR'
    hdr_padded = ('  ' + hdr).ljust(monitor_content_w)
    put(buffer, screen_y + 1, screen_x, '│' + hdr_padded[:monitor_content_w] + '│', B())
    put(buffer, screen_y + 2, screen_x, '├' + '─'*(monitor_content_w) + '┤', B())
    
    agents = [
        ('OrchestratorAgent', 'a2a/orchestrator ', '14 req/s'),
        ('AcmeKnowledge     ', 'a2a/knowledge    ', '847 docs'),
        ('OrderFulfillment  ', 'acme/orders/*    ', '10 orders'),
        ('InventoryMgmt     ', 'acme/inventory/* ', 'sync ok  '),
        ('IncidentResponse  ', 'acme/incidents/* ', '2 closed '),
        ('LogisticsAgent    ', 'acme/logistics/* ', '5 active '),
        ('NotificationSvc   ', 'acme/notify/*    ', '42/day  '),
    ]
    
    # Pulse animation: period of 4 seconds (8 frames in original, now 4s total)
    pulse_phase = (t % 4.0) / 4.0  # 0-1 over 4 seconds
    pulse = '(*)' if pulse_phase < 0.5 else '( )'
    
    for i, (aname, topic, detail) in enumerate(agents):
        done   = i < len(suites_done)
        ac     = G() if done else C()
        pk     = '[+]' if done else pulse
        res    = '[PASS]' if done else '[....]'
        res_cp = G() if done else D()
        
        row_num = screen_y + 3 + i
        put(buffer, row_num, screen_x, '│', B())
        
        col = screen_x + 1
        put(buffer, row_num, col, f' {pk} ', ac)
        col += 4
        put(buffer, row_num, col, f'{aname:<20}', ac)
        col += 20
        put(buffer, row_num, col, f'{topic:<18}', D())
        col += 18
        put(buffer, row_num, col, f'{detail:<12}', G() if done else D())
        col += 12
        put(buffer, row_num, col, res, res_cp)
        
        put(buffer, row_num, screen_x + monitor_content_w + 1, '│', B())

    # Divider after agents
    agent_section_end = screen_y + 3 + len(agents)
    put(buffer, agent_section_end, screen_x, '├' + '─'*(monitor_content_w) + '┤', B())

    # Event section header
    evts_header_y = agent_section_end + 1
    hdr2 = '  LIVE EVENT MESH'
    hdr2_padded = hdr2.ljust(monitor_content_w)
    put(buffer, evts_header_y, screen_x, '│' + hdr2_padded[:monitor_content_w] + '│', B())
    put(buffer, evts_header_y + 1, screen_x, '├' + '─'*(monitor_content_w) + '┤', B())
    
    evts = [
        ('acme/orders/created        ', 'OrderFulfillment'),
        ('acme/inventory/updated     ', 'IncidentResponse'),
        ('acme/logistics/ship-delayed', 'OrderFulfillment'),
        ('acme/suppliers/restock     ', 'InventoryMgmt   '),
        ('acme/incidents/created     ', 'IncidentResponse'),
        ('acme/orders/cancelled      ', 'OrderFulfillment'),
        ('acme/inventory/adjustment  ', 'InventoryMgmt   '),
        ('acme/payment/confirmed     ', 'OrderFulfillment'),
        ('acme/warehouse/allocated   ', 'InventoryMgmt   '),
        ('acme/customer/notified     ', 'OrderFulfillment'),
    ]
    
    max_event_rows = min(10, canvas_height - evts_header_y - 10)
    for i in range(max_event_rows):
        idx    = (int(t / 1.5) + i) % len(evts)  # scroll events every 1.5 seconds
        et, ea = evts[idx]
        age_cp = G() if i == 0 else D()
        
        event_content = f' >> {et} -> {ea}'
        event_padded = event_content[:monitor_content_w].ljust(monitor_content_w)
        
        event_row = evts_header_y + 2 + i
        put(buffer, event_row, screen_x, '│', B())
        put(buffer, event_row, screen_x + 1, event_padded[:monitor_content_w], age_cp)
        put(buffer, event_row, screen_x + monitor_content_w + 1, '│', B())
    
    # Monitor bottom screen edge
    screen_bottom = evts_header_y + 2 + max_event_rows
    put(buffer, screen_bottom, screen_x, '└' + '─'*(monitor_content_w) + '┘', B())
    
    # Monitor bezel bottom
    put(buffer, screen_bottom + 1, monitor_x, '║' + ' '*(monitor_content_w + 2) + '║', D())
    put(buffer, screen_bottom + 2, monitor_x, '╠' + '═'*(monitor_content_w + 2) + '╣', D())
    
    # Monitor stand
    stand_center = monitor_x + monitor_total_w // 2
    stand_y = screen_bottom + 3
    
    put(buffer, stand_y,     stand_center - 3, '══════', D())
    put(buffer, stand_y + 1, stand_center - 1, '║', D())
    put(buffer, stand_y + 2, stand_center - 5, '══════════', D())
    
    return buffer

# ---------------------------------------------------------------------------
# STATE + SCENE ROUTING
# ---------------------------------------------------------------------------
class State:
    def __init__(self):
        self.tick              = 0
        self.start_time        = time.time()
        self.suites_done       = []
        self.active_name       = None
        self.active_chks       = 0
        self.all_done          = False
        self.truck_collision_t = None

# Scene durations in seconds
SCENE_DURATION = [10.0, 30.0, 53.0, 80.0, 35.0]

def get_buf(state):
    """Get buffer for current scene based on elapsed time."""
    # Calculate elapsed time in seconds, scaled by playback speed
    elapsed = (time.time() - state.start_time) * PLAYBACK_SPEED
    
    acc = 0
    fns = [scene0, scene1, lambda lt: scene2(lt, state), scene3,
           lambda lt: scene4(lt, state.suites_done)]
    
    for i, scene_dur in enumerate(SCENE_DURATION):
        if elapsed < acc + scene_dur:
            # We're in scene i
            return fns[i](elapsed - acc)
        acc += scene_dur
    
    # Loop the last scene
    return scene4((elapsed - sum(SCENE_DURATION)) % SCENE_DURATION[4], state.suites_done)

# ---------------------------------------------------------------------------
# SCENE MESSAGE — drawn below the canvas
# ---------------------------------------------------------------------------
SCENE_MESSAGES = [
    ' [ Scene 1: Store Opening ]  Order Fulfillment tests starting...',
    ' [ Scene 2: Customers Arriving ]  Validating order pipeline...',
    ' [ Scene 3: Warehouse Ops ]  Inventory Management checks running...',
    ' [ Scene 4: Logistics ]  Incident Response checks running...',
    ' [ Scene 5: Command Center ]  Verifying full system...',
]

def draw_scene_message(stdscr, state, scr_h, scr_w):
    """Draw the scene title message one row below the canvas."""
    elapsed = (time.time() - state.start_time) * PLAYBACK_SPEED
    
    # Determine which scene we're in
    acc = 0
    scene_idx = 0
    for i, scene_dur in enumerate(SCENE_DURATION):
        if elapsed < acc + scene_dur:
            scene_idx = i
            break
        acc += scene_dur
    else:
        # Loop last scene
        scene_idx = len(SCENE_DURATION) - 1
    
    msg_row = canvas_row_offset + canvas_height + 1
    if msg_row < scr_h - 4:  # Leave room for status bar
        try:
            msg = SCENE_MESSAGES[scene_idx]
            stdscr.addstr(msg_row, 0, msg[:scr_w], curses.color_pair(G()))
        except (curses.error, IndexError):
            pass

# ---------------------------------------------------------------------------
# STATUS BAR  drawn below the canvas
# ---------------------------------------------------------------------------
SPIN = ['|', '/', '-', '\\']

def draw_status(stdscr, state, scr_h, scr_w):
    base  = canvas_row_offset + canvas_height + 3
    total = len(SUITES)
    done  = len(state.suites_done)

    if base + 3 >= scr_h:
        return

    # Spinner with 1 second period (scaled by playback speed)
    spin_phase = ((time.time() - state.start_time) * PLAYBACK_SPEED) % 1.0
    spin_idx = int(spin_phase / 0.25)  # 4 frames per second for spinner
    spin_ch = SPIN[spin_idx % 4] if not state.all_done else '*'
    spin_cp = curses.color_pair(G()) if not state.all_done else \
              curses.color_pair(Y()) | curses.A_BOLD
    active  = state.active_name or ('All done!' if state.all_done else 'Starting...')
    chk_str = f' ({state.active_chks} checks)' if state.active_name else ''
    cnt_str = f'{done}/{total}'
    try:
        stdscr.addstr(base, 0, spin_ch + ' ', spin_cp)
        stdscr.addstr(base, 2, (active + chk_str)[:scr_w-14], curses.color_pair(W_()))
        stdscr.addstr(base, scr_w - len(cnt_str) - 2, cnt_str, curses.color_pair(D()))
    except curses.error:
        pass

    bw     = scr_w - 4
    filled = int(bw * done / max(total, 1))
    bar    = '[' + '#'*filled + '-'*(bw-filled) + ']'
    bar_cp = curses.color_pair(G()) if state.all_done else curses.color_pair(B())
    try:
        stdscr.addstr(base+1, 1, bar[:scr_w-2], bar_cp)
    except curses.error:
        pass

    px = 1
    for name, passed in state.suites_done:
        short   = name.split()[0][:10]
        label   = (' + ' if passed else ' - ') + short + ' '
        pill_cp = (curses.color_pair(G()) | curses.A_REVERSE) if passed else \
                  (curses.color_pair(R()) | curses.A_REVERSE)
        try:
            if px + len(label) < scr_w - 2:
                stdscr.addstr(base+2, px, label, pill_cp)
        except curses.error:
            pass
        px += len(label) + 1

    if state.all_done and base+3 < scr_h:
        all_pass = all(p for _, p in state.suites_done)
        if all_pass:
            msg    = '  *** ALL TESTS PASSED  --  Grade: A+  ***  '
            msg_cp = curses.color_pair(G()) | curses.A_BOLD
        else:
            fails  = sum(1 for _, p in state.suites_done if not p)
            msg    = f'  *** {fails} SUITE(S) FAILED  --  Check output  ***  '
            msg_cp = curses.color_pair(R()) | curses.A_BOLD
        try:
            stdscr.addstr(base+3, 1, msg[:scr_w-2], msg_cp)
        except curses.error:
            pass

# ---------------------------------------------------------------------------
# CURSES MAIN
# ---------------------------------------------------------------------------
def curses_main(stdscr):
    global canvas_width, canvas_height, canvas_col_offset, canvas_row_offset

    curses.curs_set(0)
    curses.start_color()
    curses.use_default_colors()

    curses.init_pair(W_(), curses.COLOR_WHITE,  -1)
    curses.init_pair(G(),  curses.COLOR_GREEN,  -1)
    curses.init_pair(Y(),  curses.COLOR_YELLOW, -1)
    curses.init_pair(R(),  curses.COLOR_RED,    -1)
    curses.init_pair(C(),  curses.COLOR_CYAN,   -1)
    curses.init_pair(B(),  curses.COLOR_BLUE,   -1)
    curses.init_pair(D(),  curses.COLOR_WHITE,  -1)

    stdscr.nodelay(True)
    stdscr.keypad(True)

    state = State()

    threading.Thread(target=run_tests, daemon=True).start()

    while True:
        # Recalculate canvas size every frame so resizing works live
        scr_h, scr_w = stdscr.getmaxyx()
        status_rows  = 6  # scene message + 5 status bar rows

        canvas_width = max(MIN_CANVAS_WIDTH, scr_w - 2)
        canvas_height = max(MIN_CANVAS_HEIGHT, scr_h - status_rows - 1)

        canvas_col_offset = max(0, (scr_w - canvas_width) // 2)
        canvas_row_offset = 0

        # Drain event queue
        try:
            while True:
                ev = EVQ.get_nowait()
                if ev['type'] == 'suite_start':
                    state.active_name = ev['name']
                    state.active_chks = ev['checks']
                elif ev['type'] == 'suite_done':
                    state.suites_done.append((ev['name'], ev['passed']))
                    state.active_name = None
                    state.active_chks = 0
                elif ev['type'] == 'all_done':
                    state.all_done = True
        except queue.Empty:
            pass

        stdscr.erase()
        buffer = get_buf(state)
        render(stdscr, buffer)
        draw_scene_message(stdscr, state, scr_h, scr_w)
        draw_status(stdscr, state, scr_h, scr_w)
        stdscr.refresh()

        if stdscr.getch() in (ord('q'), ord('Q'), 27):
            break
        if state.all_done and ((time.time() - state.start_time) * PLAYBACK_SPEED) > sum(SCENE_DURATION) + 40:
            time.sleep(1.5)
            break

        time.sleep(FRAME_DURATION)

# ---------------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------------
def main():
    print('Starting Full Retail Day grading...')
    print('(Press q at any time to quit)\n')
    time.sleep(0.5)
    try:
        curses.wrapper(curses_main)
    except KeyboardInterrupt:
        pass
    print('\n' + '='*50)
    print('  ACME RETAIL  --  GRADING COMPLETE')
    print('='*50 + '\n')

if __name__ == '__main__':
    main()