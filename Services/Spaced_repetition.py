from datetime import timedelta


def update_spaced_repetition(quality, interval, ease):
    """Small SM-2-inspired scheduler.

    quality: 0-5, where 5 means effortless recall and <3 means failed recall.
    Returns the next interval in days and adjusted ease factor.
    """
    quality = max(0, min(5, int(quality)))
    interval = max(1, int(interval or 1))
    ease = max(1.3, float(ease or 2.5))

    if quality < 3:
        return 1, max(1.3, ease - 0.20)

    if interval == 1:
        new_interval = 3 if quality == 3 else 4
    else:
        multiplier = ease
        if quality == 3:
            multiplier = max(1.3, ease - 0.10)
        elif quality == 5:
            multiplier = ease + 0.10
        new_interval = max(interval + 1, round(interval * multiplier))

    new_ease = ease + (0.1 - (5-quality) * (0.08 + (5-quality) * 0.02))
    return min(new_interval, 365), max(1.3, round(new_ease, 2))


def get_next_review_date(last_review_date, interval):
    return last_review_date + timedelta(days=max(1, int(interval)))
