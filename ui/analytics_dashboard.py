import sys, os, argparse, json, time
from datetime import datetime

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.ticker as mticker
from matplotlib.widgets import Slider, Button

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR     = os.path.join(BASE_DIR, "data")
OUTPUTS_DIR  = os.path.join(BASE_DIR, "outputs")
REPORT_DIR   = os.path.join(BASE_DIR, "report")
MOCK_OUT     = os.path.join(DATA_DIR, "mock_output.csv")
MOCK_SP      = os.path.join(DATA_DIR, "mock_spatial.csv")
MOCK_SANDS   = os.path.join(DATA_DIR, "mock_sands_map.csv")
REAL_OUT     = os.path.join(DATA_DIR, "simulation_output.csv")
REAL_SP      = os.path.join(DATA_DIR, "simulation_spatial.csv")
REAL_SANDS   = os.path.join(DATA_DIR, "sands_map.csv")
PARAMS_FILE  = os.path.join(DATA_DIR, "parameters.json")
STATUS_FILE  = os.path.join(DATA_DIR, "sim_status.json")
os.makedirs(OUTPUTS_DIR, exist_ok=True)
os.makedirs(REPORT_DIR,  exist_ok=True)

# ── Colours ───────────────────────────────────────────────────────────────────
BG_DEEP     = "#0a0a12"
BG_AX       = "#0d0d1a"
BORDER      = "#1e1e3a"
ACCENT_BLUE = "#4FC3F7"
FAST_COLORS = ["#FF4444", "#FF6B35", "#FF8C42", "#FFA500"]
SLOW_COLORS = ["#4FC3F7", "#29B6F6", "#0288D1", "#01579B"]
PRESET_COLORS = {"fresh":"#4ADE80","slight":"#FFB300",
                 "moderate":"#FF8C42","degraded":"#FF4444"}
PRESET_LABELS = {"fresh":"Fresh","slight":"Slightly Used",
                 "moderate":"Moderately Used","degraded":"Heavily Degraded"}
PRESETS_ORDER = ["fresh","slight","moderate","degraded"]
TEXT_TITLE  = "#ccccee"
TEXT_AXIS   = "#8888aa"
TEXT_TICK   = "#666688"
THRESH_AMB  = "#FFB300"
SC_RED      = "#FF4444"
SEI_GOLD    = "#FFD700"
SAND_SAFE   = "#00E5FF"
SAND_BRANCH = "#FF3333"
DEPLETE_COL = "#AA44FF"

# Column dicts
HEIGHT_FAST  = {p: f"{p}_fast"           for p in PRESETS_ORDER}
HEIGHT_SLOW  = {p: f"{p}_slow"           for p in PRESETS_ORDER}
RISK_FAST    = {p: f"risk_{p}_fast"      for p in PRESETS_ORDER}
RISK_SLOW    = {p: f"risk_{p}_slow"      for p in PRESETS_ORDER}
SPATIAL_FAST = {p: f"{p}_fast_profile"   for p in PRESETS_ORDER}
SPATIAL_SLOW = {p: f"{p}_slow_profile"   for p in PRESETS_ORDER}
SEI_COLS     = {p: f"sei_{p}"            for p in PRESETS_ORDER}

SC_THRESHOLD       = 78.0
RISK_THRESH_AMBER  = 40.0
RISK_THRESH_RED    = 70.0
CONC_DEPLETE       = 0.3


# ── Helpers ───────────────────────────────────────────────────────────────────

def style_ax(ax, title="", xlabel="", ylabel=""):
    ax.set_facecolor(BG_AX)
    ax.grid(True, color=BORDER, linewidth=0.4, alpha=0.8)
    ax.set_axisbelow(True)
    for s in ax.spines.values():
        s.set_edgecolor(BORDER); s.set_linewidth(0.7)
    ax.tick_params(colors=TEXT_TICK, labelsize=7, length=3)
    for lbl in ax.get_xticklabels() + ax.get_yticklabels():
        lbl.set_fontfamily("monospace"); lbl.set_color(TEXT_TICK)
    if title:
        ax.set_title(title, color=TEXT_TITLE, fontsize=8.5,
                     fontweight="normal", pad=10, fontfamily="monospace")
    if xlabel:
        ax.set_xlabel(xlabel, color=TEXT_AXIS, fontsize=7,
                      fontfamily="monospace", labelpad=4)
    if ylabel:
        ax.set_ylabel(ylabel, color=TEXT_AXIS, fontsize=7,
                      fontfamily="monospace", labelpad=4)


def risk_crossing(series, threshold, df):
    mask = series >= threshold
    if mask.any():
        return int(df.loc[mask.idxmax(), "cycle"])
    return None


def load_data(mock):
    out_f = MOCK_OUT  if mock else REAL_OUT
    sp_f  = MOCK_SP   if mock else REAL_SP
    sd_f  = MOCK_SANDS if mock else REAL_SANDS

    try:
        df_out = pd.read_csv(out_f)
    except Exception:
        df_out = pd.DataFrame({"cycle": np.arange(1, 201)})

    try:
        df_sp = pd.read_csv(sp_f)
    except Exception:
        df_sp = pd.DataFrame({"anode_x": np.linspace(0, 399, 100)})

    try:
        df_sands = pd.read_csv(sd_f)
    except Exception:
        # Generate a synthetic sands map so Chart 8 always renders
        rows = []
        for cr in range(1, 21):
            for tg_i in range(1, 21):
                tg = round(tg_i * 0.05, 2)
                tau = 3000.0 / (cr * (1 + tg * 2))
                rows.append({"charge_rate": cr, "temp_gradient": tg,
                             "branching_flag": 1 if tau < 900 else 0})
        df_sands = pd.DataFrame(rows)

    try:
        with open(PARAMS_FILE) as f:
            params = json.load(f)
    except Exception:
        params = {}

    return df_out, df_sp, df_sands, params


def get_params_mtime():
    try:
        return os.path.getmtime(PARAMS_FILE)
    except Exception:
        return 0


# ── Chart renderers ───────────────────────────────────────────────────────────

def render_c1(ax, df, max_cycle=None):
    """Dendrite Growth Curves."""
    ax.cla()
    if max_cycle:
        df = df[df["cycle"] <= max_cycle]
    cycles = df["cycle"].values
    for i, p in enumerate(PRESETS_ORDER):
        if HEIGHT_FAST[p] in df.columns:
            ax.plot(cycles, df[HEIGHT_FAST[p]], color=FAST_COLORS[i],
                    lw=1.1, label=f"{PRESET_LABELS[p]} (F)")
            ax.fill_between(cycles, df[HEIGHT_FAST[p]], alpha=0.04,
                            color=FAST_COLORS[i])
        if HEIGHT_SLOW[p] in df.columns:
            ax.plot(cycles, df[HEIGHT_SLOW[p]], color=SLOW_COLORS[i],
                    lw=1.1, ls="--", label=f"{PRESET_LABELS[p]} (S)")

    ax.axhline(SC_THRESHOLD, color=THRESH_AMB, lw=0.9, ls="--", alpha=0.75)
    ax.text(cycles[-1] * 0.02, SC_THRESHOLD + 1,
            f"{SC_THRESHOLD:.0f}% SC threshold",
            color=THRESH_AMB, fontsize=6, fontfamily="monospace")

    # SC crossings
    for i, p in enumerate(PRESETS_ORDER):
        if HEIGHT_FAST[p] in df.columns:
            fh = df[HEIGHT_FAST[p]].values
            idx = next((j for j, v in enumerate(fh) if v >= SC_THRESHOLD), None)
            if idx is not None:
                cx = cycles[idx]
                ax.axvline(cx, color=SC_RED, lw=0.5, ls=":", alpha=0.6)
                ax.text(cx + 1, 5, f"SC:{cx}",
                        color=SC_RED, fontsize=5,
                        fontfamily="monospace", rotation=90, va="bottom")

    ax.set_ylim(0, 115)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f%%"))
    ax.legend(loc="upper left", fontsize=5, ncol=4, framealpha=0.1,
              labelcolor=TEXT_TICK, prop={"family":"monospace","size":5})
    style_ax(ax, "Dendrite Growth Curves — Max Height", "Cycle", "Max Height")


def render_c2(ax, df, max_cycle=None):
    """Short-Circuit Risk Score."""
    ax.cla()
    if max_cycle:
        df = df[df["cycle"] <= max_cycle]
    cycles = df["cycle"].values
    for p in PRESETS_ORDER:
        color = PRESET_COLORS[p]
        if RISK_FAST[p] in df.columns:
            ax.plot(cycles, df[RISK_FAST[p]], color=color, lw=1.2,
                    label=PRESET_LABELS[p])
            ax.fill_between(cycles, df[RISK_FAST[p]], alpha=0.08, color=color)
        if RISK_SLOW[p] in df.columns:
            ax.plot(cycles, df[RISK_SLOW[p]], color=color, lw=0.7,
                    ls="--", alpha=0.45)

    for thresh, color, label in [
        (RISK_THRESH_AMBER, THRESH_AMB, "40"),
        (RISK_THRESH_RED,   SC_RED,     "70"),
    ]:
        ax.axhline(thresh, color=color, lw=0.8, ls="--", alpha=0.7)
        ax.text(cycles[-1] * 0.98, thresh + 1, label,
                color=color, fontsize=6, fontfamily="monospace", ha="right")

    ax.set_ylim(0, 115)
    ax.legend(loc="upper left", fontsize=6, ncol=2, framealpha=0.1,
              labelcolor=TEXT_TICK, prop={"family":"monospace","size":6})
    style_ax(ax, "Short-Circuit Risk Score", "Cycle", "Risk Score")


def render_c3(ax, df_sp, cycle_pct=1.0):
    """Anode Spatial Profile with SEI golden band."""
    ax.cla()
    x_pct = (df_sp["anode_x"] / df_sp["anode_x"].max()) * 100

    fast_col = SPATIAL_FAST["moderate"]
    slow_col = SPATIAL_SLOW["moderate"]

    if fast_col in df_sp.columns:
        fh = df_sp[fast_col].values * cycle_pct
        ax.fill_between(x_pct, fh, alpha=0.18, color=FAST_COLORS[0])
        ax.plot(x_pct, fh, color=FAST_COLORS[0], lw=1.3, label="Mod. Fast")
        pk = np.argmax(fh)
        ax.scatter([x_pct.iloc[pk]], [fh[pk]], color=FAST_COLORS[0], s=25, zorder=6)
        ax.annotate(f"Peak {x_pct.iloc[pk]:.0f}%",
                    xy=(x_pct.iloc[pk], fh[pk]),
                    xytext=(x_pct.iloc[pk]+3, fh[pk]+1),
                    color=FAST_COLORS[0], fontsize=6, fontfamily="monospace")

    if slow_col in df_sp.columns:
        sh = df_sp[slow_col].values * cycle_pct
        ax.plot(x_pct, sh, color=SLOW_COLORS[0], lw=1.3, ls="--", label="Mod. Slow")
        pk2 = np.argmax(sh)
        ax.scatter([x_pct.iloc[pk2]], [sh[pk2]], color=SLOW_COLORS[0], s=25, zorder=6)

    # SEI golden overlay
    if "sei_profile_fast" in df_sp.columns:
        sei_norm = df_sp["sei_profile_fast"].values / df_sp["sei_profile_fast"].max()
        max_h = df_sp[fast_col].max() * cycle_pct if fast_col in df_sp.columns else 80
        ax.fill_between(x_pct, max_h * sei_norm * 0.3, alpha=0.12, color=SEI_GOLD,
                        label="SEI thickness (rel.)")

    ax.set_xlim(0, 100)
    ax.xaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f%%"))
    ax.legend(loc="upper right", fontsize=5.5, framealpha=0.1,
              labelcolor=TEXT_TICK, prop={"family":"monospace","size":5.5})
    style_ax(ax, "Anode Spatial Profile", "Anode Position", "Mean Height (cells)")


def render_c4(ax, df):
    """Cycle-Life Comparison Bar Chart."""
    ax.cla()
    bars, labels, colors = [], [], []
    for p in reversed(PRESETS_ORDER):
        if RISK_FAST[p] in df.columns:
            fc = risk_crossing(df[RISK_FAST[p]], RISK_THRESH_RED, df) or int(df["cycle"].max())
            sc = risk_crossing(df[RISK_SLOW[p]], RISK_THRESH_RED, df) or int(df["cycle"].max())
            bars.extend([fc, sc])
            labels.extend([f"{PRESET_LABELS[p]} (F)", f"{PRESET_LABELS[p]} (S)"])
            colors.extend([FAST_COLORS[PRESETS_ORDER.index(p)],
                           SLOW_COLORS[PRESETS_ORDER.index(p)]])

    y = range(len(bars))
    bc = ax.barh(list(y), bars, color=colors, alpha=0.82, height=0.6)
    ax.set_yticks(list(y))
    ax.set_yticklabels(labels, fontsize=6, fontfamily="monospace")
    for bar, val in zip(bc, bars):
        ax.text(val + 1, bar.get_y() + bar.get_height() / 2,
                f" {val}", va="center", color=TEXT_TICK,
                fontsize=6, fontfamily="monospace")
    style_ax(ax, "Cycle Life — Cycles Until Risk > 70%", "Safe Cycles", "")


def render_c5(ax, df, max_cycle=None):
    """Degradation Acceleration."""
    ax.cla()
    if max_cycle:
        df = df[df["cycle"] <= max_cycle]
    cycles = df["cycle"].values

    for col, color, label in [
        (HEIGHT_FAST["moderate"], FAST_COLORS[0], "Fast rate"),
        (HEIGHT_SLOW["moderate"], SLOW_COLORS[0], "Slow rate"),
    ]:
        if col in df.columns:
            rate = np.gradient(df[col].values)
            kernel = np.ones(5) / 5
            rate = np.convolve(rate, kernel, mode="same")
            ax.plot(cycles, rate, color=color, lw=1.2, label=label)

            if color == FAST_COLORS[0]:
                thresh = np.mean(rate) + 0.5 * np.std(rate)
                ax.fill_between(cycles, rate, thresh,
                                where=(rate > thresh),
                                color=SC_RED, alpha=0.10,
                                label="Accel. zone")
                ax.axhline(thresh, color=THRESH_AMB, lw=0.7, ls=":", alpha=0.6)

    # Sand's Time crossing marker
    if "sand_crossed_cycle_fast" in df.columns:
        sc_val = int(df["sand_crossed_cycle_fast"].iloc[0])
        if sc_val > 0:
            ax.axvline(sc_val, color=SAND_BRANCH, lw=1.0, ls="--", alpha=0.8)
            ax.text(sc_val + 1, ax.get_ylim()[1] * 0.85,
                    "Branching onset", color=SAND_BRANCH,
                    fontsize=6, fontfamily="monospace", rotation=90, va="top")

    ax.legend(loc="upper right", fontsize=6, framealpha=0.1,
              labelcolor=TEXT_TICK, prop={"family":"monospace","size":6})
    style_ax(ax, "Degradation Acceleration", "Cycle", "dHeight/dCycle")


def render_c6(ax, df, max_cycle=None):
    """Ion Concentration Field Over Time."""
    ax.cla()
    if max_cycle:
        df = df[df["cycle"] <= max_cycle]
    cycles = df["cycle"].values

    for col, color, label in [
        ("conc_fast", FAST_COLORS[0], "Fast charge"),
        ("conc_slow", SLOW_COLORS[0], "Slow charge"),
    ]:
        if col in df.columns:
            ax.plot(cycles, df[col], color=color, lw=1.2, label=label)

    ax.axhline(CONC_DEPLETE, color=DEPLETE_COL, lw=0.9, ls="--", alpha=0.8)
    ax.fill_between(
        cycles,
        0, CONC_DEPLETE,
        alpha=0.08, color=DEPLETE_COL, label="Depletion zone"
    )
    ax.text(cycles[-1] * 0.02, CONC_DEPLETE + 0.02,
            "Depletion threshold — branching risk",
            color=DEPLETE_COL, fontsize=6, fontfamily="monospace")

    # Annotate first crossing
    if "conc_fast" in df.columns:
        below = df[df["conc_fast"] < CONC_DEPLETE]
        if not below.empty:
            cx = int(below.iloc[0]["cycle"])
            ax.axvline(cx, color=DEPLETE_COL, lw=0.6, ls=":", alpha=0.7)
            ax.text(cx + 1, 0.05, f"Dep. c{cx}",
                    color=DEPLETE_COL, fontsize=5, fontfamily="monospace",
                    rotation=90, va="bottom")

    ax.set_ylim(0, 1.1)
    ax.legend(loc="upper right", fontsize=6, framealpha=0.1,
              labelcolor=TEXT_TICK, prop={"family":"monospace","size":6})
    style_ax(ax, "Ion Concentration Field", "Cycle", "Mean Tip Concentration")


def render_c7(ax, df, max_cycle=None):
    """SEI Layer Thickness — dual Y axis."""
    # Remove any existing twinx axes from previous renders before clearing.
    # ax.cla() alone does NOT remove twinned axes; they stack up and hide content.
    fig = ax.get_figure()
    for other_ax in fig.axes:
        if other_ax is not ax and other_ax.get_shared_x_axes().joined(ax, other_ax):
            other_ax.remove()

    ax.cla()
    if max_cycle:
        df = df[df["cycle"] <= max_cycle]
    cycles = df["cycle"].values

    # Style ax BEFORE creating twinx so facecolor is set on the right axis
    style_ax(ax, "SEI Layer Thickness Over Cycles", "Cycle", "SEI Thickness (nm)")

    for p in PRESETS_ORDER:
        col = SEI_COLS[p]
        if col in df.columns:
            ax.plot(cycles, df[col], color=PRESET_COLORS[p],
                    lw=1.2, label=PRESET_LABELS[p])

    # High-resistance regime shading
    if "sei_moderate" in df.columns:
        crit = df["sei_moderate"].max() * 0.7
        ax.axhline(crit, color=SEI_GOLD, lw=0.8, ls="--", alpha=0.6)
        ax.fill_between(cycles, crit, df["sei_moderate"].max() * 1.05,
                        alpha=0.07, color=SEI_GOLD, label="High-resistance regime")

    ax.legend(loc="upper left", fontsize=5.5, framealpha=0.1,
              labelcolor=TEXT_TICK, prop={"family": "monospace", "size": 5.5})

    # Create twinx AFTER all primary axis plotting is done
    ax2 = ax.twinx()
    ax2.set_facecolor(BG_AX)
    for s in ax2.spines.values():
        s.set_edgecolor(BORDER)
    if "sei_moderate" in df.columns:
        li_loss = df["sei_moderate"] * 0.3
        ax2.plot(cycles, li_loss, color=SEI_GOLD, lw=0.8, ls=":", alpha=0.6)
        ax2.set_ylabel("Li loss est. (%)", color=SEI_GOLD,
                       fontsize=6, fontfamily="monospace")
        ax2.tick_params(colors=SEI_GOLD, labelsize=6)


def render_c8(ax, df_sands, params):
    """Sand's Time Heatmap — 2D operating envelope."""
    # Remove any colorbar axes from previous renders — plt.colorbar injects
    # new axes each call; they stack up visually if not cleaned first.
    fig = ax.get_figure()
    for other_ax in list(fig.axes):
        if getattr(other_ax, '_is_c8_colorbar', False):
            other_ax.remove()

    ax.cla()
    if df_sands is None or df_sands.empty:
        ax.text(0.5, 0.5, "mock_sands_map.csv not found",
                transform=ax.transAxes, ha="center", color=TEXT_AXIS,
                fontsize=9, fontfamily="monospace")
        style_ax(ax, "Sand's Time Threshold Map", "Charge Rate", "Temp. Gradient")
        return

    crs  = sorted(df_sands["charge_rate"].unique())
    tgs  = sorted(df_sands["temp_gradient"].unique())
    grid = np.zeros((len(tgs), len(crs)))
    for _, row in df_sands.iterrows():
        ci = crs.index(row["charge_rate"])
        ti = tgs.index(row["temp_gradient"])
        grid[ti, ci] = row["branching_flag"]

    cmap = matplotlib.colors.LinearSegmentedColormap.from_list(
        "sands", [SAND_SAFE, "#003311", "#220000", SAND_BRANCH], N=256)
    im = ax.imshow(grid, origin="lower", aspect="auto",
                   extent=[min(crs)-0.5, max(crs)+0.5,
                           min(tgs)-0.025, max(tgs)+0.025],
                   cmap=cmap, vmin=0, vmax=1)

    try:
        ax.contour(np.array(crs), np.array(tgs), grid,
                   levels=[0.5], colors=[TEXT_AXIS], linewidths=0.8, linestyles="--")
    except Exception:
        pass

    cur_cr = params.get("charge_rate", 6)
    cur_tg = params.get("temperature_gradient", 0.5)
    ax.scatter([cur_cr], [cur_tg], color="white", s=60, zorder=10,
               marker="o", linewidths=1.5, edgecolors=ACCENT_BLUE)
    ax.annotate("Current config", xy=(cur_cr, cur_tg),
                xytext=(cur_cr + 0.8, cur_tg + 0.03),
                color="white", fontsize=6, fontfamily="monospace",
                arrowprops=dict(arrowstyle="->", color="white", lw=0.8))

    # Use make_axes_locatable to create a fixed-size colorbar that does NOT
    # steal and re-inject space from ax on each render call.
    from mpl_toolkits.axes_grid1 import make_axes_locatable
    divider = make_axes_locatable(ax)
    cax = divider.append_axes("right", size="2%", pad=0.06)
    cax._is_c8_colorbar = True
    cax.set_facecolor(BG_AX)
    cb = fig.colorbar(im, cax=cax)
    cb.set_label("Branching (1=yes)", color=TEXT_AXIS,
                 fontsize=6, fontfamily="monospace")
    cb.ax.tick_params(colors=TEXT_TICK, labelsize=6)
    cb.ax._is_c8_colorbar = True

    style_ax(ax, "Sand's Time Threshold Map — Safe Operating Envelope",
             "Charge Rate (p/step)", "Temperature Gradient")


# ── Main Dashboard Class ──────────────────────────────────────────────────────

class Dashboard:

    def __init__(self, mock=True):
        self.mock         = mock
        self._last_mtime  = 0.0
        self._last_status = None
        self._cur_cycle   = None   # None = show all

        plt.style.use("dark_background")
        self.fig = plt.figure(figsize=(20, 26), facecolor=BG_DEEP)
        self.fig.patch.set_facecolor(BG_DEEP)

        # 5-row grid with more vertical breathing room
        self.gs = gridspec.GridSpec(
            5, 2,
            figure=self.fig,
            left=0.07, right=0.93,
            top=0.93, bottom=0.12,
            hspace=0.65, wspace=0.30,
        )

        self.ax = [
            self.fig.add_subplot(self.gs[0, 0]),   # C1
            self.fig.add_subplot(self.gs[0, 1]),   # C2
            self.fig.add_subplot(self.gs[1, 0]),   # C3
            self.fig.add_subplot(self.gs[1, 1]),   # C4
            self.fig.add_subplot(self.gs[2, 0]),   # C5
            self.fig.add_subplot(self.gs[2, 1]),   # C6
            self.fig.add_subplot(self.gs[3, :]),   # C7 full
            self.fig.add_subplot(self.gs[4, :]),   # C8 full
        ]

        # Header — title centred, timestamp on same line right-aligned
        mode = " [MOCK DATA]" if mock else ""
        self.title_txt = self.fig.text(
            0.50, 0.977,
            f"DENDRITE ENGINE — ANALYTICS DASHBOARD{mode}",
            color=ACCENT_BLUE, fontsize=11, fontfamily="monospace",
            fontweight="bold", va="top", ha="center")
        self.ts_txt = self.fig.text(
            0.93, 0.977, "", color=TEXT_AXIS, fontsize=7.5,
            fontfamily="monospace", va="top", ha="right")

        # Cycle scrubber
        self.ax_sl = self.fig.add_axes(
            [0.07, 0.065, 0.87, 0.018], facecolor=BG_AX)
        self.slider = Slider(self.ax_sl, "Cycle ", 1, 200,
                             valinit=200, valstep=1, color=ACCENT_BLUE)
        self.slider.label.set_color(TEXT_AXIS)
        self.slider.label.set_fontsize(8)
        self.slider.valtext.set_color(TEXT_AXIS)
        self.slider.on_changed(self._on_scrub)

        self.fig.text(0.07, 0.088,
                      "CYCLE SCRUBBER — drag to filter all time-series charts",
                      color=TEXT_AXIS, fontsize=7, fontfamily="monospace")

        # Export buttons
        ax_ec = self.fig.add_axes([0.07, 0.025, 0.12, 0.030])
        ax_er = self.fig.add_axes([0.21, 0.025, 0.12, 0.030])
        self.btn_charts = Button(ax_ec, "⬇ Export PNGs",
                                 color=BG_AX, hovercolor=BORDER)
        self.btn_report = Button(ax_er, "⬇ Export Report",
                                 color=BG_AX, hovercolor=BORDER)
        self.btn_charts.label.set_color(ACCENT_BLUE)
        self.btn_charts.label.set_fontfamily("monospace")
        self.btn_charts.label.set_fontsize(7)
        self.btn_report.label.set_color(THRESH_AMB)
        self.btn_report.label.set_fontfamily("monospace")
        self.btn_report.label.set_fontsize(7)
        self.btn_charts.on_clicked(lambda e: self.export_charts())
        self.btn_report.on_clicked(lambda e: self.export_report())

        # Load and render
        self.df_out, self.df_sp, self.df_sands, self.params = load_data(mock)
        self._update_slider_range()
        self.render_all()

        # Live polling — use Tk-native after() which works reliably on Windows
        # new_timer can miss callbacks when window is idle on TkAgg
        self._start_polling()

    def _start_polling(self):
        """Start Tk-native polling loop. More reliable than new_timer on Windows."""
        try:
            # Get the Tk root window from TkAgg backend
            self._tk_root = self.fig.canvas.manager.window
            self._tk_root.after(2000, self._tk_poll)
        except Exception:
            # Fallback to matplotlib timer if not TkAgg
            self._timer = self.fig.canvas.new_timer(interval=2000)
            self._timer.add_callback(self._poll)
            self._timer.start()

    def _tk_poll(self):
        """Called by Tk event loop every 2s — guaranteed to fire on Windows."""
        self._poll()
        try:
            self._tk_root.after(2000, self._tk_poll)
        except Exception:
            pass

    # ── Scrubber ──────────────────────────────────────────────────────────────

    def _on_scrub(self, val):
        self._cur_cycle = int(val)
        self._render_time_series()
        self.fig.canvas.draw_idle()

    def _update_slider_range(self):
        if not self.df_out.empty:
            mx = int(self.df_out["cycle"].max())
            self.slider.valmax = mx
            self.slider.set_val(mx)
            self._cur_cycle = mx

    # ── Render ────────────────────────────────────────────────────────────────

    def render_all(self):
        mc = self._cur_cycle
        render_c1(self.ax[0], self.df_out, mc)
        render_c2(self.ax[1], self.df_out, mc)
        render_c3(self.ax[2], self.df_sp,
                  cycle_pct=mc / max(self.df_out["cycle"].max(), 1) if mc else 1.0)
        render_c4(self.ax[3], self.df_out)
        render_c5(self.ax[4], self.df_out, mc)
        render_c6(self.ax[5], self.df_out, mc)
        render_c7(self.ax[6], self.df_out, mc)
        render_c8(self.ax[7], self.df_sands, self.params)
        self.ts_txt.set_text(
            f"LG M50 INR21700  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        self.fig.canvas.draw_idle()

    def _render_time_series(self):
        """Only re-render the cycle-dependent charts for fast scrubbing."""
        mc = self._cur_cycle
        render_c1(self.ax[0], self.df_out, mc)
        render_c2(self.ax[1], self.df_out, mc)
        render_c3(self.ax[2], self.df_sp,
                  cycle_pct=mc / max(self.df_out["cycle"].max(), 1) if mc else 1.0)
        render_c5(self.ax[4], self.df_out, mc)
        render_c6(self.ax[5], self.df_out, mc)
        render_c7(self.ax[6], self.df_out, mc)

    # ── Live poll: react to parameters.json changes ───────────────────────────

    def _poll(self):
        changed = False

        # Check parameters.json mtime
        mtime = get_params_mtime()
        if mtime != self._last_mtime:
            self._last_mtime = mtime
            self.df_out, self.df_sp, self.df_sands, self.params = \
                load_data(self.mock)
            self._update_slider_range()
            changed = True

        # Check sim_status.json
        try:
            status = {}
            if os.path.exists(STATUS_FILE):
                with open(STATUS_FILE) as f:
                    status = json.load(f)
            if status != self._last_status:
                self._last_status = status
                changed = True
        except Exception:
            pass

        if changed:
            self.render_all()

    # ── Export charts ─────────────────────────────────────────────────────────

    def export_charts(self):
        renders = [
            ("chart1_growth_curves",          render_c1,  (self.df_out,)),
            ("chart2_risk_scores",             render_c2,  (self.df_out,)),
            ("chart3_spatial_profile",         render_c3,  (self.df_sp,)),
            ("chart4_cycle_life_comparison",   render_c4,  (self.df_out,)),
            ("chart5_degradation_acceleration",render_c5,  (self.df_out,)),
            ("chart6_concentration_field",     render_c6,  (self.df_out,)),
            ("chart7_sei_thickness",           render_c7,  (self.df_out,)),
            ("chart8_sands_map",               render_c8,  (self.df_sands, self.params)),
        ]
        print("\nExporting charts...")
        for name, fn, args in renders:
            fig_e, ax_e = plt.subplots(figsize=(14, 8), facecolor=BG_DEEP)
            fig_e.patch.set_facecolor(BG_DEEP)
            fn(ax_e, *args)
            fig_e.tight_layout()
            path = os.path.join(OUTPUTS_DIR, f"{name}.png")
            fig_e.savefig(path, dpi=300, facecolor=BG_DEEP, bbox_inches="tight")
            plt.close(fig_e)
            print(f"  ✓ {name}.png")
        print("Export complete.")

    # ── Export report ─────────────────────────────────────────────────────────

    def export_report(self):
        df = self.df_out
        fast_c, slow_c = {}, {}
        for p in PRESETS_ORDER:
            fast_c[p] = risk_crossing(df[RISK_FAST[p]], RISK_THRESH_RED, df) \
                        if RISK_FAST[p] in df.columns else "N/A"
            slow_c[p] = risk_crossing(df[RISK_SLOW[p]], RISK_THRESH_RED, df) \
                        if RISK_SLOW[p] in df.columns else "N/A"

        # Fast vs slow ratio
        fm = fast_c.get("moderate")
        sm = slow_c.get("moderate")
        ratio = f"{round((sm-fm)/fm*100,1)}%" \
                if isinstance(fm, int) and isinstance(sm, int) and fm > 0 \
                else "N/A"

        # SEI at cycle 200
        sei_200 = round(float(df["sei_moderate"].iloc[-1]), 1) \
                  if "sei_moderate" in df.columns else "N/A"
        li_loss = round(sei_200 * 0.3, 1) if isinstance(sei_200, float) else "N/A"

        # Concentration depletion
        def dep_cycle(col):
            if col in df.columns:
                b = df[df[col] < CONC_DEPLETE]
                return int(b.iloc[0]["cycle"]) if not b.empty else "N/A (>200)"
            return "N/A"

        conc_fast_dep = dep_cycle("conc_fast")
        conc_slow_dep = dep_cycle("conc_slow")

        # Sand's crossing
        sand_fast = int(df["sand_crossed_cycle_fast"].iloc[0]) \
                    if "sand_crossed_cycle_fast" in df.columns else "N/A"
        sand_slow = int(df["sand_crossed_cycle_slow"].iloc[0]) \
                    if "sand_crossed_cycle_slow" in df.columns else "N/A"
        sand_slow = "N/A — not reached" if sand_slow == -1 else sand_slow

        # Spatial peaks
        if "anode_x" in self.df_sp.columns:
            xp = (self.df_sp["anode_x"] / self.df_sp["anode_x"].max()) * 100
            fast_pk = round(float(xp.iloc[np.argmax(
                self.df_sp.get(SPATIAL_FAST["moderate"],
                               pd.Series([0])).values)]), 1)
            slow_pk = round(float(xp.iloc[np.argmax(
                self.df_sp.get(SPATIAL_SLOW["moderate"],
                               pd.Series([0])).values)]), 1)
        else:
            fast_pk = slow_pk = "N/A"

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines = [
            "DENDRITE ENGINE — SIMULATION RESULTS SUMMARY",
            "=" * 45,
            f"Run date:          {now}",
            f"Target cell:       LG M50 INR21700",
            f"Simulation cycles: {int(df['cycle'].max())}",
            f"Ensemble runs:     {self.params.get('ensemble_runs', '—')}",
            f"Mode:              {'Mock data' if self.mock else 'Real simulation'}",
            "",
            "FAST CHARGE — cycles until risk > 70%",
            "-" * 45,
        ] + [
            f"  {PRESET_LABELS[p]:20s}: cycle {fast_c[p]}"
            for p in PRESETS_ORDER
        ] + [
            "",
            "SLOW CHARGE — cycles until risk > 70%",
            "-" * 45,
        ] + [
            f"  {PRESET_LABELS[p]:20s}: cycle {slow_c[p]}"
            for p in PRESETS_ORDER
        ] + [
            "",
            "SEI ANALYSIS",
            "-" * 45,
            f"  SEI thickness at cycle 200 (mod. fast): {sei_200} nm",
            f"  Cumulative Li loss estimate (mod. fast): {li_loss}%",
            "",
            "MASS TRANSPORT",
            "-" * 45,
            f"  Conc. depletion below 0.3 (fast charge): cycle {conc_fast_dep}",
            f"  Conc. depletion below 0.3 (slow charge): cycle {conc_slow_dep}",
            "",
            "SAND'S TIME",
            "-" * 45,
            f"  Branching onset cycle (fast charge): {sand_fast}",
            f"  Branching onset cycle (slow charge): {sand_slow}",
            "",
            "KEY FINDING",
            "-" * 45,
            f"  Fast charging reduces safe cycle life by {ratio}",
            f"  vs slow charging (moderately used battery).",
            "",
            f"  Peak degradation zone: {fast_pk}% from left (fast)",
            f"  Peak degradation zone: {slow_pk}% from left (slow)",
            "",
            "NOTE: Absolute counts carry calibration uncertainty.",
            "      Fast-vs-slow ratio is the robust scientific output.",
        ]

        path = os.path.join(REPORT_DIR, "simulation_summary.txt")
        with open(path, "w") as f:
            f.write("\n".join(lines))
        print("\n".join(lines))
        print(f"\n✓ Saved to {path}")


# ── Entry ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mock",   action="store_true", default=True,
                        help="Use mock CSV data")
    parser.add_argument("--export", action="store_true",
                        help="Export all charts and report, then exit")
    args = parser.parse_args()

    print(f"Dendrite Engine Dashboard — {'MOCK' if args.mock else 'REAL'} mode")
    dash = Dashboard(mock=args.mock)

    if args.export:
        dash.export_charts()
        dash.export_report()
        return

    plt.show()


if __name__ == "__main__":
    main()
