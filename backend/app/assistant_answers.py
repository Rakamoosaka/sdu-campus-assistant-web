"""Render answers from server records rather than model-authored prose."""


def render(intent: str, places: list[dict], clarification: bool,
           routes: list[dict], results: list[tuple[str, dict]]) -> str:
    if clarification:
        return "I found several campus places. Which one do you mean?"
    if routes:
        route = routes[-1]
        return route["message"] + (
            "\nChoose Open route on map to view the route and floor transfers."
            if route.get("segments") else ""
        )
    data = dict(results)
    personal_tool = {
        "profile": "get_my_profile", "next_class": "get_next_class",
        "saved_places": "get_my_saved_places", "preferences": "get_my_preferences",
        "schedule": "get_my_schedule", "reports": "get_my_reports",
        "updates": "get_campus_updates",
    }.get(intent)
    personal = data.get(personal_tool, {})
    if personal.get("status") == "login_required":
        return "Log in to see your stored profile and personal sample campus information."
    if intent == "profile" and personal:
        return (f"Your name is {personal['full_name']}. Your account role is {personal['role']}, "
                f"and your faculty is {personal['faculty']}.")
    if intent == "preferences" and personal:
        preference = "avoid stairs" if personal["avoid_stairs"] else "allow stairs"
        return f"Your saved route preference is to {preference}. Step-free approaches remain unverified."
    if intent == "next_class" and personal:
        if personal.get("status") == "empty":
            return "There are no upcoming lessons in your stored sample schedule (Asia/Almaty)."
        return (f"Sample schedule: {personal['course']}, {personal['room']}, "
                f"{personal['starts_at']} Asia/Almaty.")
    if intent == "schedule" and personal:
        lessons = personal["lessons"]
        if not lessons:
            return "Your stored sample timetable is empty."
        return "Your stored sample timetable (Asia/Almaty):\n" + "\n".join(
            f"{item['course']} · {item['room']} · {item['starts_at']}" for item in lessons
        )
    if intent == "saved_places" and personal:
        return ("Your saved places:\n" + "\n".join(
            f"{item['name']} · {item['block']} · {item['floor']}" for item in personal["locations"]
        )) if personal["locations"] else "You have no saved campus places yet."
    if intent == "reports" and personal:
        return ("Your latest submitted campus reports:\n" + "\n".join(
            f"{item['created_at']} · {item['status']} · {item['message']}"
            for item in personal["reports"]
        )) if personal["reports"] else "You have no submitted campus reports."
    if intent == "updates" and personal:
        return ("Current campus announcements (seeded announcements are sample data):\n" + "\n".join(
            f"{item['title']} · {item['published_at']}\n{item['body']}" for item in personal["updates"]
        )) if personal["updates"] else "There are no campus announcements right now."
    if places:
        text = "\n\n".join(
            f"{place['name']} · {place['block']} · {place['floor']}.\n"
            f"Opening hours: {place['opening_hours']}. Contact: {place['contact']}."
            for place in places
        )
        if intent == "route":
            text += "\nWhere are you starting from?"
        return text
    return ("I could not find confirmed campus information for that request. "
            "Try a room code or a service such as the library, printing, or medical point.")
