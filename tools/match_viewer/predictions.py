"""Optional prediction labels, using the official CSV contract without scoring."""

from evaluation.possession_metrics import read_label_csv, validate_submission
from .tracking import ViewerError


def load_predictions(path, n_frames):
    if path is None:
        return None
    try:
        table = read_label_csv(path)
        if list(table.columns) != ["frame", "label"] or validate_submission(table, n_frames):
            raise ViewerError("Prediction CSV must have frame,label, consecutive frames and H/A/D/X labels.")
        return [str(value).strip().upper() for value in table["label"]]
    except ViewerError:
        raise
    except Exception:
        raise ViewerError("Cannot read the prediction CSV; verify its format and path.") from None
