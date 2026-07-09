import os
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

import database
from config import GUILD_ID, ROLE_MILESTONES, ANNOUNCEMENT_CHANNEL_ID, MILESTONE_ANNOUNCEMENTS

load_dotenv()

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
GUILD = discord.Object(id=GUILD_ID)


# ---------------------------------------------------------------------------
# Role helpers
# ---------------------------------------------------------------------------

def _target_role_name(attendance: int) -> Optional[str]:
    """Return the highest milestone role name the member qualifies for."""
    qualified = [
        name
        for threshold, name in sorted(ROLE_MILESTONES.items())
        if attendance >= threshold
    ]
    return qualified[-1] if qualified else None


async def _sync_roles(
    guild: discord.Guild, member: discord.Member, attendance: int
) -> tuple[Optional[str], Optional[str]]:
    """
    Assign the correct milestone role and remove stale ones.
    Returns (new_role_name, warning):
      - new_role_name: role just assigned, or None if no change
      - warning: human-readable problem string, or None if everything is fine
    """
    all_milestone_names = set(ROLE_MILESTONES.values())
    target_name = _target_role_name(attendance)

    stale = [r for r in member.roles if r.name in all_milestone_names and r.name != target_name]
    if stale:
        await member.remove_roles(*stale, reason="Attendance milestone update")

    if target_name:
        target_role = discord.utils.get(guild.roles, name=target_name)
        if target_role is None:
            return None, f'Role **"{target_name}"** does not exist in this server — create it and re-run to assign it.'
        if target_role not in member.roles:
            await member.add_roles(target_role, reason="Attendance milestone reached")
            return target_name, None

    return None, None


async def _post_milestone_announcement(guild: discord.Guild, member: discord.Member, role_name: str, attendance: int):
    """Post the rank-up message (and optional sticker) to the announcement channel."""
    if not ANNOUNCEMENT_CHANNEL_ID:
        return

    channel = guild.get_channel(ANNOUNCEMENT_CHANNEL_ID)
    if channel is None:
        print(f"Warning: announcement channel {ANNOUNCEMENT_CHANNEL_ID} not found")
        return

    announcement = MILESTONE_ANNOUNCEMENTS.get(role_name)
    if not announcement:
        return

    text = announcement["message"].format(mention=member.mention, count=attendance)
    sticker_id = announcement.get("sticker_id")

    if sticker_id:
        try:
            sticker = await guild.fetch_sticker(sticker_id)
            await channel.send(content=text, stickers=[sticker])
        except (discord.NotFound, discord.HTTPException):
            await channel.send(content=text)
    else:
        await channel.send(content=text)


# ---------------------------------------------------------------------------
# Bot events
# ---------------------------------------------------------------------------

@bot.event
async def on_ready():
    database.init_db()
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        synced = await bot.tree.sync(guild=GUILD)
        print(f"Synced {len(synced)} slash command(s) to guild {GUILD_ID}")
    except Exception as exc:
        print(f"Failed to sync commands: {exc}")


# ---------------------------------------------------------------------------
# Slash commands
# ---------------------------------------------------------------------------

@bot.tree.command(guild=GUILD, name="attend", description="Record that a member attended an event (+1)")
@app_commands.describe(member="The member who attended")
@app_commands.checks.has_permissions(manage_roles=True)
async def cmd_attend(interaction: discord.Interaction, member: discord.Member):
    new_count = database.increment_attendance(str(member.id), member.display_name)
    new_role, warning = await _sync_roles(interaction.guild, member, new_count)

    lines = [f"Attendance recorded for {member.mention}. Total: **{new_count}**"]
    if new_role:
        lines.append(f"They've reached the **{new_role}** milestone!")
        await _post_milestone_announcement(interaction.guild, member, new_role, new_count)
    if warning:
        lines.append(f"⚠️ {warning}")

    await interaction.response.send_message("\n".join(lines))


@bot.tree.command(guild=GUILD, name="attendance", description="Check a member's attendance count")
@app_commands.describe(member="Member to check (leave blank to check yourself)")
async def cmd_attendance(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    data = database.get_member(str(target.id))

    if not data:
        await interaction.response.send_message(
            f"{target.mention} has no recorded attendance.", ephemeral=True
        )
        return

    count = data["attendance"]
    role_name = _target_role_name(count) or "None"
    await interaction.response.send_message(
        f"{target.mention} — **{count}** event(s) attended | Current rank: **{role_name}**",
        ephemeral=True,
    )


@bot.tree.command(guild=GUILD, name="set_attendance", description="Manually set a member's attendance count")
@app_commands.describe(member="The member to update", count="New attendance count")
@app_commands.checks.has_permissions(manage_roles=True)
async def cmd_set_attendance(interaction: discord.Interaction, member: discord.Member, count: int):
    if count < 0:
        await interaction.response.send_message("Count must be 0 or greater.", ephemeral=True)
        return

    database.set_attendance(str(member.id), member.display_name, count)
    new_role, warning = await _sync_roles(interaction.guild, member, count)

    lines = [f"Attendance for {member.mention} set to **{count}**."]
    if new_role:
        lines.append(f"They now qualify for the **{new_role}** role!")
        await _post_milestone_announcement(interaction.guild, member, new_role, count)
    if warning:
        lines.append(f"⚠️ {warning}")

    await interaction.response.send_message("\n".join(lines))


@bot.tree.command(guild=GUILD, name="reset_all", description="[DEBUG] Wipe all attendance records and remove milestone roles from everyone")
@app_commands.describe(confirm='Type "yes" to confirm — this cannot be undone')
@app_commands.checks.has_permissions(administrator=True)
async def cmd_reset_all(interaction: discord.Interaction, confirm: str):
    if confirm.strip().lower() != "yes":
        await interaction.response.send_message(
            'Aborted. Pass `confirm: yes` to actually reset everything.', ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)

    deleted = database.reset_all()

    # Strip milestone roles from every member in the guild
    milestone_names = set(ROLE_MILESTONES.values())
    milestone_roles = [r for r in interaction.guild.roles if r.name in milestone_names]
    cleared = 0
    async for member in interaction.guild.fetch_members(limit=None):
        roles_to_remove = [r for r in member.roles if r in milestone_roles]
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove, reason="Debug reset")
            cleared += 1

    await interaction.followup.send(
        f"Reset complete. Deleted **{deleted}** record(s) and stripped milestone roles from **{cleared}** member(s).",
        ephemeral=True,
    )


@bot.tree.command(guild=GUILD, name="leaderboard", description="Show the top event attendees")
@app_commands.describe(limit="Number of members to show (default 10, max 25)")
async def cmd_leaderboard(interaction: discord.Interaction, limit: int = 10):
    limit = max(1, min(limit, 25))
    rows = database.get_leaderboard(limit)

    if not rows:
        await interaction.response.send_message("No attendance records yet.", ephemeral=True)
        return

    lines = ["**Event Attendance Leaderboard**", ""]
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for i, row in enumerate(rows, 1):
        prefix = medals.get(i, f"{i}.")
        lines.append(f"{prefix} <@{row['discord_id']}> — **{row['attendance']}** event(s)")

    await interaction.response.send_message("\n".join(lines))


# ---------------------------------------------------------------------------
# Global error handler
# ---------------------------------------------------------------------------

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "You don't have permission to use this command.", ephemeral=True
        )
    else:
        await interaction.response.send_message(
            f"An error occurred: {error}", ephemeral=True
        )
        raise error


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

token = os.getenv("DISCORD_TOKEN")
if not token:
    raise RuntimeError("DISCORD_TOKEN is not set in your .env file")

bot.run(token)
