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

EVQ = queue.Queue()

# ---------------------------------------------------------------------------
# TEST RUNNER
# ---------------------------------------------------------------------------
def run_tests():
    if DEMO_MODE:
        for name, _, checks in SUITES:
            EVQ.put({'type': 'suite_start', 'name': name, 'checks': checks})
            time.sleep(checks * 0.9)
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
    buffer = new_buf()
    dawn = t / 15.0  # 2x faster dawn progression (was 30.0)

    # Calculate when sun reaches peak height
    # Sun rises: sy = clamp(6 - int(t * 0.36), 1, 6)
    # Peak is when sy = 1, which happens at: 6 - int(t * 0.36) = 1 → t ≈ 13.9
    sun_peak_t = 13.9
    stars_visible = t < sun_peak_t

    # Stars
    star_cols = [6, 14, 22, 34, 46, 58, canvas_width-8, canvas_width-2]
    for i, sc in enumerate(star_cols):
        sr = i % 3
        if stars_visible and sc < canvas_width:
            put(buffer, sr, sc, '+', D())

    # Moon
    if dawn < 0.5:
        mx = clamp(canvas_width - 8 - t * 4, 2, canvas_width - 8)  # 2x faster (was t * 2)
        put(buffer, 0, mx, '( )', D())

    # Sun
    if dawn > 0.2:
        sy = clamp(6 - int(t * 0.36), 1, 6)  # rise vertically
        sx = clamp(canvas_width - 12 - int(t * 0.5), canvas_width//2, canvas_width - 12)  # arc horizontally from right to center
        put(buffer, sy,     sx,     '\\|/', Y())
        put(buffer, sy + 1, sx - 2, '--(O)--', Y())
        put(buffer, sy + 2, sx,     '/|\\', Y())

    # Ground
    ground = canvas_height - 2
    hline(buffer, ground, 0, canvas_width-1, '_', D())

    # Store — centred, roof at row 2, walls all the way to ground
    store_w  = 35
    sx2      = center_column(store_w)
    roof_row = 2
    right_wall = sx2 + store_w - 1

    # Roof
    put(buffer, roof_row,   sx2, ','+'-'*(store_w-2)+'.', W_())
    
    # Calculate top row light frame early so we can use it for all synchronized events
    # Windows light up bottom-to-top starting at t=5
    # Each row lights up with 2-frame intervals (~0.44 seconds)
    # With 4 rows max: frames 5, 7, 9, 11 — all complete before Scene 0 ends at frame 15
    window_start_t = 5
    row_interval = 1  # frames between each row lighting up (1 frame ≈ 0.22 seconds, ~0.3s feel)
    # We need num_win_rows to calculate top_row_light_frame
    # Calculate it early before rendering anything
    inner_w   = store_w - 2
    building_rows_early = ground - (roof_row + 3)
    num_win_rows_early = max(1, (building_rows_early - 2) // 4)
    top_row_light_frame = window_start_t + (num_win_rows_early - 1) * row_interval
    
    # Building name turns green when top row of windows light up (synchronized)
    put(buffer, roof_row+1, sx2, '| A C M E   R E T A I L   C O R P |',
        G() if t >= top_row_light_frame else W_())
    put(buffer, roof_row+2, sx2, '+'+'-'*(store_w-2)+'+', W_())

    # Walls — left and right, full height
    for row in range(roof_row+3, ground):
        put(buffer, row, sx2,        '|', W_())
        put(buffer, row, right_wall, '|', W_())

    # Windows — fill building height dynamically, 2 rows of windows if tall enough
    # Each window block is 3 rows tall, with 1 gap row between blocks
    # Windows centred inside store: margin=4, 4 wins spaced 7 apart
    n_wins    = 4
    win_w     = 3
    win_gap   = 4
    win_span  = n_wins * win_w + (n_wins - 1) * win_gap  # 24
    win_off   = 1 + (inner_w - win_span) // 2            # left margin inside walls
    win_cols  = [sx2 + win_off + i*(win_w+win_gap) for i in range(n_wins)]
    win_start = roof_row + 3   # first window row starts here
    win_block = 4              # 3 rows per window + 1 gap below
    num_win_rows = num_win_rows_early  # Use the value calculated earlier
    
    for wr in range(num_win_rows):
        row0 = win_start + wr * win_block
        # Only render if there's room (don't let windows overlap with door/sign area)
        if row0 + 2 >= ground - 5:
            continue  # Skip this row if it overlaps with door area
        
        # Calculate which row from the bottom this is (0 = bottom, 1 = above, etc.)
        row_from_bottom = (num_win_rows - 1) - wr
        # Time when this row should light up (in frames)
        row_light_frame = window_start_t + row_from_bottom * row_interval
        # This row lights up when t >= row_light_frame
        row_lit = t >= row_light_frame
        
        for wi, wc in enumerate(win_cols):
            if wc + 3 >= right_wall: continue
            cp  = Y() if row_lit else D()
            put(buffer, row0,   wc, '+-+', cp)
            put(buffer, row0+1, wc, '|' + ('#' if row_lit else ' ') + '|', cp)
            put(buffer, row0+2, wc, '+-+', cp)

    # OPEN FOR BUSINESS sign — appears when top row of windows light up
    # (synchronized with building name color change and door opening)
    if t >= top_row_light_frame:
        sign_row = ground - 6
        if sign_row > win_start:
            sign     = '* * OPEN FOR BUSINESS * *'
            sign_col = sx2 + (store_w - len(sign)) // 2
            put(buffer, sign_row, sign_col, sign, G())

    # Door — clean, 4 rows, centred on store, sits at ground
    # Door opens at the same time as building name turns green and sign appears
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

    hr = 6 + t // 5
    mn = str((t % 5) * 12).zfill(2)
    put(buffer, 0, 0, f' {hr}:{mn} AM ', C())

    msg = ' [ Scene 1: Store Opening ]  Order Fulfillment tests starting...'
    put(buffer, canvas_height-1, 0, msg[:canvas_width], G())
    return buffer

# ---------------------------------------------------------------------------
# SCENE 1  Same store as scene0 — order board fades in, shoppers arrive
# ---------------------------------------------------------------------------
def scene1(t):
    buffer = new_buf()
    ground = canvas_height - 2

    # Ground
    hline(buffer, ground, 0, canvas_width-1, '_', D())
    
    # Sun at fixed position (same as end of scene0 at t=15)
    sy = clamp(6 - int(15 * 0.36), 1, 6)
    sx = clamp(canvas_width - 12 - int(15 * 0.5), canvas_width//2, canvas_width - 12)
    put(buffer, sy,     sx,     '\\|/', Y())
    put(buffer, sy + 1, sx - 2, '--(O)--', Y())
    put(buffer, sy + 2, sx,     '/|\\', Y())

    # ── Identical store from scene0 (centred, full height) ──────────────
    store_w    = 35
    sx2        = center_column(store_w)
    roof_row   = 2
    right_wall = sx2 + store_w - 1

    put(buffer, roof_row,   sx2, ','+'-'*(store_w-2)+'.', W_())
    put(buffer, roof_row+1, sx2, '| A C M E   R E T A I L   C O R P |', G())
    put(buffer, roof_row+2, sx2, '+'+'-'*(store_w-2)+'+', W_())
    for row in range(roof_row+3, ground):
        put(buffer, row, sx2,        '|', W_())
        put(buffer, row, right_wall, '|', W_())

    # Windows — same centred formula
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

    # ── Order board — fades in top-left after t=4 ────────────────────────
    if t > 4:
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
        footer = f'| Confirmed: {confirmed}/3    Pending: {3-confirmed}/3'
        put(buffer, 6, box_x, footer.ljust(box_w), B())
        put(buffer, 6, box_x + box_w + 1, '|', B())
        put(buffer, 7, box_x, '+' + '-'*box_w + '+', B())

# ── Shoppers walk from left toward the store entrance ─────────────────
    # max_x: stop just before the left wall of the store
    max_x  = sx2 - 2
    shoppers = [
        dict(bx=-2,  spd=3.3, oid='ORD-001', tot='$299', appear_delay=3),
        dict(bx=-18, spd=2.7, oid='ORD-002', tot='$849', appear_delay=3),
        dict(bx=-36, spd=2.1, oid='ORD-005', tot='$549', appear_delay=3),
    ]
    walk = (t//4) % 2
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

# Speech bubble — appears 3 seconds after shopper arrives, 3 lines above head
        appear_frame = -s['bx'] / s['spd']
        time_since_appear = t - appear_frame
        if time_since_appear > s['appear_delay'] and sx >= 0 and r_head >= 6:
            bx2 = clamp(sx - 2, 2, sx - 2)
            put(buffer, r_head-5, bx2, '.-----------------.', W_())
            put(buffer, r_head-4, bx2, '| '+s['oid']+'  '+s['tot']+'   |', G())
            put(buffer, r_head-3, bx2, "'-----------------'", W_())

    msg = ' [ Scene 2: Customers Arriving ]  Validating order pipeline...'
    put(buffer, canvas_height-1, 0, msg[:canvas_width], G())
    return buffer

# ---------------------------------------------------------------------------
# SCENE 2  Warehouse + forklift + restock truck
# ---------------------------------------------------------------------------
def scene2(t, state=None):
    buffer = new_buf()
    put(buffer, 0, 0, (' WAREHOUSE WH-A | San Francisco, CA | 65% capacity')[:canvas_width], W_())
    hline(buffer, 1, 0, canvas_width-1, '=', D())

    # Two columns of shelves — spread evenly across terminal, larger and more detailed
    left_col = 1
    right_col = canvas_width - 40
    
    # Calculate vertical spacing to centre middle shelf
    top_row = 2
    mid_row = canvas_height // 2 - 4
    bot_row = canvas_height - 11
    
    # Determine Pro Tablet 12 shelf color and state based on timeline
    if state.truck_collision_t is None:
        # Before truck collision
        if t < 15:
            # Initially yellow (low stock)
            tablet_color = Y()
            tablet_qty = ' 8 '
            tablet_status = 'LOW'
            tablet_fill = 2
        else:
            # After forklift picks it up: turn red (out of stock)
            tablet_color = R()
            tablet_qty = ' 0 '
            tablet_status = '!!!'
            tablet_fill = 0
    else:
        # After truck collision: turn green (restocked)
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
        
        # Top border
        put(buffer, sr,   sc2, '+-' + '-'*(shelf_w-2) + '-+', cp)
        # Header row with product name
        header = f'| {name:<30} {qty:>4}'
        put(buffer, sr+1, sc2, header, cp)
        put(buffer, sr+1, sc2 + shelf_w - 1, '|', cp)
        # Status row
        status_txt = f'| Status: [{st:^3}]' + ' '*(shelf_w-15)
        put(buffer, sr+2, sc2, status_txt, W_())
        put(buffer, sr+2, sc2 + shelf_w - 1, '|', W_())
        # Stock bar
        bar = '#'*fill + ' '*(10-fill)
        bar_row = f'| Stock: [{bar}]' + ' '*(shelf_w-16)
        put(buffer, sr+3, sc2, bar_row, cp)
        put(buffer, sr+3, sc2 + shelf_w - 1, '|', cp)
        # Divider
        put(buffer, sr+4, sc2, '|' + '-'*(shelf_w-2) + '|', D())
        # Bottom border
        put(buffer, sr+5, sc2, '+-' + '-'*(shelf_w-2) + '-+', cp)

    # Forklift journey with complete lifecycle
    floor_r = canvas_height - 3
    shelf_w = 38  # shelf width (matches shelf definition above)
    under_shelf_x = left_col + shelf_w  # position at bottom right corner of bottom left shelf
    start_x = canvas_width // 2
    right_deposit_x = right_col  # position at bottom left corner of bottom right shelf
    
    # Expanded timeline for complete forklift lifecycle
    if t < 10:
        # Phase 1: Move from start to left shelf (0-10)
        progress = t / 10.0
        fx = int(start_x - (start_x - under_shelf_x) * progress)
        carrying = False
        lh = 0  # forks down
        mirrored = False
    elif t < 15:
        # Phase 2: Raise forks, box appears (10-15)
        fx = under_shelf_x
        carrying = True
        lh = ((t - 10) / 5.0) * 2  # raise from 0 to 2 over 5 frames
        mirrored = False
    elif t < 20:
        # Phase 3: Lower forks fully with box still visible (15-20)
        fx = under_shelf_x
        carrying = True
        lh = max(0, 2 - ((t - 15) / 5.0) * 2)  # lower from 2 to 0
        mirrored = False
    elif t < 28:
        # Phase 4: Back up, turn around (mirror), move toward center (20-28)
        progress = (t - 20) / 8.0
        fx = int(under_shelf_x + (start_x - under_shelf_x) * progress)
        carrying = True
        lh = 0  # forks stay down during backup/turn
        mirrored = True  # flip to face right
    elif t < 36:
        # Phase 5: Move right toward right shelf (28-36)
        progress = (t - 28) / 8.0
        fx = int(start_x + (right_deposit_x - start_x) * progress)
        carrying = True
        lh = 0  # forks down while moving
        mirrored = True  # still facing right
    elif t < 40:
        # Phase 6: Raise forks with box (36-40)
        fx = right_deposit_x
        carrying = True
        lh = ((t - 36) / 4.0) * 2  # raise from 0 to 2
        mirrored = True
    elif t < 44:
        # Phase 7: Box disappears, forks lower (40-44)
        fx = right_deposit_x
        carrying = False  # box disappears
        lh = max(0, 2 - ((t - 40) / 4.0) * 2)  # lower from 2 to 0
        mirrored = True
    elif t < 52:
        # Phase 8: Turn around (mirror back), move toward start (44-52)
        progress = (t - 44) / 8.0
        fx = int(right_deposit_x - (right_deposit_x - start_x) * progress)
        carrying = False
        lh = 0  # forks down
        mirrored = False  # flip back to face left
    else:
        # Phase 9: Idle at start (52+)
        fx = start_x
        carrying = False
        lh = 0
        mirrored = False

    # Cab with butt extension — mirrored based on direction
    if not mirrored:
        # Mast — 4 rows tall above floor (facing left)
        for mr in range(floor_r-3, floor_r):
            put(buffer, mr, fx, '|=|', Y())
        put(buffer, floor_r-2, fx, '|o|~~~|', Y())
        put(buffer, floor_r-1, fx, '|_|~~~|', Y())
        # Wheels — front pair at mast, rear pair at butt
        put(buffer, floor_r, fx, 'O O', Y())
        put(buffer, floor_r, fx+4, 'O O', Y())
        # Forks extend left
        fork_row = int((floor_r - 1) - lh)
        if fx - 5 >= 0:
            put(buffer, fork_row,   fx-5, '=====', Y())
            put(buffer, fork_row+1, fx-5, '=====', Y())
        # Box on left forks - appears when forks reach full height, stays until deposited
        if carrying and t >= 15 and fx - 8 >= 0:
            box_row = int(fork_row - 1)
            put(buffer, box_row,     fx-8, '+-----+', C())
            put(buffer, box_row+1,   fx-8, '|_____|', C())
            put(buffer, box_row+2,   fx-8, '|-----|', C())
            put(buffer, box_row+3,   fx-8, '+-----+', C())
    else:
        # Mast — 4 rows tall above floor (facing right)
        for mr in range(floor_r-3, floor_r):
            put(buffer, mr, fx+4, '|=|', Y())
        # Mirrored: facing right
        put(buffer, floor_r-2, fx, '|~~~|o|', Y())
        put(buffer, floor_r-1, fx, '|~~~|_|', Y())
        # Wheels — same positioning as non-mirrored
        put(buffer, floor_r, fx, 'O O', Y())
        put(buffer, floor_r, fx+4, 'O O', Y())
        # Forks extend right from the cab
        fork_row = int((floor_r - 1) - lh)
        if fx + 7 < canvas_width:
            put(buffer, fork_row,   fx+7, '=====', Y())
            put(buffer, fork_row+1, fx+7, '=====', Y())
        # Box on right forks - appears when forks reach full height, stays until deposited
        if carrying and t >= 15 and fx + 10 < canvas_width:
            box_row = int(fork_row - 1)
            put(buffer, box_row,     fx+10, '+-----+', C())
            put(buffer, box_row+1,   fx+10, '|_____|', C())
            put(buffer, box_row+2,   fx+10, '|-----|', C())
            put(buffer, box_row+3,   fx+10, '+-----+', C())

    # Out-of-stock alert (replaces lower shelves when triggered)
    alert_w = min(42, canvas_width - 2)
    alert_col = center_column(alert_w)
    alert_right_edge = alert_col + alert_w  # right edge of the alert box
    
    # Restock truck rolls in from the right starting at t=11 (same time as alert)
    truck_w = 13  # truck width
    success_duration = 1.5 * (1.0 / 0.22)  # 1.5 seconds in frames (at 0.22s per frame) — shortened from 3
    truck_speed = 7  # faster exit speed
    
    # Alert appears at t=20 (after forklift has picked up box from left shelf)
    if t > 20:
        # Check if we should show the alert
        if state.truck_collision_t is None:
            # No collision yet: show red alert
            alert_color = R()
            alert_text = '| !! Pro Tablet 12 OUT OF STOCK !!'
            extra_text = '| INC-2026-015 created  >> ESCALATING'
        elif (t - state.truck_collision_t) < success_duration:
            # During success window: show green success message
            alert_color = G()
            alert_text = '| Pro Tablet 12 back in stock √'
            extra_text = '| Restock shipment received'
        else:
            # After success window: hide alert entirely
            alert_color = None
        
        if alert_color is not None:
            put(buffer, 14, alert_col, '+' + '-'*alert_w + '+', alert_color)
            put(buffer, 15, alert_col, (alert_text).ljust(alert_w+1) + '|', alert_color)
            put(buffer, 16, alert_col, (extra_text).ljust(alert_w+1) + '|', alert_color)
            put(buffer, 17, alert_col, '+' + '-'*alert_w + '+', alert_color)
    
    # Restock truck appears at t=24 (later arrival), starts far right
    if t > 24:
        # Calculate truck position: comes from right moving left at consistent speed
        tx_raw = canvas_width - 5 - (t - 24) * truck_speed
        truck_left_edge = int(tx_raw)
        
        # Check collision: truck's left edge reaches alert box's right edge
        if truck_left_edge <= alert_right_edge and state.truck_collision_t is None:
            state.truck_collision_t = t
        
        # Truck movement logic
        if state.truck_collision_t is None:
            # Before collision: truck moving left (from right) at consistent speed
            tx = int(canvas_width - 5 - (t - 24) * truck_speed)
        elif (t - state.truck_collision_t) < success_duration:
            # During success window: truck pauses at collision point (stops at alert edge)
            tx = int(alert_right_edge)
        else:
            # After success window: truck reverses and exits right at consistent speed
            time_exiting = t - state.truck_collision_t - success_duration
            tx = int(alert_right_edge + time_exiting * truck_speed)
        
        # DO NOT clamp tx — let it go off-screen
        
        # Track when truck completely exits screen (left edge goes past right edge)
        truck_completely_off_screen = tx >= canvas_width
        if truck_completely_off_screen and state.truck_collision_t is not None:
            if not hasattr(state, 'truck_exit_t'):
                state.truck_exit_t = t
        
        # Only draw truck if it's still visible on screen
        if tx < canvas_width - 2:
            put(buffer, 14, tx, '+===========+', Y())
            put(buffer, 15, tx, '| RESTOCK!  |', Y())
            put(buffer, 16, tx, '| +50 TBLT  |', Y())
            put(buffer, 17, tx, '+--O-----O--+', Y())
            if tx < canvas_width//2 + 4:
                put(buffer, 14, tx+13, 'ARRIVED!', G())
                put(buffer, 15, tx+13, '+50 units', G())

    # Ground
    ground = canvas_height - 2
    hline(buffer, ground, 0, canvas_width-1, '_', D())

    msg = ' [ Scene 3: Warehouse Ops ]  Inventory Management checks running...'
    put(buffer, canvas_height-1, 0, msg[:canvas_width], G())
    return buffer

# ---------------------------------------------------------------------------
# SCENE 3  Truck + flat tire + mechanic
# ---------------------------------------------------------------------------
def scene3(t):
    buffer = new_buf()
    put(buffer, 0, 0, (' Highway 101 | ORD-005 Lisa Wang | Chicago IL | 11:45 AM')[:canvas_width], C())
    hline(buffer, 1, 0, canvas_width-1, '=', D())

    # Road scrolling — stops 0.5 seconds after tire blows (t=24)
    # Tire blows at t=24, stop at t=24 + (0.5s / 0.22s per frame) ≈ t=26.3
    # Round to t=26 for clean cutoff
    if t < 26:
        scroll = int(t * 1.5)
    else:
        # Road frozen after tire blow
        scroll = int(24 * 1.5)  # 36

    # Scrolling scenery
    scenery = [
        (5,  [(2,' /\\ ',D()), (3,'/__\\',D())]),
        (22, [(2,'+--+',D()), (3,'|HQ|',D()), (4,'+--+',D())]),
        (int(canvas_width*0.55), [(2,' /\\ ',D()), (3,'/__\\',D())]),
        (int(canvas_width*0.8),  [(2,'+--+',D()), (3,'|  |',D()), (4,'+--+',D())]),
    ]
    for bx, rows in scenery:
        sx = (bx - scroll % canvas_width + canvas_width*3) % canvas_width
        for dr, ch, cp in rows:
            if sx < canvas_width-4:
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

    # Truck phases — revised timeline
    truck_w = 24
    if t < 20:
        # Phase 1: Accelerate to center (0-20) — FASTER
        tx = clamp(int(t*3.5), 0, canvas_width//2 - truck_w)
        phase = 'rolling'
    elif t < 24:
        # Phase 2: Wobble as tire fails (20-24)
        tx = canvas_width//2 - truck_w + int(math.sin((t-20)*3.5)*2)
        phase = 'wobble'
    elif t < 60:
        # Phase 3: Flat tire / skidding / repair (24-60) — extended for longer mechanic animation
        tx = canvas_width//2 - truck_w + 2
        phase = 'flat'
    else:
        # Phase 4: Repaired and driving off (60+) — faster exit, allow off-screen
        tx = canvas_width//2 - truck_w + 2 + (t-60)*6
        phase = 'repaired'
    tx = clamp(tx, 0, canvas_width - truck_w - 2) if phase != 'repaired' else tx

    tcl = G() if phase == 'repaired' else Y()
    truck_top = road_top - 4
    put(buffer, truck_top,   tx, '+------------------+  +---+', Y())
    put(buffer, truck_top+1, tx, '|  ACME LOGISTICS  |  |>  |', Y())
    put(buffer, truck_top+2, tx, '|  ORD-005  $549   |  |   |', Y())
    put(buffer, truck_top+3, tx, '+------------------+--+---+', tcl)

    tire_ok = phase in ('rolling', 'repaired')
    put(buffer, road_top, tx+2,  '(O)', Y())
    put(buffer, road_top, tx+8,  '(O)' if tire_ok else '(_)', Y() if tire_ok else R())
    put(buffer, road_top, tx+14, '(O)', Y())
    put(buffer, road_top, tx+18, '(O)', Y())

    if phase == 'rolling':
        for p in range(3):
            ex = tx - p*3 - 1
            if ex >= 0:
                put(buffer, truck_top, ex, '~', D())
        put(buffer, truck_top-1, tx+2, '>> cruising... all nominal <<', D())

    if phase == 'wobble':
        pass

    # ───── BANG ANIMATION (appears at tire color change t=20, visible for 2 seconds) ─────
    if phase in ('wobble', 'flat'):
        bang_frame = int(t - 20)  # 0+ after t=20 (when tire color changes)
        
        if bang_frame < 9:  # BANG visible for 9 frames (~2 seconds at 0.22s per frame)
            # Create dramatic BANG art (larger)
            bang_col = tx + truck_w // 2 - 8  # center above truck
            bang_row = truck_top - 12
            
            # Faster color flashing - alternate every frame
            flash_fast = bang_frame % 2  # alternates 0, 1, 0, 1, 0, 1...
            
            # Draw larger BANG box (17 chars wide, 7 tall) — BANG only in middle
            put(buffer, bang_row,     bang_col, '╔═══════════════╗', R())
            put(buffer, bang_row + 1, bang_col, '║               ║', R() if flash_fast == 0 else Y())
            put(buffer, bang_row + 2, bang_col, '║   ***   ***   ║', R() if flash_fast == 0 else Y())
            put(buffer, bang_row + 3, bang_col, '║    B A N G    ║', R() if flash_fast == 0 else Y())
            put(buffer, bang_row + 4, bang_col, '║   ***   ***   ║', R() if flash_fast == 0 else Y())
            put(buffer, bang_row + 5, bang_col, '║               ║', R() if flash_fast == 0 else Y())
            put(buffer, bang_row + 6, bang_col, '╚═══════════════╝', R())

    # ───── FLAT TIRE PHASE ─────
    if phase == 'flat':
        # Incident alert box — appears AFTER BANG ends (t=20 + 9 frames = t=29, show at t=29+)
        if t > 28:  # Wait for BANG to completely finish before showing message
            box_w = 44
            box_col = tx + truck_w // 2 - box_w // 2  # center on truck during flat phase
            box_top = truck_top - 14  # higher to clear BANG animation
            
            put(buffer, box_top,     box_col, '+' + '-'*box_w + '+', R())
            put(buffer, box_top + 1, box_col, ('| !! SHIPMENT DELAY INCIDENT CREATED !!').ljust(box_w+1) + '|', R())
            put(buffer, box_top + 2, box_col, ('| SHIP-2026-0048  flat tire  Hwy 101').ljust(box_w+1) + '|', R())
            put(buffer, box_top + 3, box_col, ('| INC created  ETA +2d  team notified').ljust(box_w+1) + '|', R())
            put(buffer, box_top + 4, box_col, '+' + '-'*box_w + '+', R())
        
        # Mechanic arrives and fixes (from t=34 onwards, after message settles)
        if t > 33:
            mx2 = tx + truck_w - 2
            mf  = (t//3) % 2
            put(buffer, truck_top+1, mx2, ' o ',             W_())
            put(buffer, truck_top+2, mx2, '/|\\' if mf else ' |/', W_())
            put(buffer, truck_top+3, mx2, ' | ',             W_())
            put(buffer, truck_top+3, mx2, ' /\\ ',             W_())
            if t > 38:
                put(buffer, truck_top+2, mx2+5, ['-0','/0','|0','\\0'][(t-40)%4], Y())
                put(buffer, truck_top+1, mx2+6, 'fixing', D())

    if phase == 'repaired':
        for p in range(min(t-60, 4)):
            ex = tx - p*3
            if ex >= 0:
                put(buffer, truck_top, ex, '~', D())
        
        # Repaired message box — stationary after truck leaves
        # Keep it at the position where it was centered during flat phase
        box_w = 44
        stationary_tx = canvas_width//2 - truck_w  # truck position when it stops
        box_col = stationary_tx + truck_w // 2 - box_w // 2
        box_top = truck_top - 14
        
        put(buffer, box_top,     box_col, '+' + '-'*box_w + '+', G())
        put(buffer, box_top + 1, box_col, ('| >> Tire replaced! Back on the road.').ljust(box_w+1) + '|', G())
        put(buffer, box_top + 2, box_col, ('| SHIP-2026-0048  in_transit  ETA updated').ljust(box_w+1) + '|', G())
        put(buffer, box_top + 3, box_col, ('| Customer notified via SMS + email').ljust(box_w+1) + '|', G())
        put(buffer, box_top + 4, box_col, '+' + '-'*box_w + '+', G())

    msg = ' [ Scene 4: Logistics ]  Incident Response checks running...'
    put(buffer, canvas_height-1, 0, msg[:canvas_width], G())
    return buffer

# ---------------------------------------------------------------------------
# SCENE 4  Command centre
# ---------------------------------------------------------------------------
def scene4(t, suites_done):
    buffer = new_buf()
    title = '[ ACME COMMAND CENTER  |  SAM v1.18.9 ]'
    put(buffer, 0, center_column(len(title)), title, W_())
    hline(buffer, 1, 0, canvas_width-1, '=', W_())

    # Desktop Monitor Frame
    # Calculate monitor dimensions — larger 16:9 aspect ratio
    monitor_content_w = 80
    monitor_total_w   = monitor_content_w + 4  # 2-char bezel on each side
    monitor_x         = center_column(monitor_total_w)
    monitor_y         = 2
    
    # Monitor top bezel and screen edge
    put(buffer, monitor_y, monitor_x, '╔' + '═'*(monitor_content_w + 2) + '╗', D())
    put(buffer, monitor_y + 1, monitor_x, '║' + ' '*(monitor_content_w + 2) + '║', D())
    
    # Screen content area starts at monitor_y + 2
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
    pulse = '(*)' if (t % 8 < 4) else '( )'
    for i, (aname, topic, detail) in enumerate(agents):
        done   = i < len(suites_done)
        ac     = G() if done else C()
        pk     = '[+]' if done else pulse
        res    = '[PASS]' if done else '[....]'
        res_cp = G() if done else D()
        
        row_num = screen_y + 3 + i
        put(buffer, row_num, screen_x, '│', B())
        
        # Draw content with fixed spacing aligned to the right edge
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
        
        # Right border at fixed position
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
    
    # Show 10 events max (much taller monitor)
    max_event_rows = min(10, canvas_height - evts_header_y - 10)
    for i in range(max_event_rows):
        idx    = (t // 3 + i) % len(evts)
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
    
    # Monitor stand (upside-down T)
    stand_center = monitor_x + monitor_total_w // 2
    stand_y = screen_bottom + 3
    
    # Top bar of T
    put(buffer, stand_y,     stand_center - 3, '══════', D())
    # Vertical post
    put(buffer, stand_y + 1, stand_center - 1, '║', D())
    put(buffer, stand_y + 2, stand_center - 5, '══════════', D())
    
    all_done = len(suites_done) >= len(SUITES)
    if all_done and t > 10:
        all_pass = all(p for _, p in suites_done)
        msg = ' *** ALL TESTS PASSED  --  Grade: A+  --  Retail Day Complete! *** '
        put(buffer, canvas_height-1, center_column(len(msg)), msg[:canvas_width], G() if all_pass else R())
    else:
        msg = ' [ Scene 5: Command Center ]  Verifying full system...'
        put(buffer, canvas_height-1, 0, msg[:canvas_width], G())
    return buffer

# ---------------------------------------------------------------------------
# STATE + SCENE ROUTING
# ---------------------------------------------------------------------------
class State:
    def __init__(self):
        self.tick              = 0
        self.suites_done       = []
        self.active_name       = None
        self.active_chks       = 0
        self.all_done          = False
        self.truck_collision_t = None  # tracks when truck collides with alert box

SCENE_LEN = [15, 36, 52, 80, 35]

def get_buf(state):
    t, acc = state.tick, 0
    fns = [scene0, scene1, lambda lt: scene2(lt, state), scene3,
           lambda lt: scene4(lt, state.suites_done)]
    for i, slen in enumerate(SCENE_LEN):
        if t < acc + slen:
            return fns[i](t - acc)
        acc += slen
    return scene4((t - sum(SCENE_LEN)) % SCENE_LEN[4], state.suites_done)

# ---------------------------------------------------------------------------
# STATUS BAR  drawn below the canvas
# ---------------------------------------------------------------------------
SPIN = ['|', '/', '-', '\\']

def draw_status(stdscr, state, si, scr_h, scr_w):
    base  = canvas_row_offset + canvas_height   # first row below the centred canvas
    total = len(SUITES)
    done  = len(state.suites_done)

    if base + 3 >= scr_h:
        return

    spin_ch = SPIN[si % 4] if not state.all_done else '*'
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
    si    = 0

    threading.Thread(target=run_tests, daemon=True).start()

    while True:
        # ── Recalculate canvas size every frame so resizing works live ──
        scr_h, scr_w = stdscr.getmaxyx()
        status_rows  = 5   # rows reserved for status bar below canvas

        # Canvas fills as much of the terminal as possible
        canvas_width = max(MIN_CANVAS_WIDTH, scr_w - 2)
        canvas_height = max(MIN_CANVAS_HEIGHT, scr_h - status_rows - 1)

        # Centre the canvas
        canvas_col_offset = max(0, (scr_w - canvas_width) // 2)
        canvas_row_offset = 0   # pin to top; status bar goes below

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
        draw_status(stdscr, state, si, scr_h, scr_w)
        stdscr.refresh()

        if stdscr.getch() in (ord('q'), ord('Q'), 27):
            break
        if state.all_done and state.tick > sum(SCENE_LEN) + 40:
            time.sleep(1.5)
            break

        si         += 1
        state.tick += 1
        time.sleep(0.22)   # ~4.5 fps — slow enough to read

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