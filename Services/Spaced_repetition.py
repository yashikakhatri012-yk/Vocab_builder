from datetime import timedelta

def update_spaced_repetition(quality, interval, ease):
    if quality < 3:
        return 1, 2.5

    new_interval = int(interval * ease)
    new_ease = ease + (0.1 - (5-quality)*(0.08+(5-quality)*0.02))

    return new_interval, max(1.3, new_ease)
def get_next_review_date(last_review_date, interval):
    return last_review_date + timedelta(days=interval)
