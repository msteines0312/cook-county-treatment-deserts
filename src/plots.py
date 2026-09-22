"""
Shared chart styling and map helpers, so every figure in the project looks
like it belongs to the same report.

Colors come from a colorblind-validated reference palette. On maps, only two
hues are used at once (plus grays), because more categorical colors than that
stop being reliably distinguishable for colorblind readers when every pair of
neighboring shapes can touch.
"""

import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import Patch

from src.config import FIGURES_DIR

# Categorical slots, used in this fixed order
BLUE = "#2a78d6"
ORANGE = "#eb6834"
AQUA = "#1baf7a"

# Neutrals for de-emphasized groups, text, and grid
GRAY_LIGHT = "#e4e3df"
GRAY_MID = "#c3c2bc"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e8e7e3"
SURFACE = "#fcfcfb"

# Single-hue sequential ramp (light = low, dark = high), for rates on maps
BLUE_RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

# Access groups: color only the two groups the story is about
ACCESS_GROUP_COLORS = {
    "high burden, low access": ORANGE,
    "high burden, high access": BLUE,
    "low burden, low access": GRAY_MID,
    "low burden, high access": GRAY_LIGHT,
    "no rate": "#ffffff",
}


def set_style():
    """Apply the project's matplotlib defaults: quiet axes, light grid, readable text."""
    plt.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "axes.edgecolor": GRID,
        "axes.labelcolor": TEXT_SECONDARY,
        "axes.titlecolor": TEXT_PRIMARY,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.grid.axis": "y",
        "axes.axisbelow": True,  # gridlines behind bars, not across them
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "xtick.color": TEXT_SECONDARY,
        "ytick.color": TEXT_SECONDARY,
        "font.size": 10,
        "legend.frameon": False,
    })


def save_figure(fig, filename):
    """Save to outputs/figures/ at a resolution that looks sharp in a README."""
    path = FIGURES_DIR / filename
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"saved {path.relative_to(FIGURES_DIR.parent.parent)}")


def add_source_note(fig, text, y=-0.02):
    """
    Small gray source line under the chart, the way a published figure would have it.

    Lower `y` (more negative) when a legend sits along the bottom of the figure,
    so the note lands below it instead of on top of it.
    """
    fig.text(0.01, y, text, fontsize=8, color=TEXT_SECONDARY, ha="left", va="top")


def map_axes(figsize=(7, 9)):
    """Figure and axes set up for a map: no grid, no ticks, no frame."""
    fig, ax = plt.subplots(figsize=figsize)
    ax.set_axis_off()
    return fig, ax


def plot_categories(ax, tracts, column, colors, order):
    """
    Draw a categorical choropleth with a legend in the given order.

    Tract edges are drawn in the surface color, which leaves a thin gap
    between neighboring tracts so borders read without dark outlines.
    """
    for category in order:
        subset = tracts[tracts[column] == category]
        if not subset.empty:
            subset.plot(ax=ax, color=colors[category], edgecolor=SURFACE, linewidth=0.3)
    handles = [Patch(facecolor=colors[category], edgecolor=GRAY_MID, label=category) for category in order]
    ax.legend(handles=handles, loc="lower left", fontsize=9)


def plot_binned_rates(ax, tracts, column, bins, suppressed_mask, legend_title):
    """
    Draw a sequential choropleth with fixed bins, graying out suppressed tracts.

    Fixed bins (not a continuous scale) make the legend easy to read and keep
    one very high tract from washing out everything else. Suppressed tracts get
    a flat light gray rather than hatching: with hundreds of small suburban
    tracts suppressed, hatching pulls the eye to the missing data.
    """
    colors = BLUE_RAMP[: len(bins) - 1]
    cmap = ListedColormap(colors)
    norm = BoundaryNorm(bins, cmap.N)

    shown = tracts[~suppressed_mask & tracts[column].notna()]
    hidden = tracts[suppressed_mask | tracts[column].isna()]
    shown.plot(ax=ax, column=column, cmap=cmap, norm=norm, edgecolor=SURFACE, linewidth=0.3)
    hidden.plot(ax=ax, color=GRAY_LIGHT, edgecolor=SURFACE, linewidth=0.3)

    labels = [f"{bins[i]:g} to {bins[i + 1]:g}" for i in range(len(bins) - 2)]
    labels.append(f"{bins[-2]:g}+")
    handles = [Patch(facecolor=color, label=label) for color, label in zip(colors, labels)]
    handles.append(Patch(facecolor=GRAY_LIGHT, label="fewer than 10 deaths (suppressed)"))
    ax.legend(handles=handles, loc="lower left", fontsize=9, title=legend_title,
              title_fontsize=9, alignment="left")
