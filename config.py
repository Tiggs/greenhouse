# --- Server Config ---
GUILD_ID = 294133307611021312  # Replace with your Discord server ID (right-click server > Copy Server ID)

# Channel where rank-up announcements are posted.
# Right-click the channel > Copy Channel ID.
ANNOUNCEMENT_CHANNEL_ID = 1045051962619592804

# --- Role Milestones ---
# Maps attendance count -> role name in your Discord server.
# The bot assigns only the highest role the member qualifies for,
# removing lower-tier milestone roles automatically.
# Make sure these roles exist in your server before running the bot.
ROLE_MILESTONES = {
    1:  "Seed",
    6:  "Sprout",
    11: "Seedling",
    16: "Sapling",
    21: "Treesome",
}

# --- Milestone Announcements ---
# Keyed by role name (must match ROLE_MILESTONES values).
# `message`    — text posted when the member reaches this rank.
#                Use {mention} for the member's @mention and {count} for their attendance.
# `sticker_id` — optional Discord sticker ID to attach (int), or None to skip.
#                To get a sticker ID: Server Settings > Stickers, then copy its ID.
MILESTONE_ANNOUNCEMENTS: dict[str, dict] = {
    "Seed": {
        "message": "🌱 {mention} has just been planted! Welcome to the garden as a **Seed**!",
        "sticker_id": None,
    },
    "Sprout": {
        "message": "🌿 {mention} is breaking through the soil after **{count}** events! They're now a **Sprout**!",
        "sticker_id": None,
    },
    "Seedling": {
        "message": "🪴 {mention} is growing strong after **{count}** events! Rank up to **Seedling**!",
        "sticker_id": None,
    },
    "Sapling": {
        "message": "🌳 {mention} has reached **{count}** events and is now a **Sapling**! Roots are setting in.",
        "sticker_id": None,
    },
    "Treesome": {
        "message": "🌲 {mention} has attended **{count}** events and achieved **Treesome** status! A true pillar of the community.",
        "sticker_id": None,
    },
}