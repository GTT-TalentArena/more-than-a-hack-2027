"""Reusable validations for data contract v1."""
import numpy as np

VERSION = "1.0"


def check_tracking_frames(path, n_frames):
    """Strict streaming check: stops the baseline from hiding lost rows."""
    count = 0
    with open(path, encoding="utf-8-sig") as handle:
        for count, line in enumerate(handle, start=1):
            parts = line.rstrip("\r\n").split(":")
            if len(parts) != 3 or int(parts[0]) != count:
                raise ValueError("ATD no consecutivo o mal formado en registro {}".format(count))
    if count != n_frames:
        raise ValueError("ATD: {} registros, esperados {}".format(count, n_frames))


def validate_frames(frames, n_frames):
    frames = np.asarray(frames)
    if (frames.shape != (n_frames,) or not np.issubdtype(frames.dtype, np.integer)
            or not np.array_equal(frames, np.arange(n_frames))):
        raise ValueError("frame debe ser la secuencia entera 0..N-1")


def normalized_to_metres(xy, pitch):
    xy = np.asarray(xy, dtype=np.float64)
    dimensions = np.asarray(pitch, dtype=np.float64)
    if xy.ndim < 1 or xy.shape[-1] != 2:
        raise ValueError("Las coordenadas deben terminar en dimensión 2")
    if dimensions.shape != (2,) or not np.all(np.isfinite(dimensions) & (dimensions > 0)):
        raise ValueError("Dimensiones del campo inválidas")
    return xy * dimensions


def validate_positions(xy, observed, available, imputed):
    xy = np.asarray(xy)
    masks = [np.asarray(mask) for mask in (observed, available, imputed)]
    if xy.ndim < 2 or xy.shape[-1] != 2:
        raise ValueError("Posiciones con forma (..., 2) requeridas")
    if any(m.shape != xy.shape[:-1] or m.dtype != np.bool_ for m in masks):
        raise ValueError("Máscaras booleanas con la forma de las posiciones requeridas")
    observed, available, imputed = masks
    if np.any(observed & imputed) or not np.array_equal(available, observed | imputed):
        raise ValueError("available debe ser observed OR imputed, sin solapes")
    if not np.all(np.isfinite(xy[available])) or not np.all(np.isnan(xy[~available])):
        raise ValueError("Posiciones disponibles finitas; ausentes NaN, nunca cero")
