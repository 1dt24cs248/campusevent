"""Role and section filtering for the existing announcement records."""

def announcement_visible(announcement, role: str, section_id: str | None) -> bool:
    if announcement.section_id and announcement.section_id != section_id:
        return False
    return audience_matches(announcement.audience, role, section_id)


def audience_matches(audience, role: str, section_id: str | None) -> bool:
    if audience is None:
        return True
    if isinstance(audience, list):
        values = {str(value).upper() for value in audience}
        return role.upper() in values or "ALL" in values or bool(section_id and section_id.upper() in values)
    if isinstance(audience, dict):
        roles = audience.get("roles", [])
        sections = audience.get("section_ids", [])
        return (
            role.upper() in {str(value).upper() for value in roles if isinstance(value, str)}
            or "ALL" in {str(value).upper() for value in roles if isinstance(value, str)}
            or bool(section_id and section_id in sections)
        )
    return False
