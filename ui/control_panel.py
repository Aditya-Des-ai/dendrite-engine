import tkinter as tk
from tkinter import ttk
import json, os
from datetime import datetime

# ── Windows DPI fix (must be before any Tk window) ────────────────────────────
try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        import ctypes
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARAMS_FILE = os.path.join(BASE_DIR, "data", "parameters.json")
STATUS_FILE = os.path.join(BASE_DIR, "data", "sim_status.json")

# ── Colours ───────────────────────────────────────────────────────────────────
BG_DEEP     = "#0a0a12"
BG_SURFACE  = "#0d0d1a"
BG_PANEL    = "#12121e"
BORDER      = "#1e1e3a"
ACCENT_BLUE = "#4FC3F7"
ACCENT_AMB  = "#FFB300"
DANGER_RED  = "#FF4444"
SUCCESS_GRN = "#4ADE80"
SEI_GOLD    = "#FFD700"
SAND_SAFE   = "#00E5FF"
SAND_BRANCH = "#FF3333"
TEXT_PRI    = "#ccccee"
TEXT_SEC    = "#8888aa"
TEXT_DIM    = "#666688"
SLIDER_TRO  = "#1a1a2e"
SLIDER_ACT  = "#7DD3F5"

# ── Preset bundles (v2 — 8 physics params each) ───────────────────────────────
PRESETS = {
    "Fresh": {
        "alpha": 0.15, "charge_rate": 3, "temperature_gradient": 0.20,
        "degradation_rate": 0.001, "sep_factor": 0.85, "edge_factor": 1.10,
        "seed_roughness": 0.05, "sei_growth_rate": 0.001,
        "battery_age_preset": "fresh",
    },
    "Slightly Used": {
        "alpha": 0.30, "charge_rate": 5, "temperature_gradient": 0.40,
        "degradation_rate": 0.002, "sep_factor": 0.70, "edge_factor": 1.20,
        "seed_roughness": 0.15, "sei_growth_rate": 0.002,
        "battery_age_preset": "slight",
    },
    "Moderately Used": {
        "alpha": 0.50, "charge_rate": 8, "temperature_gradient": 0.65,
        "degradation_rate": 0.003, "sep_factor": 0.55, "edge_factor": 1.30,
        "seed_roughness": 0.30, "sei_growth_rate": 0.003,
        "battery_age_preset": "moderate",
    },
    "Heavily Degraded": {
        "alpha": 0.75, "charge_rate": 12, "temperature_gradient": 0.85,
        "degradation_rate": 0.005, "sep_factor": 0.35, "edge_factor": 1.40,
        "seed_roughness": 0.55, "sei_growth_rate": 0.005,
        "battery_age_preset": "degraded",
    },
}

FAST_CR, FAST_TG = 12, 0.70
SLOW_CR, SLOW_TG = 3,  0.25

# ── I/O ───────────────────────────────────────────────────────────────────────

def load_params():
    try:
        if os.path.exists(PARAMS_FILE):
            with open(PARAMS_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_params(data):
    os.makedirs(os.path.dirname(PARAMS_FILE), exist_ok=True)
    with open(PARAMS_FILE, "w") as f:
        json.dump(data, f, indent=2)

def read_status():
    try:
        if os.path.exists(STATUS_FILE):
            with open(STATUS_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def write_status(data):
    os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
    with open(STATUS_FILE, "w") as f:
        json.dump(data, f)


# ── App ───────────────────────────────────────────────────────────────────────

class DendriteControlPanel(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("Dendrite Engine — Control Panel")
        self.configure(bg=BG_DEEP)
        self.minsize(480, 640)
        self.geometry("520x920")

        self._sim_running    = False
        self._sim_paused     = False
        self._active_preset  = None
        self._charge_profile = tk.StringVar(value="slow")
        self._slider_vars    = {}
        self._slider_labels  = {}
        self._preset_btns    = {}

        self._build_ui()
        self._load_from_file()
        self._poll()

    # ── Layout skeleton ───────────────────────────────────────────────────────

    def _build_ui(self):
        # Fixed header
        hdr = tk.Frame(self, bg=BG_DEEP, padx=18, pady=10)
        hdr.pack(fill=tk.X, side=tk.TOP)
        self._build_header(hdr)

        # Fixed status bar
        self._build_status_bar()

        # Scrollable body
        outer = tk.Frame(self, bg=BG_DEEP)
        outer.pack(fill=tk.BOTH, expand=True)

        self._canvas = tk.Canvas(outer, bg=BG_DEEP, highlightthickness=0)
        sb = ttk.Scrollbar(outer, orient="vertical", command=self._canvas.yview)
        self._sf = tk.Frame(self._canvas, bg=BG_DEEP, padx=18)
        self._sf.bind("<Configure>",
                      lambda e: self._canvas.configure(
                          scrollregion=self._canvas.bbox("all")))
        self._cwin = self._canvas.create_window(
            (0, 0), window=self._sf, anchor="nw")
        self._canvas.bind("<Configure>",
                          lambda e: self._canvas.itemconfig(
                              self._cwin, width=e.width))
        self._canvas.configure(yscrollcommand=sb.set)
        self._canvas.bind_all("<MouseWheel>",
            lambda e: self._canvas.yview_scroll(
                int(-1 * (e.delta / 120)), "units"))
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        self._build_presets(self._sf)
        self._build_sliders(self._sf)
        self._build_charge_toggle(self._sf)
        self._build_sands_panel(self._sf)
        self._build_buttons(self._sf)

    # ── Header ────────────────────────────────────────────────────────────────

    def _build_header(self, p):
        row = tk.Frame(p, bg=BG_DEEP)
        row.pack(fill=tk.X)
        tk.Label(row, text="DENDRITE ENGINE", bg=BG_DEEP, fg=ACCENT_BLUE,
                 font=("Courier New", 14, "bold"), anchor="w").pack(side=tk.LEFT)
        tk.Label(row, text="SIMULATION CONTROL", bg=BG_DEEP, fg=TEXT_DIM,
                 font=("Courier New", 9)).pack(side=tk.RIGHT)
        tk.Frame(p, bg=ACCENT_BLUE, height=1).pack(fill=tk.X, pady=(8, 0))

    # ── Section divider ───────────────────────────────────────────────────────

    def _sec(self, p, text):
        tk.Label(p, text=text, bg=BG_DEEP, fg=TEXT_DIM,
                 font=("Courier New", 8), anchor="w").pack(
                     fill=tk.X, pady=(12, 2))
        tk.Frame(p, bg=BORDER, height=1).pack(fill=tk.X, pady=(0, 6))

    def _bdr(self, w, c=BORDER):
        w.config(highlightthickness=1, highlightbackground=c, highlightcolor=c)

    # ── Preset buttons ────────────────────────────────────────────────────────

    def _build_presets(self, p):
        self._sec(p, "BATTERY AGE PRESET")
        row = tk.Frame(p, bg=BG_DEEP)
        row.pack(fill=tk.X, pady=(0, 4))
        for name in PRESETS:
            b = tk.Button(row, text=name.upper().replace(" ", "\n"),
                          bg=BG_PANEL, fg=TEXT_SEC,
                          activebackground=BG_PANEL, activeforeground=ACCENT_BLUE,
                          relief=tk.FLAT, bd=0,
                          font=("Courier New", 7, "bold"),
                          width=10, height=3, cursor="hand2",
                          command=lambda n=name: self._apply_preset(n))
            b.pack(side=tk.LEFT, padx=3, fill=tk.X, expand=True)
            self._bdr(b)
            self._preset_btns[name] = b

    def _apply_preset(self, name):
        self._active_preset = name
        for key, val in PRESETS[name].items():
            if key in self._slider_vars:
                self._slider_vars[key].set(val)
                self._slider_labels[key].config(text=self._fmt(key, val))
        for bn, btn in self._preset_btns.items():
            if bn == name:
                btn.config(fg=ACCENT_BLUE); self._bdr(btn, ACCENT_BLUE)
            else:
                btn.config(fg=TEXT_SEC);    self._bdr(btn)
        self._refresh_sands()
        self._push()

    # ── 10 Sliders ────────────────────────────────────────────────────────────

    def _build_sliders(self, p):
        self._sec(p, "SIMULATION PARAMETERS")
        specs = [
            ("alpha",               "Sticking Probability",   0.01, 1.00,  0.55, "",         "Electrolyte deposition aggressiveness"),
            ("charge_rate",         "Charge Rate",            1,    20,    6,    "p/step",   "Maps to current density via Faraday's Law"),
            ("temperature_gradient","Temperature Gradient",   0.0,  1.0,   0.50, "",         "Spatial heat intensity — hot center = faster growth"),
            ("num_cycles",          "Cycles to Simulate",     50,   500,   200,  "cycles",   "Each cycle = one charge event"),
            ("ensemble_runs",       "Ensemble Runs",          1,    100,   50,   "runs",     "Repeat runs averaged for stability"),
            ("degradation_rate",    "Degradation Rate",       0.000,0.010, 0.002,"per cycle","Electrolyte decay per cycle"),
            ("sep_factor",          "Separator Resistance",   0.1,  1.0,   0.65, "",         "Ion slowdown near cathode boundary (porosity)"),
            ("edge_factor",         "Edge Enhancement",       1.0,  2.0,   1.25, "",         "Extra ion flux at anode edges due to geometry"),
            ("seed_roughness",      "Nucleation Roughness",   0.0,  1.0,   0.20, "",         "Anode surface defect density — dendrite start sites"),
            ("sei_growth_rate",     "SEI Growth Rate",        0.000,0.010, 0.002,"per cycle","SEI layer thickening speed per cycle"),
        ]
        c = tk.Frame(p, bg=BG_DEEP)
        c.pack(fill=tk.X)
        for args in specs:
            self._make_slider(c, *args)

    def _make_slider(self, p, key, label, mn, mx, default, unit, desc):
        f = tk.Frame(p, bg=BG_PANEL, padx=10, pady=6)
        f.pack(fill=tk.X, pady=3)
        self._bdr(f)

        top = tk.Frame(f, bg=BG_PANEL)
        top.pack(fill=tk.X)
        tk.Label(top, text=label.upper(), bg=BG_PANEL, fg=TEXT_PRI,
                 font=("Courier New", 8, "bold"), anchor="w").pack(side=tk.LEFT)

        var = tk.DoubleVar(value=default)
        self._slider_vars[key] = var

        ro = tk.Label(top, text=self._fmt(key, default), bg=BG_PANEL,
                      fg=ACCENT_BLUE, font=("Courier New", 10, "bold"),
                      anchor="e", width=10)
        ro.pack(side=tk.RIGHT)
        self._slider_labels[key] = ro

        if unit:
            tk.Label(top, text=unit, bg=BG_PANEL, fg=TEXT_DIM,
                     font=("Courier New", 7)).pack(side=tk.RIGHT, padx=4)

        res = 0.001 if key in ("degradation_rate", "sei_growth_rate") else \
              1     if key in ("num_cycles", "ensemble_runs", "charge_rate") else \
              0.01

        tk.Scale(f, from_=mn, to=mx, orient=tk.HORIZONTAL,
                 variable=var, resolution=res, showvalue=False,
                 bg=BG_PANEL, fg=TEXT_DIM, troughcolor=SLIDER_TRO,
                 activebackground=SLIDER_ACT,
                 highlightthickness=0, bd=0, sliderlength=16, sliderrelief=tk.FLAT,
                 command=lambda v, k=key: self._on_slide(k, v)
                 ).pack(fill=tk.X, pady=2)

        tk.Label(f, text=desc, bg=BG_PANEL, fg=TEXT_DIM,
                 font=("Courier New", 7), anchor="w").pack(fill=tk.X)

    def _on_slide(self, key, val):
        self._slider_labels[key].config(text=self._fmt(key, val))
        if key in ("charge_rate", "temperature_gradient"):
            self._refresh_sands()
        self._push()

    # ── Charge toggle ─────────────────────────────────────────────────────────

    def _build_charge_toggle(self, p):
        self._sec(p, "CHARGE PROFILE")
        row = tk.Frame(p, bg=BG_DEEP)
        row.pack(fill=tk.X, pady=(0, 4))

        self._fast_btn = tk.Button(
            row, text="⚡  FAST CHARGE   15 min",
            bg=BG_PANEL, fg=TEXT_SEC,
            activebackground=ACCENT_BLUE, activeforeground=BG_DEEP,
            relief=tk.FLAT, bd=0, font=("Courier New", 8),
            height=2, cursor="hand2", command=self._fast)
        self._fast_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        self._bdr(self._fast_btn)

        self._slow_btn = tk.Button(
            row, text="🔋  SLOW CHARGE   60 min",
            bg=BG_PANEL, fg=TEXT_SEC,
            activebackground=ACCENT_BLUE, activeforeground=BG_DEEP,
            relief=tk.FLAT, bd=0, font=("Courier New", 8),
            height=2, cursor="hand2", command=self._slow)
        self._slow_btn.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._bdr(self._slow_btn)

    def _fast(self):
        self._charge_profile.set("fast")
        self._set_slider("charge_rate", FAST_CR)
        self._set_slider("temperature_gradient", FAST_TG)
        self._fast_btn.config(bg=ACCENT_BLUE, fg=BG_DEEP)
        self._bdr(self._fast_btn, ACCENT_BLUE)
        self._slow_btn.config(bg=BG_PANEL, fg=TEXT_SEC)
        self._bdr(self._slow_btn)
        self._refresh_sands()
        self._push()

    def _slow(self):
        self._charge_profile.set("slow")
        self._set_slider("charge_rate", SLOW_CR)
        self._set_slider("temperature_gradient", SLOW_TG)
        self._slow_btn.config(bg=ACCENT_BLUE, fg=BG_DEEP)
        self._bdr(self._slow_btn, ACCENT_BLUE)
        self._fast_btn.config(bg=BG_PANEL, fg=TEXT_SEC)
        self._bdr(self._fast_btn)
        self._refresh_sands()
        self._push()

    def _set_slider(self, key, val):
        if key in self._slider_vars:
            self._slider_vars[key].set(val)
            self._slider_labels[key].config(text=self._fmt(key, val))

    # ── Sand's Time panel ─────────────────────────────────────────────────────

    def _build_sands_panel(self, p):
        self._sec(p, "SAND'S TIME — BRANCHING ONSET PREDICTOR")
        f = tk.Frame(p, bg=BG_PANEL, padx=12, pady=10)
        f.pack(fill=tk.X, pady=(0, 4))
        self._bdr(f)

        r1 = tk.Frame(f, bg=BG_PANEL)
        r1.pack(fill=tk.X)
        tk.Label(r1, text="τ  =", bg=BG_PANEL, fg=TEXT_SEC,
                 font=("Courier New", 9)).pack(side=tk.LEFT)
        self._sand_tau = tk.Label(r1, text="—", bg=BG_PANEL, fg=SAND_SAFE,
                                  font=("Courier New", 11, "bold"))
        self._sand_tau.pack(side=tk.LEFT, padx=(6, 0))
        self._sand_step = tk.Label(r1, text="", bg=BG_PANEL, fg=TEXT_DIM,
                                   font=("Courier New", 8))
        self._sand_step.pack(side=tk.LEFT, padx=(14, 0))

        r2 = tk.Frame(f, bg=BG_PANEL)
        r2.pack(fill=tk.X, pady=(6, 0))
        self._sand_dot = tk.Label(r2, text="●", bg=BG_PANEL, fg=SAND_SAFE,
                                  font=("Courier New", 9))
        self._sand_dot.pack(side=tk.LEFT)
        self._sand_lbl = tk.Label(r2, text=" SAFE — rate below branching limit",
                                  bg=BG_PANEL, fg=SAND_SAFE, font=("Courier New", 8))
        self._sand_lbl.pack(side=tk.LEFT, padx=(4, 0))

    def _refresh_sands(self):
        params = load_params()
        tau = params.get("sand_time_seconds", None)
        if tau is None:
            cr  = float(self._slider_vars.get(
                "charge_rate", tk.DoubleVar(value=6)).get())
            tg  = float(self._slider_vars.get(
                "temperature_gradient", tk.DoubleVar(value=0.5)).get())
            tau = 3000.0 / max(cr * (1 + tg * 2), 0.01)

        cycle_dur = 900
        branching = tau < cycle_dur
        color = SAND_BRANCH if branching else SAND_SAFE
        step_str = f"→ branching at ~step {int(tau/cycle_dur*200)}" \
                   if branching else "→ no branching in 200 cycles"
        status = "⚠  BRANCHING INEVITABLE" if branching \
                 else "SAFE — rate below branching limit"

        try:
            self._sand_tau.config(text=f"{tau:.0f} s", fg=color)
            self._sand_step.config(text=step_str, fg=color)
            self._sand_dot.config(fg=color)
            self._sand_lbl.config(text=f" {status}", fg=color)
        except Exception:
            pass

    # ── Control buttons ───────────────────────────────────────────────────────

    def _build_buttons(self, p):
        self._sec(p, "SIMULATION CONTROL")
        row = tk.Frame(p, bg=BG_DEEP)
        row.pack(fill=tk.X, pady=(0, 20))

        self._run_btn = tk.Button(
            row, text="▶  RUN SIMULATION",
            bg=ACCENT_BLUE, fg=BG_DEEP,
            activebackground=SLIDER_ACT, activeforeground=BG_DEEP,
            relief=tk.FLAT, bd=0, font=("Courier New", 9, "bold"),
            height=2, cursor="hand2", command=self._on_run)
        self._run_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        self._pause_btn = tk.Button(
            row, text="⏸  PAUSE", bg=BG_PANEL, fg=TEXT_SEC,
            activebackground=BG_SURFACE, activeforeground=TEXT_PRI,
            relief=tk.FLAT, bd=0, font=("Courier New", 8),
            height=2, cursor="hand2", command=self._on_pause)
        self._pause_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        self._bdr(self._pause_btn)

        self._reset_btn = tk.Button(
            row, text="↺  RESET", bg=BG_PANEL, fg=TEXT_SEC,
            activebackground=BG_SURFACE, activeforeground=TEXT_PRI,
            relief=tk.FLAT, bd=0, font=("Courier New", 8),
            height=2, cursor="hand2", command=self._on_reset)
        self._reset_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        self._bdr(self._reset_btn)

        self._ens_btn = tk.Button(
            row, text="⚙  ENSEMBLE", bg=BG_PANEL, fg=TEXT_SEC,
            activebackground=BG_SURFACE, activeforeground=TEXT_PRI,
            relief=tk.FLAT, bd=0, font=("Courier New", 8),
            height=2, cursor="hand2", command=self._on_ensemble)
        self._ens_btn.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._bdr(self._ens_btn)

    # ── Status bar ────────────────────────────────────────────────────────────

    def _build_status_bar(self):
        bar = tk.Frame(self, bg=BG_PANEL, pady=5, padx=12)
        bar.pack(fill=tk.X, side=tk.BOTTOM)
        self._bdr(bar)

        self._st_dot   = tk.Label(bar, text="●", bg=BG_PANEL, fg=SUCCESS_GRN,
                                  font=("Courier New", 9))
        self._st_dot.pack(side=tk.LEFT)
        self._st_state = tk.Label(bar, text=" IDLE ", bg=BG_PANEL, fg=SUCCESS_GRN,
                                  font=("Courier New", 8, "bold"))
        self._st_state.pack(side=tk.LEFT)
        self._st_cyc  = tk.Label(bar, text="Cyc:—",  bg=BG_PANEL, fg=TEXT_DIM,
                                 font=("Courier New", 8))
        self._st_cyc.pack(side=tk.LEFT, padx=8)
        self._st_risk = tk.Label(bar, text="Risk:—", bg=BG_PANEL, fg=TEXT_DIM,
                                 font=("Courier New", 8))
        self._st_risk.pack(side=tk.LEFT, padx=8)
        self._st_sei  = tk.Label(bar, text="SEI:—",  bg=BG_PANEL, fg=TEXT_DIM,
                                 font=("Courier New", 8))
        self._st_sei.pack(side=tk.LEFT, padx=8)
        self._st_sand = tk.Label(bar, text="Sand:—", bg=BG_PANEL, fg=TEXT_DIM,
                                 font=("Courier New", 8))
        self._st_sand.pack(side=tk.LEFT, padx=8)
        self._st_time = tk.Label(bar, text="", bg=BG_PANEL, fg=TEXT_DIM,
                                 font=("Courier New", 7))
        self._st_time.pack(side=tk.RIGHT)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _on_run(self):
        if self._sim_running:
            return
        self._sim_running = True
        self._sim_paused  = False
        params = self._collect()
        save_params(params)
        write_status({
            "state": "running", "cycle": 0,
            "total": params.get("num_cycles", 200),
            "risk": 0.0, "height": 0,
            "sei_nm": 0.0, "sand_status": "SAFE"
        })
        self._run_btn.config(state=tk.DISABLED, bg=TEXT_DIM, fg=BG_DEEP)
        self._set_st("RUNNING", SUCCESS_GRN)

    def _on_pause(self):
        if not self._sim_running:
            return
        if not self._sim_paused:
            self._sim_paused = True
            write_status({**read_status(), "state": "paused"})
            self._pause_btn.config(text="▶  RESUME")
            self._set_st("PAUSED", ACCENT_AMB)
        else:
            self._sim_paused = False
            write_status({**read_status(), "state": "running"})
            self._pause_btn.config(text="⏸  PAUSE")
            self._set_st("RUNNING", SUCCESS_GRN)

    def _on_reset(self):
        self._sim_running = False
        self._sim_paused  = False
        write_status({"state": "idle", "cycle": 0, "total": 0,
                      "risk": 0.0, "height": 0,
                      "sei_nm": 0.0, "sand_status": "SAFE"})
        self._run_btn.config(state=tk.NORMAL, bg=ACCENT_BLUE, fg=BG_DEEP)
        self._pause_btn.config(text="⏸  PAUSE")
        self._set_st("IDLE", SUCCESS_GRN)
        for lbl, txt in [(self._st_cyc, "Cyc:—"),
                         (self._st_risk,"Risk:—"),
                         (self._st_sei, "SEI:—"),
                         (self._st_sand,"Sand:—")]:
            lbl.config(text=txt, fg=TEXT_DIM)

    def _on_ensemble(self):
        params = self._collect()
        params["mode"] = "ensemble"
        save_params(params)
        write_status({"state": "ensemble", "cycle": 0,
                      "total": params.get("num_cycles", 200),
                      "risk": 0.0, "height": 0,
                      "sei_nm": 0.0, "sand_status": "SAFE"})
        self._set_st("ENSEMBLE", ACCENT_AMB)

    def _set_st(self, text, color):
        self._st_dot.config(fg=color)
        self._st_state.config(text=f" {text} ", fg=color)

    # ── Param push (triggers dashboard reload via mtime) ──────────────────────

    def _push(self):
        try:
            save_params(self._collect())
        except Exception:
            pass

    def _collect(self):
        p = load_params()
        int_keys = ("num_cycles", "ensemble_runs", "charge_rate")
        for key, var in self._slider_vars.items():
            val = float(var.get())
            p[key] = int(val) if key in int_keys else round(val, 4)
        p["charge_profile"]     = self._charge_profile.get()
        p["battery_age_preset"] = PRESETS.get(
            self._active_preset or "Fresh", PRESETS["Fresh"]
        )["battery_age_preset"]
        return p

    # ── Poll sim_status.json every 1 s ────────────────────────────────────────

    def _poll(self):
        st = read_status()
        if st:
            state = st.get("state", "idle")
            cycle = st.get("cycle", 0)
            total = st.get("total", 0)
            risk  = float(st.get("risk", 0.0))
            sei   = float(st.get("sei_nm", 0.0))
            sand  = st.get("sand_status", "SAFE")

            if state in ("running", "ensemble"):
                self._set_st("RUNNING", SUCCESS_GRN)
                self._st_cyc.config(text=f"Cyc:{cycle}/{total}")
                rc = SUCCESS_GRN if risk < 40 else \
                     ACCENT_AMB  if risk < 70 else DANGER_RED
                self._st_risk.config(text=f"Risk:{risk:.1f}%", fg=rc)
                self._st_sei.config(text=f"SEI:{sei:.0f}nm", fg=SEI_GOLD)
                sc = SAND_BRANCH if "BRANCH" in sand else SAND_SAFE
                self._st_sand.config(
                    text=f"Sand:{'⚠' if 'BRANCH' in sand else 'SAFE'}",
                    fg=sc)
                if cycle >= total > 0:
                    self._sim_running = False
                    self._run_btn.config(
                        state=tk.NORMAL, bg=ACCENT_BLUE, fg=BG_DEEP)
                    self._set_st("COMPLETE", ACCENT_BLUE)

        self._refresh_sands()
        self._st_time.config(text=datetime.now().strftime("%H:%M:%S"))
        self.after(1000, self._poll)

    # ── Load from file ────────────────────────────────────────────────────────

    def _load_from_file(self):
        p = load_params()
        for key in self._slider_vars:
            if key in p and p[key] is not None:
                try:
                    self._slider_vars[key].set(float(p[key]))
                    self._slider_labels[key].config(
                        text=self._fmt(key, p[key]))
                except Exception:
                    pass
        profile = p.get("charge_profile", "slow")
        if profile == "fast":
            self._fast()
        else:
            self._slow()
        pm = {"fresh":"Fresh","slight":"Slightly Used",
              "moderate":"Moderately Used","degraded":"Heavily Degraded"}
        self._apply_preset(pm.get(p.get("battery_age_preset","fresh"),"Fresh"))

    # ── Format ────────────────────────────────────────────────────────────────

    def _fmt(self, key, val):
        val = float(val)
        if key in ("num_cycles", "ensemble_runs", "charge_rate"):
            return f"{int(val)}"
        elif key in ("degradation_rate", "sei_growth_rate"):
            return f"{val:.4f}"
        else:
            return f"{val:.3f}"


if __name__ == "__main__":
    app = DendriteControlPanel()
    app.mainloop()
