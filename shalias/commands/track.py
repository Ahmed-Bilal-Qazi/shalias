"""Internal _track command — called by launchers, hidden from help."""
from ..utils import track_usage


def cmd_track(args):
    track_usage(args.alias)
