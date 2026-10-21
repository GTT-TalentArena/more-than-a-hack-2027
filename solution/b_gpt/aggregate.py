"""Pure aggregate calculations. Input sequences/events never enter the output schema."""

import numpy as np


SET_PIECES = {
    "throw-in": "throw_in",
    "corner kick": "corner_kick",
    "free kick": "free_kick",
    "goal kick": "goal_kick",
    "kick off (start)": "kickoff_start",
    "kick off (after goal)": "kickoff_after_goal",
}
# Reporting tolerance only: automatic tags are intervals with roughly second-scale
# timing uncertainty. It is fixed, exposed in the report, and never changes labels.
AFTER_DEAD_SECONDS = 2.0


def segments(labels):
    """Internal half-open segments. Never serialize this return value."""
    if not len(labels):
        return []
    cuts = np.r_[0, np.flatnonzero(labels[1:] != labels[:-1]) + 1, len(labels)]
    return [(int(a), int(b), str(labels[a])) for a, b in zip(cuts[:-1], cuts[1:])]


def fill_abstentions(labels):
    """Same within-half fill policy as the official scorer; no GT needed."""
    known = np.flatnonzero(labels != "X")
    if not len(known):
        return labels.copy()
    carry = np.maximum.accumulate(np.where(labels != "X", np.arange(len(labels)), -1))
    carry[carry < 0] = known[0]
    return labels[carry]


def quantiles(values):
    if not len(values):
        return dict(p10=None, p50=None, p90=None)
    return dict(zip(("p10", "p50", "p90"), map(float, np.quantile(values, [.1, .5, .9]))))


def ratio(numerator, denominator):
    return float(numerator / denominator) if denominator else None


def spell_statistics(durations, n_frames, fps):
    minutes = n_frames / fps / 60
    return dict(n_possessions=len(durations), minutes=minutes,
                possessions_per_minute=ratio(len(durations), minutes),
                mean_duration_seconds=float(np.mean(durations)) if len(durations) else None,
                duration_seconds=quantiles(durations))


def piece_counts():
    return dict(n_events=0, inside_dead=0, just_after_dead=0,
                coherent_midpoint=0, near_dead_to_live_boundary=0,
                interval_could_be_coherent=0)


def finish_counts(counts):
    result = counts.copy()
    for key in ("inside_dead", "just_after_dead", "coherent_midpoint",
                "near_dead_to_live_boundary", "interval_could_be_coherent"):
        result[key + "_fraction"] = ratio(counts[key], counts["n_events"])
    return result


def add_counts(target, source):
    for key in target:
        target[key] += source[key]


def event_coherence(labels, events, offset, fps, tolerance_seconds=AFTER_DEAD_SECONDS):
    """Raw D only: an X never supplies invented evidence of a stoppage.

    Events belong to the half containing their midpoint. A midpoint is coherent
    when it is D or follows the exclusive end of a D run by <= tolerance.
    Only explicit D->H/A exits count as restart boundaries. All event intervals
    are clipped to this half; nothing can connect across halftime.
    """
    n = len(labels)
    tolerance = round(tolerance_seconds * fps)
    dead = labels == "D"
    after = np.zeros(n, dtype=bool)
    boundary = np.zeros(n, dtype=bool)
    for a, b, state in segments(labels):
        if state == "D":
            after[b:min(n, b + tolerance + 1)] = True
            if b < n and labels[b] in ("H", "A"):
                boundary[max(0, b - tolerance):min(n, b + tolerance + 1)] = True
    after &= ~dead
    coherent = dead | after
    cumulative = np.r_[0, np.cumsum(coherent)]
    by_type = {kind: piece_counts() for kind in SET_PIECES.values()}
    for event in events:
        kind = SET_PIECES.get(event["tags"].get("type", "").strip().casefold())
        if event["code"].strip().casefold() != "set pieces" or kind is None:
            continue
        start, stop = event["start"] - offset, event["end"] - offset
        midpoint = (start + stop) // 2
        if not 0 <= midpoint < n:
            continue
        counts = by_type[kind]
        counts["n_events"] += 1
        counts["inside_dead"] += int(dead[midpoint])
        counts["just_after_dead"] += int(after[midpoint])
        counts["coherent_midpoint"] += int(coherent[midpoint])
        counts["near_dead_to_live_boundary"] += int(boundary[midpoint])
        lo, hi = max(0, start), min(n, stop)
        counts["interval_could_be_coherent"] += int(hi > lo and cumulative[hi] > cumulative[lo])
    total = piece_counts()
    for counts in by_type.values():
        add_counts(total, counts)
    return total, by_type


def summarise_prediction(labels, events, blocks, fps):
    if fps <= 0:
        raise ValueError("Frame rate must be positive.")
    by_half = {}
    full_durations, raw_durations = [], []
    totals = {c: 0 for c in "HADX"}
    full_events = piece_counts()
    full_types = {kind: piece_counts() for kind in SET_PIECES.values()}
    n_frames = 0
    last_stop = 0
    for half, start, last in blocks:
        stop = last + 1
        if not (last_stop <= start < stop <= len(labels)) or str(half) in by_half:
            raise ValueError("Invalid, overlapping or duplicate half definition.")
        last_stop = stop
        raw = labels[start:stop]
        filled = fill_abstentions(raw)
        durations = [(b - a) / fps for a, b, c in segments(filled) if c in ("H", "A")]
        raw_lengths = [(b - a) / fps for a, b, c in segments(raw) if c in ("H", "A")]
        full_durations.extend(durations)
        raw_durations.extend(raw_lengths)
        counts = {c: int(np.sum(raw == c)) for c in "HADX"}
        for label in totals:
            totals[label] += counts[label]
        n_frames += len(raw)
        event_total, event_types = event_coherence(raw, events, start, fps)
        add_counts(full_events, event_total)
        for kind in full_types:
            add_counts(full_types[kind], event_types[kind])
        by_half[str(half)] = dict(
            **spell_statistics(durations, len(raw), fps),
            label_counts=counts,
            percent_D=100 * counts["D"] / len(raw),
            percent_X=100 * counts["X"] / len(raw),
            n_possessions_without_X_fill=len(raw_lengths),
            smart_tagging=dict(all_set_pieces=finish_counts(event_total),
                               by_type={k: finish_counts(v) for k, v in event_types.items()}))
    return dict(
        full_match=dict(**spell_statistics(full_durations, n_frames, fps),
                        label_counts=totals,
                        percent_D=100 * totals["D"] / n_frames if n_frames else None,
                        percent_X=100 * totals["X"] / n_frames if n_frames else None,
                        n_possessions_without_X_fill=len(raw_durations),
                        smart_tagging=dict(all_set_pieces=finish_counts(full_events),
                                           by_type={k: finish_counts(v) for k, v in full_types.items()})),
        by_half=by_half,
        # Kept separate: otherwise the ungraded break makes %X misleading.
        whole_video=dict(n_frames=len(labels),
                         percent_D=100 * float(np.mean(labels == "D")) if len(labels) else None,
                         percent_X=100 * float(np.mean(labels == "X")) if len(labels) else None))


def comparison(candidate, baseline, events, blocks, fps):
    if len(candidate) != len(baseline):
        raise ValueError("Candidate and baseline length mismatch.")
    inventory = dict(set_piece_instances=0, recognised_in_halves=0,
                     unrecognised_type_in_halves=0, midpoint_outside_halves=0)
    for event in events:
        if event["code"].strip().casefold() != "set pieces":
            continue
        inventory["set_piece_instances"] += 1
        midpoint = (event["start"] + event["end"]) // 2
        if not any(a <= midpoint <= b for _, a, b in blocks):
            inventory["midpoint_outside_halves"] += 1
        elif event["tags"].get("type", "").strip().casefold() not in SET_PIECES:
            inventory["unrecognised_type_in_halves"] += 1
        else:
            inventory["recognised_in_halves"] += 1
    return dict(
        schema_version=1,
        event_inventory=inventory,
        definitions=dict(
            scope="Published half blocks; includes their stoppages and pre-kickoff lead-in",
            minute_denominator="All video time inside each published half, not alive time",
            possession_policy="H/A maximal runs after within-half X forward fill and leading backfill",
            label_percent_policy="Raw labels before X filling; 0 to 100",
            event_policy="Automatic SET PIECES instances, attributed by interval midpoint",
            after_dead_tolerance_seconds=AFTER_DEAD_SECONDS,
            fractions="0 to 1; null means zero events, not zero coherence",
            coherence_policy="Raw D only; midpoint inside D or <=2 seconds after its exclusive end",
            boundary_policy="Midpoint within +/-2 seconds of an explicit D to H/A exit",
            interval_policy="Any point in the tag interval could satisfy coherence; a loose upper bound",
            independent_accuracy_estimate=False),
        b_gpt=summarise_prediction(candidate, events, blocks, fps),
        baseline_smooth50=summarise_prediction(baseline, events, blocks, fps))
