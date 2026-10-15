import re
from datetime import datetime
from urllib.parse import urlparse


# ============================================================
# VALIDATION RESULT
# ============================================================

def validate_event(event):

    errors = []
    warnings = []

    title = str(event.get("title", "") or "").strip()
    date = str(event.get("date", "") or "").strip()
    event_time = str(event.get("time", "") or "").strip()
    venue = str(event.get("venue", "") or "").strip()
    city = str(event.get("city", "") or "").strip()
    link = str(event.get("link", "") or "").strip()
    image = str(event.get("image", "") or "").strip()
    source = str(event.get("source", "") or "").strip()


    # ========================================================
    # TITLE
    # ========================================================

    if not title or title.upper() == "N/A":

        errors.append(
            "Missing event title"
        )

    elif len(title) < 3:

        errors.append(
            "Event title is too short"
        )

    elif len(title) > 300:

        warnings.append(
            "Event title is unusually long"
        )


    # ========================================================
    # DATE
    # ========================================================

    if not date or date.upper() == "N/A":

        warnings.append(
            "Missing event date"
        )

    else:

        date_only = date[:10]

        try:

            datetime.strptime(
                date_only,
                "%Y-%m-%d"
            )

        except ValueError:

            errors.append(
                f"Invalid date format: {date}"
            )


    # ========================================================
    # TIME
    # ========================================================

    if (
        event_time
        and event_time.upper() != "N/A"
    ):

        valid_time = re.match(
            r"^(?:[01]\d|2[0-3]):[0-5]\d$",
            event_time
        )

        if not valid_time:

            warnings.append(
                f"Invalid time format: {event_time}"
            )


    # ========================================================
    # VENUE
    # ========================================================

    if not venue or venue.upper() == "N/A":

        warnings.append(
            "Missing venue"
        )

    else:

        garbage_words = [

            "open menu",
            "login",
            "sign in",
            "create event",
            "control panel",
            "feedback",
            "suggestions",
            "download app"

        ]

        venue_lower = venue.lower()

        for word in garbage_words:

            if word in venue_lower:

                errors.append(
                    f"Venue appears to contain navigation text: {venue}"
                )

                break


    # ========================================================
    # CITY
    # ========================================================

    if not city:

        warnings.append(
            "Missing city"
        )


    # ========================================================
    # LINK
    # ========================================================

    if not link:

        errors.append(
            "Missing event URL"
        )

    else:

        parsed = urlparse(
            link
        )

        if parsed.scheme not in (
            "http",
            "https"
        ):

            errors.append(
                f"Invalid URL: {link}"
            )

        elif not parsed.netloc:

            errors.append(
                f"Invalid URL: {link}"
            )


    # ========================================================
    # IMAGE
    # ========================================================

    if (
        image
        and image.upper() != "N/A"
    ):

        parsed_image = urlparse(
            image
        )

        if parsed_image.scheme not in (
            "http",
            "https"
        ):

            warnings.append(
                "Image URL is invalid"
            )


    # ========================================================
    # SOURCE
    # ========================================================

    if not source:

        warnings.append(
            "Missing source"
        )


    # ========================================================
    # RESULT
    # ========================================================

    is_valid = len(errors) == 0


    return {

        "valid": is_valid,

        "errors": errors,

        "warnings": warnings

    }


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    test_event = {

        "title":
            "Sri Krishna Janmashtami",

        "date":
            "2026-09-04",

        "time":
            "10:00",

        "venue":
            "Karnataka Trade Promotion Organisation",

        "city":
            "Bangalore",

        "link":
            "https://allevents.in/bangalore/test/123456",

        "image":
            "https://example.com/image.jpg",

        "source":
            "allevents.in"

    }


    result = validate_event(
        test_event
    )


    print()
    print("=" * 60)
    print("DATA VALIDATOR TEST")
    print("=" * 60)

    print(
        "Valid:",
        result["valid"]
    )

    print(
        "Errors:",
        result["errors"]
    )

    print(
        "Warnings:",
        result["warnings"]
    )

    print("=" * 60)