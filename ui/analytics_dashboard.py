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
BG_DEEP      = "#0a0a12"
BG_AX        = "#0d0d1a"
BG_PANEL     = "#10101f"
BORDER       = "#1e1e3a"
ACCENT_BLUE  = "#4FC3F7"
ACCENT_CYAN  = "#00E5FF"
FAST_COLORS  = ["#FF4444", "#FF6B35", "#FF8C42", "#FFA500"]
SLOW_COLORS  = ["#4FC3F7", "#29B6F6", "#0288D1", "#01579B"]
PRESET_COLORS = {"fresh":"#4ADE80","slight":"#FFB300",
                 "moderate":"#FF8C42","degraded":"#FF4444"}
PRESET_LABELS = {"fresh":"Fresh","slight":"Slightly Used",
                 "moderate":"Moderately Used","degraded":"Heavily Degraded"}
PRESETS_ORDER = ["fresh","slight","moderate","degraded"]
TEXT_TITLE   = "#ccccee"
TEXT_AXIS    = "#8888aa"
TEXT_TICK    = "#666688"
TEXT_DIM     = "#444466"
THRESH_AMB   = "#FFB300"
SC_RED       = "#FF4444"
SEI_GOLD     = "#FFD700"
SAND_SAFE    = "#00E5FF"
SAND_BRANCH  = "#FF3333"
DEPLETE_COL  = "#AA44FF"
DROPDOWN_BG  = "#151528"
DROPDOWN_ACT = "#222244"

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

# ── Chart registry ────────────────────────────────────────────────────────────
CHART_NAMES = [
    "Dendrite Growth Curves — Max Height",
    "Short-Circuit Risk Score",
    "Anode Spatial Profile",
    "Cycle Life — Cycles Until Risk > 70%",
    "Degradation Acceleration",
    "Ion Concentration Field",
    "SEI Layer Thickness Over Cycles",
    "Sand's Time Threshold Map",
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def style_ax(ax, title="", xlabel="", ylabel=""):
    ax.set_facecolor(BG_AX)
    ax.grid(True, color=BORDER, linewidth=0.3, alpha=0.6)
    ax.set_axisbelow(True)
    for s in ax.spines.values():
        s.set_edgecolor(BORDER); s.set_linewidth(0.7)
    ax.tick_params(colors=TEXT_TICK, labelsize=9, length=4, pad=6)
    for lbl in ax.get_xticklabels() + ax.get_yticklabels():
        lbl.set_fontfamily("monospace"); lbl.set_color(TEXT_TICK)
    if title:
        ax.set_title(title, color=TEXT_TITLE, fontsize=13,
                     fontweight="bold", pad=18, fontfamily="monospace")
    if xlabel:
        ax.set_xlabel(xlabel, color=TEXT_AXIS, fontsize=10,
                      fontfamily="monospace", labelpad=8)
    if ylabel:
        ax.set_ylabel(ylabel, color=TEXT_AXIS, fontsize=10,
                      fontfamily="monospace", labelpad=8)


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
# Each renderer draws into a single ax that fills the main area.

def render_c1(ax, df, max_cycle=None):
    """Dendrite Growth Curves."""
    ax.cla()
    if max_cycle:
        df = df[df["cycle"] <= max_cycle]
    cycles = df["cycle"].values
    for i, p in enumerate(PRESETS_ORDER):
        if HEIGHT_FAST[p] in df.columns:
            ax.plot(cycles, df[HEIGHT_FAST[p]], color=FAST_COLORS[i],
                    lw=1.4, label=f"{PRESET_LABELS[p]} (F)")
            ax.fill_between(cycles, df[HEIGHT_FAST[p]], alpha=0.05,
                            color=FAST_COLORS[i])
        if HEIGHT_SLOW[p] in df.columns:
            ax.plot(cycles, df[HEIGHT_SLOW[p]], color=SLOW_COLORS[i],
                    lw=1.4, ls="--", label=f"{PRESET_LABELS[p]} (S)")

    ax.axhline(SC_THRESHOLD, color=THRESH_AMB, lw=0.9, ls="--", alpha=0.75)
    ax.text(cycles[-1] * 0.02, SC_THRESHOLD + 1,
            f"{SC_THRESHOLD:.0f}% SC threshold",
            color=THRESH_AMB, fontsize=8, fontfamily="monospace")

    for i, p in enumerate(PRESETS_ORDER):
        if HEIGHT_FAST[p] in df.columns:
            fh = df[HEIGHT_FAST[p]].values
            idx = next((j for j, v in enumerate(fh) if v >= SC_THRESHOLD), None)
            if idx is not None:
                cx = cycles[idx]
                ax.axvline(cx, color=SC_RED, lw=0.5, ls=":", alpha=0.6)
                ax.text(cx + 1, 5, f"SC:{cx}",
                        color=SC_RED, fontsize=7,
                        fontfamily="monospace", rotation=90, va="bottom")

    ax.set_ylim(0, 115)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f%%"))
    ax.legend(loc="upper left", fontsize=7, ncol=4, framealpha=0.1,
              labelcolor=TEXT_TICK, prop={"family":"monospace","size":7})
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
            ax.plot(cycles, df[RISK_FAST[p]], color=color, lw=1.4,
                    label=PRESET_LABELS[p])
            ax.fill_between(cycles, df[RISK_FAST[p]], alpha=0.08, color=color)
        if RISK_SLOW[p] in df.columns:
            ax.plot(cycles, df[RISK_SLOW[p]], color=color, lw=0.8,
                    ls="--", alpha=0.45)

    for thresh, color, label in [
        (RISK_THRESH_AMBER, THRESH_AMB, "40"),
        (RISK_THRESH_RED,   SC_RED,     "70"),
    ]:
        ax.axhline(thresh, color=color, lw=0.8, ls="--", alpha=0.7)
        ax.text(cycles[-1] * 0.98, thresh + 1, label,
                color=color, fontsize=8, fontfamily="monospace", ha="right")

    ax.set_ylim(0, 115)
    ax.legend(loc="upper left", fontsize=7, ncol=2, framealpha=0.1,
              labelcolor=TEXT_TICK, prop={"family":"monospace","size":7})
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
        ax.plot(x_pct, fh, color=FAST_COLORS[0], lw=1.5, label="Mod. Fast")
        pk = np.argmax(fh)
        ax.scatter([x_pct.iloc[pk]], [fh[pk]], color=FAST_COLORS[0], s=35, zorder=6)
        ax.annotate(f"Peak {x_pct.iloc[pk]:.0f}%",
                    xy=(x_pct.iloc[pk], fh[pk]),
                    xytext=(x_pct.iloc[pk]+3, fh[pk]+1),
                    color=FAST_COLORS[0], fontsize=8, fontfamily="monospace")

    if slow_col in df_sp.columns:
        sh = df_sp[slow_col].values * cycle_pct
        ax.plot(x_pct, sh, color=SLOW_COLORS[0], lw=1.5, ls="--", label="Mod. Slow")
        pk2 = np.argmax(sh)
        ax.scatter([x_pct.iloc[pk2]], [sh[pk2]], color=SLOW_COLORS[0], s=35, zorder=6)

    if "sei_profile_fast" in df_sp.columns:
        sei_norm = df_sp["sei_profile_fast"].values / df_sp["sei_profile_fast"].max()
        max_h = df_sp[fast_col].max() * cycle_pct if fast_col in df_sp.columns else 80
        ax.fill_between(x_pct, max_h * sei_norm * 0.3, alpha=0.12, color=SEI_GOLD,
                        label="SEI thickness (rel.)")

    ax.set_xlim(0, 100)
    ax.xaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f%%"))
    ax.legend(loc="upper right", fontsize=7, framealpha=0.1,
              labelcolor=TEXT_TICK, prop={"family":"monospace","size":7})
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
    ax.set_yticklabels(labels, fontsize=8, fontfamily="monospace")
    for bar, val in zip(bc, bars):
        ax.text(val + 1, bar.get_y() + bar.get_height() / 2,
                f" {val}", va="center", color=TEXT_TICK,
                fontsize=8, fontfamily="monospace")
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
            ax.plot(cycles, rate, color=color, lw=1.4, label=label)

            if color == FAST_COLORS[0]:
                thresh = np.mean(rate) + 0.5 * np.std(rate)
                ax.fill_between(cycles, rate, thresh,
                                where=(rate > thresh),
                                color=SC_RED, alpha=0.10,
                                label="Accel. zone")
                ax.axhline(thresh, color=THRESH_AMB, lw=0.7, ls=":", alpha=0.6)

    if "sand_crossed_cycle_fast" in df.columns:
        sc_val = int(df["sand_crossed_cycle_fast"].iloc[0])
        if sc_val > 0:
            ax.axvline(sc_val, color=SAND_BRANCH, lw=1.0, ls="--", alpha=0.8)
            ax.text(sc_val + 1, ax.get_ylim()[1] * 0.85,
                    "Branching onset", color=SAND_BRANCH,
                    fontsize=8, fontfamily="monospace", rotation=90, va="top")

    ax.legend(loc="upper right", fontsize=7, framealpha=0.1,
              labelcolor=TEXT_TICK, prop={"family":"monospace","size":7})
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
            ax.plot(cycles, df[col], color=color, lw=1.4, label=label)

    ax.axhline(CONC_DEPLETE, color=DEPLETE_COL, lw=0.9, ls="--", alpha=0.8)
    ax.fill_between(
        cycles,
        0, CONC_DEPLETE,
        alpha=0.08, color=DEPLETE_COL, label="Depletion zone"
    )
    ax.text(cycles[-1] * 0.02, CONC_DEPLETE + 0.02,
            "Depletion threshold — branching risk",
            color=DEPLETE_COL, fontsize=8, fontfamily="monospace")

    if "conc_fast" in df.columns:
        below = df[df["conc_fast"] < CONC_DEPLETE]
        if not below.empty:
            cx = int(below.iloc[0]["cycle"])
            ax.axvline(cx, color=DEPLETE_COL, lw=0.6, ls=":", alpha=0.7)
            ax.text(cx + 1, 0.05, f"Dep. c{cx}",
                    color=DEPLETE_COL, fontsize=7, fontfamily="monospace",
                    rotation=90, va="bottom")

    ax.set_ylim(0, 1.1)
    ax.legend(loc="upper right", fontsize=7, framealpha=0.1,
              labelcolor=TEXT_TICK, prop={"family":"monospace","size":7})
    style_ax(ax, "Ion Concentration Field", "Cycle", "Mean Tip Concentration")


def render_c7(ax, df, max_cycle=None):
    """SEI Layer Thickness — dual Y axis."""
    fig = ax.get_figure()
    for other_ax in list(fig.axes):
        if other_ax is not ax and hasattr(other_ax, '_is_sei_twin') and other_ax._is_sei_twin:
            other_ax.remove()

    ax.cla()
    if max_cycle:
        df = df[df["cycle"] <= max_cycle]
    cycles = df["cycle"].values

    style_ax(ax, "SEI Layer Thickness Over Cycles", "Cycle", "SEI Thickness (nm)")

    for p in PRESETS_ORDER:
        col = SEI_COLS[p]
        if col in df.columns:
            ax.plot(cycles, df[col], color=PRESET_COLORS[p],
                    lw=1.4, label=PRESET_LABELS[p])

    if "sei_moderate" in df.columns:
        crit = df["sei_moderate"].max() * 0.7
        ax.axhline(crit, color=SEI_GOLD, lw=0.8, ls="--", alpha=0.6)
        ax.fill_between(cycles, crit, df["sei_moderate"].max() * 1.05,
                        alpha=0.07, color=SEI_GOLD, label="High-resistance regime")

    ax.legend(loc="upper left", fontsize=7, framealpha=0.1,
              labelcolor=TEXT_TICK, prop={"family": "monospace", "size": 7})

    ax2 = ax.twinx()
    ax2._is_sei_twin = True
    ax2.set_facecolor(BG_AX)
    for s in ax2.spines.values():
        s.set_edgecolor(BORDER)
    if "sei_moderate" in df.columns:
        li_loss = df["sei_moderate"] * 0.3
        ax2.plot(cycles, li_loss, color=SEI_GOLD, lw=0.8, ls=":", alpha=0.6)
        ax2.set_ylabel("Li loss est. (%)", color=SEI_GOLD,
                       fontsize=8, fontfamily="monospace")
        ax2.tick_params(colors=SEI_GOLD, labelsize=8)


def render_c8(ax, df_sands, params):
    """Sand's Time Heatmap — 2D operating envelope."""
    fig = ax.get_figure()
    for other_ax in list(fig.axes):
        if getattr(other_ax, '_is_c8_colorbar', False):
            other_ax.remove()

    ax.cla()
    if df_sands is None or df_sands.empty:
        ax.text(0.5, 0.5, "mock_sands_map.csv not found",
                transform=ax.transAxes, ha="center", color=TEXT_AXIS,
                fontsize=12, fontfamily="monospace")
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
    ax.scatter([cur_cr], [cur_tg], color="white", s=80, zorder=10,
               marker="o", linewidths=1.5, edgecolors=ACCENT_BLUE)
    ax.annotate("Current config", xy=(cur_cr, cur_tg),
                xytext=(cur_cr + 0.8, cur_tg + 0.03),
                color="white", fontsize=8, fontfamily="monospace",
                arrowprops=dict(arrowstyle="->", color="white", lw=0.8))

    from mpl_toolkits.axes_grid1 import make_axes_locatable
    divider = make_axes_locatable(ax)
    cax = divider.append_axes("right", size="2%", pad=0.06)
    cax._is_c8_colorbar = True
    cax.set_facecolor(BG_AX)
    cb = fig.colorbar(im, cax=cax)
    cb.set_label("Branching (1=yes)", color=TEXT_AXIS,
                 fontsize=8, fontfamily="monospace")
    cb.ax.tick_params(colors=TEXT_TICK, labelsize=8)
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
        self._active_idx  = 0      # Index into CHART_NAMES

        plt.style.use("dark_background")
        self.fig = plt.figure(figsize=(18, 11), facecolor=BG_DEEP)
        self.fig.patch.set_facecolor(BG_DEEP)

        # Load data
        self.df_out, self.df_sp, self.df_sands, self.params = load_data(mock)

        # ── Layout ────────────────────────────────────────────────────────
        self.ax_main = self.fig.add_axes(
            [0.08, 0.18, 0.88, 0.68], facecolor=BG_AX)

        # ── Header ───────────────────────────────────────────────────────
        mode = " [MOCK DATA]" if mock else ""
        self.title_txt = self.fig.text(
            0.50, 0.975,
            f"DENDRITE ENGINE — DATA EXPLORER{mode}",
            color=ACCENT_BLUE, fontsize=14, fontfamily="monospace",
            fontweight="bold", va="top", ha="center")
        self.ts_txt = self.fig.text(
            0.96, 0.975, "", color=TEXT_AXIS, fontsize=8,
            fontfamily="monospace", va="top", ha="right")

        # ── Dropdown selector ────────────────────────────────────────────
        self._dropdown_ax = self.fig.add_axes(
            [0.08, 0.915, 0.50, 0.022], facecolor=DROPDOWN_BG)
        for s in self._dropdown_ax.spines.values():
            s.set_edgecolor(BORDER); s.set_linewidth(0.8)
        self._dropdown_ax.set_xticks([])
        self._dropdown_ax.set_yticks([])

        self._sel_text = self._dropdown_ax.text(
            0.02, 0.5, f"▼  {CHART_NAMES[self._active_idx]}",
            color=ACCENT_CYAN, fontsize=9, fontfamily="monospace",
            fontweight="bold", va="center", ha="left",
            transform=self._dropdown_ax.transAxes)

        self.fig.text(0.08, 0.953,
                      "CHART VIEW",
                      color=TEXT_DIM, fontsize=7.5, fontfamily="monospace",
                      fontweight="bold")

        # ── Chart index indicator ────────────────────────────────────────
        self._idx_text = self.fig.text(
            0.96, 0.93, f"1 / {len(CHART_NAMES)}",
            color=TEXT_DIM, fontsize=9, fontfamily="monospace",
            ha="right")

        # ── Cycle scrubber ───────────────────────────────────────────────
        self.ax_sl = self.fig.add_axes(
            [0.08, 0.085, 0.88, 0.022], facecolor=BG_AX)
        max_cyc = int(self.df_out["cycle"].max()) if not self.df_out.empty else 200
        self.slider = Slider(self.ax_sl, "Cycle ", 1, max_cyc,
                             valinit=max_cyc, valstep=1, color=ACCENT_BLUE)
        self.slider.label.set_color(TEXT_AXIS)
        self.slider.label.set_fontsize(9)
        self.slider.label.set_fontfamily("monospace")
        self.slider.valtext.set_color(TEXT_AXIS)
        self.slider.valtext.set_fontfamily("monospace")
        self.slider.on_changed(self._on_scrub)
        self._cur_cycle = max_cyc

        self.fig.text(0.08, 0.115,
                      "CYCLE SCRUBBER — drag to set max cycle",
                      color=TEXT_DIM, fontsize=7.5, fontfamily="monospace")

        # ── Export buttons ───────────────────────────────────────────────
        ax_ec = self.fig.add_axes([0.08, 0.025, 0.14, 0.035])
        ax_er = self.fig.add_axes([0.24, 0.025, 0.14, 0.035])
        self.btn_charts = Button(ax_ec, "⬇ Export Chart",
                                 color=BG_AX, hovercolor=BORDER)
        self.btn_report = Button(ax_er, "⬇ Export Report",
                                 color=BG_AX, hovercolor=BORDER)
        self.btn_charts.label.set_color(ACCENT_BLUE)
        self.btn_charts.label.set_fontfamily("monospace")
        self.btn_charts.label.set_fontsize(8)
        self.btn_report.label.set_color(THRESH_AMB)
        self.btn_report.label.set_fontfamily("monospace")
        self.btn_report.label.set_fontsize(8)
        self.btn_charts.on_clicked(lambda e: self.export_charts())
        self.btn_report.on_clicked(lambda e: self.export_report())

        # ── Navigation arrows (prev / next chart) ───────────────────────
        ax_prev = self.fig.add_axes([0.82, 0.025, 0.06, 0.035])
        ax_next = self.fig.add_axes([0.90, 0.025, 0.06, 0.035])
        self.btn_prev = Button(ax_prev, "◀ Prev",
                               color=BG_AX, hovercolor=BORDER)
        self.btn_next = Button(ax_next, "Next ▶",
                               color=BG_AX, hovercolor=BORDER)
        for btn in [self.btn_prev, self.btn_next]:
            btn.label.set_color(ACCENT_BLUE)
            btn.label.set_fontfamily("monospace")
            btn.label.set_fontsize(8)
        self.btn_prev.on_clicked(lambda e: self._nav_chart(-1))
        self.btn_next.on_clicked(lambda e: self._nav_chart(+1))

        # ── Connect dropdown click ───────────────────────────────────────
        self.fig.canvas.mpl_connect(
            "button_press_event", self._on_dropdown_click)

        # ── Initial render ───────────────────────────────────────────────
        self.render_chart()

        # ── Live polling ─────────────────────────────────────────────────
        self._start_polling()

    # ── Dropdown ──────────────────────────────────────────────────────────────

    def _on_dropdown_click(self, event):
        """Open a tkinter popup menu when user clicks the dropdown area."""
        if event.inaxes != self._dropdown_ax:
            return
        try:
            import tkinter as tk
            root = self.fig.canvas.manager.window

            menu = tk.Menu(root, tearoff=0,
                           bg=DROPDOWN_BG, fg=ACCENT_CYAN,
                           activebackground=DROPDOWN_ACT,
                           activeforeground="white",
                           font=("Consolas", 10),
                           relief="flat", bd=0)

            for i, name in enumerate(CHART_NAMES):
                menu.add_command(
                    label=f"  {name}",
                    command=lambda idx=i: self._select_chart(idx))

            x = root.winfo_pointerx()
            y = root.winfo_pointery()
            menu.tk_popup(x, y)
        except Exception as e:
            print(f"Dropdown error: {e}")

    def _select_chart(self, idx):
        """Switch to chart at given index."""
        self._active_idx = idx
        self._sel_text.set_text(f"▼  {CHART_NAMES[idx]}")
        self._idx_text.set_text(f"{idx + 1} / {len(CHART_NAMES)}")
        self.render_chart()

    def _nav_chart(self, direction):
        """Move to previous/next chart."""
        idx = (self._active_idx + direction) % len(CHART_NAMES)
        self._select_chart(idx)

    # ── Polling ───────────────────────────────────────────────────────────────

    def _start_polling(self):
        try:
            self._tk_root = self.fig.canvas.manager.window
            self._tk_root.after(2000, self._tk_poll)
        except Exception:
            self._timer = self.fig.canvas.new_timer(interval=2000)
            self._timer.add_callback(self._poll)
            self._timer.start()

    def _tk_poll(self):
        self._poll()
        try:
            self._tk_root.after(2000, self._tk_poll)
        except Exception:
            pass

    # ── Scrubber ──────────────────────────────────────────────────────────────

    def _on_scrub(self, val):
        self._cur_cycle = int(val)
        self.render_chart()

    def _update_slider_range(self):
        if not self.df_out.empty:
            mx = int(self.df_out["cycle"].max())
            self.slider.valmax = mx
            self.slider.set_val(mx)
            self._cur_cycle = mx

    # ── Render dispatcher ─────────────────────────────────────────────────────

    def render_chart(self):
        """Render the currently selected chart into the main axes."""
        ax = self.ax_main
        mc = self._cur_cycle
        idx = self._active_idx

        # Clean up any twinx / colorbar axes from previous charts
        fig = ax.get_figure()
        for other_ax in list(fig.axes):
            if other_ax is ax:
                continue
            if getattr(other_ax, '_is_sei_twin', False):
                other_ax.remove()
            if getattr(other_ax, '_is_c8_colorbar', False):
                other_ax.remove()

        ax.cla()

        if idx == 0:
            render_c1(ax, self.df_out, mc)
        elif idx == 1:
            render_c2(ax, self.df_out, mc)
        elif idx == 2:
            cycle_pct = mc / max(self.df_out["cycle"].max(), 1) if mc else 1.0
            render_c3(ax, self.df_sp, cycle_pct)
        elif idx == 3:
            render_c4(ax, self.df_out)
        elif idx == 4:
            render_c5(ax, self.df_out, mc)
        elif idx == 5:
            render_c6(ax, self.df_out, mc)
        elif idx == 6:
            render_c7(ax, self.df_out, mc)
        elif idx == 7:
            render_c8(ax, self.df_sands, self.params)

        # Timestamp
        self.ts_txt.set_text(
            f"LG M50 INR21700  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}")

        self.fig.canvas.draw_idle()

    # ── Live poll ─────────────────────────────────────────────────────────────

    def _poll(self):
        changed = False

        mtime = get_params_mtime()
        if mtime != self._last_mtime:
            self._last_mtime = mtime
            self.df_out, self.df_sp, self.df_sands, self.params = \
                load_data(self.mock)
            self._update_slider_range()
            changed = True

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
            self.render_chart()

    # ── Export chart ──────────────────────────────────────────────────────────

    def export_charts(self):
        """Export the currently displayed chart as a high-res PNG."""
        idx = self._active_idx
        safe_name = CHART_NAMES[idx].lower().replace(" ", "_").replace("—", "").replace(">","gt")
        safe_name = "".join(c for c in safe_name if c.isalnum() or c == "_")
        name = f"chart_{idx+1}_{safe_name}"

        fig_e, ax_e = plt.subplots(figsize=(16, 9), facecolor=BG_DEEP)
        fig_e.patch.set_facecolor(BG_DEEP)

        mc = self._cur_cycle
        if idx == 0:
            render_c1(ax_e, self.df_out, mc)
        elif idx == 1:
            render_c2(ax_e, self.df_out, mc)
        elif idx == 2:
            cycle_pct = mc / max(self.df_out["cycle"].max(), 1) if mc else 1.0
            render_c3(ax_e, self.df_sp, cycle_pct)
        elif idx == 3:
            render_c4(ax_e, self.df_out)
        elif idx == 4:
            render_c5(ax_e, self.df_out, mc)
        elif idx == 5:
            render_c6(ax_e, self.df_out, mc)
        elif idx == 6:
            render_c7(ax_e, self.df_out, mc)
        elif idx == 7:
            render_c8(ax_e, self.df_sands, self.params)

        fig_e.tight_layout()
        path = os.path.join(OUTPUTS_DIR, f"{name}.png")
        fig_e.savefig(path, dpi=300, facecolor=BG_DEEP, bbox_inches="tight")
        plt.close(fig_e)
        print(f"\n  ✓ Exported {name}.png → {path}")

    # ── Export report ─────────────────────────────────────────────────────────

    def export_report(self):
        df = self.df_out
        fast_c, slow_c = {}, {}
        for p in PRESETS_ORDER:
            fast_c[p] = risk_crossing(df[RISK_FAST[p]], RISK_THRESH_RED, df) \
                        if RISK_FAST[p] in df.columns else "N/A"
            slow_c[p] = risk_crossing(df[RISK_SLOW[p]], RISK_THRESH_RED, df) \
                        if RISK_SLOW[p] in df.columns else "N/A"

        fm = fast_c.get("moderate")
        sm = slow_c.get("moderate")
        ratio = f"{round((sm-fm)/fm*100,1)}%" \
                if isinstance(fm, int) and isinstance(sm, int) and fm > 0 \
                else "N/A"

        sei_200 = round(float(df["sei_moderate"].iloc[-1]), 1) \
                  if "sei_moderate" in df.columns else "N/A"
        li_loss = round(sei_200 * 0.3, 1) if isinstance(sei_200, float) else "N/A"

        def dep_cycle(col):
            if col in df.columns:
                b = df[df[col] < CONC_DEPLETE]
                return int(b.iloc[0]["cycle"]) if not b.empty else "N/A (>200)"
            return "N/A"

        conc_fast_dep = dep_cycle("conc_fast")
        conc_slow_dep = dep_cycle("conc_slow")

        sand_fast = int(df["sand_crossed_cycle_fast"].iloc[0]) \
                    if "sand_crossed_cycle_fast" in df.columns else "N/A"
        sand_slow = int(df["sand_crossed_cycle_slow"].iloc[0]) \
                    if "sand_crossed_cycle_slow" in df.columns else "N/A"
        sand_slow = "N/A — not reached" if sand_slow == -1 else sand_slow

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
                        help="Export current chart and report, then exit")
    args = parser.parse_args()

    print(f"Dendrite Engine Dashboard v3 — Data Explorer — {'MOCK' if args.mock else 'REAL'} mode")
    dash = Dashboard(mock=args.mock)

    if args.export:
        dash.export_charts()
        dash.export_report()
        return

    plt.show()


if __name__ == "__main__":
    main()
