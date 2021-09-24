import datetime
import logging
import time

import dataset
import discord
from discord.ext import commands
from cogs.commands import settings
from discord.ext.commands import Bot, Cog
from discord_slash import SlashContext, cog_ext
from discord_slash.model import SlashCommandPermissionType
from discord_slash.utils.manage_commands import (
    create_choice,
    create_option,
    create_permission,
)
from utils import database, embeds
from utils.pagination import LinePaginator
from utils.record import record_usage

# Enabling logs
log = logging.getLogger(__name__)


class NotesCog(Cog):
    """Notes Cog"""

    def __init__(self, bot):
        self.bot = bot

    @commands.bot_has_permissions(send_messages=True)
    @commands.before_invoke(record_usage)
    @cog_ext.cog_slash(
        name="addnote",
        description="Add a note to a user",
        guild_ids=[settings.get_value("guild_id")],
        options=[
            create_option(
                name="user",
                description="The user to add the note to",
                option_type=6,
                required=True,
            ),
            create_option(
                name="note",
                description="The note to leave on the user",
                option_type=3,
                required=True,
            ),
        ],
        default_permission=False,
        permissions={
            settings.get_value("guild_id"): [
                create_permission(
                    settings.get_value("role_staff"),
                    SlashCommandPermissionType.ROLE,
                    True,
                ),
                create_permission(
                    settings.get_value("role_trial_mod"),
                    SlashCommandPermissionType.ROLE,
                    True,
                ),
            ]
        },
    )
    async def add_note(self, ctx: SlashContext, user: discord.User, note: str):
        """Adds a moderator note to a user."""
        await ctx.defer()

        # If we received an int instead of a discord.Member, the user is not in the server.
        if not isinstance(user, discord.Member):
            user = await self.bot.fetch_user(user)

        # Open a connection to the database.
        db = dataset.connect(database.get_db())

        # Add the note to the mod_logs database.
        note_id = db["mod_logs"].insert(
            dict(
                user_id=user.id,
                mod_id=ctx.author.id,
                timestamp=int(time.time()),
                reason=note,
                type="note",
            )
        )

        embed = embeds.make_embed(
            ctx=ctx,
            title=f"Noting user: {user.name}",
            description=f"{user.mention} was noted by {ctx.author.mention}",
            thumbnail_url="https://i.imgur.com/A4c19BJ.png",
            color="blurple",
        )
        embed.add_field(name="ID: ", value=note_id, inline=False)
        embed.add_field(name="Note: ", value=note, inline=False)
        await ctx.send(embed=embed)

        # Commit the changes to the database and close the connection.
        db.commit()
        db.close()

    @cog_ext.cog_slash(
        name="search",
        description="View users notes and mod actions history",
        guild_ids=[settings.get_value("guild_id")],
        options=[
            create_option(
                name="user",
                description="The user to lookup",
                option_type=6,
                required=True,
            ),
            create_option(
                name="action",
                description="Filter specific actions",
                option_type=3,
                choices=[
                    create_choice(value="ban", name="Ban"),
                    create_choice(value="unban", name="Unban"),
                    create_choice(value="mute", name="Mute"),
                    create_choice(value="unmute", name="Unmute"),
                    create_choice(value="kick", name="Kick"),
                    create_choice(value="restrict", name="Restrict"),
                    create_choice(value="unrestrict", name="Unrestrict"),
                    create_choice(value="warn", name="Warn"),
                    create_choice(value="note", name="Note"),
                ],
                required=False,
            ),
        ],
        default_permission=False,
        permissions={
            settings.get_value("guild_id"): [
                create_permission(
                    settings.get_value("role_staff"),
                    SlashCommandPermissionType.ROLE,
                    True,
                ),
                create_permission(
                    settings.get_value("role_trial_mod"),
                    SlashCommandPermissionType.ROLE,
                    True,
                ),
            ]
        },
    )
    async def search_mod_actions(
        self, ctx: SlashContext, user: discord.User, action: str = None
    ):
        """Searches for mod actions on a user"""
        await ctx.defer()

        # If we received an int instead of a discord.Member, the user is not in the server.
        if not isinstance(user, discord.Member):
            user = await self.bot.fetch_user(user)

        # Open a connection to the database.
        db = dataset.connect(database.get_db())

        # Querying DB for the list of actions matching the filter criteria (if mentioned).
        mod_logs = db["mod_logs"]
        if action:
            results = mod_logs.find(user_id=user.id, type=action)
        else:
            results = mod_logs.find(user_id=user.id)

        # Creating a List to store actions for the paginator.
        actions = []
        for action in results:
            action_emoji = dict(
                mute="🤐",
                unmute="🗣",
                warn="⚠",
                kick="👢",
                ban="🔨",
                unban="⚒",
                restrict="🚫",
                unrestrict="✅",
                note="🗒️",
            )

            action_type = action["type"]
            # Capitalising the first letter of the action type.
            action_type = action_type[0].upper() + action_type[1:]
            # Adding fluff emoji to action_type.
            action_type = f"{action_emoji[action['type']]} {action_type}"

            actions.append(
                f"""
            **{action_type} | ID: {action['id']}**
            **Timestamp:** {str(datetime.datetime.fromtimestamp(action['timestamp'], tz=datetime.timezone.utc)).replace("+00:00", " UTC")} 
            **Moderator:** <@!{action['mod_id']}>
            **Reason:** {action['reason']}"""
            )

        if not actions:
            # Nothing was found, so returning an appropriate error.
            await embeds.error_message(
                ctx=ctx, description="No mod actions found for that user!"
            )
            return

        db.close()

        embed = embeds.make_embed(ctx=ctx, title="Mod Actions")

        # paginating through the results
        await LinePaginator.paginate(
            actions,
            ctx=ctx,
            embed=embed,
            max_lines=4,
            max_size=2000,
            linesep="",
            timeout=30,
        )

    @commands.bot_has_permissions(send_messages=True)
    @commands.before_invoke(record_usage)
    @cog_ext.cog_slash(
        name="editlog",
        description="Edits an existing log or note for a user",
        guild_ids=[settings.get_value("guild_id")],
        options=[
            create_option(
                name="id",
                description="The ID of the log or note to be edited",
                option_type=4,
                required=True,
            ),
            create_option(
                name="note",
                description="The updated message for the log or note",
                option_type=3,
                required=True,
            ),
        ],
        default_permission=False,
        permissions={
            settings.get_value("guild_id"): [
                create_permission(
                    settings.get_value("role_staff"),
                    SlashCommandPermissionType.ROLE,
                    True,
                ),
                create_permission(
                    settings.get_value("role_trial_mod"),
                    SlashCommandPermissionType.ROLE,
                    True,
                ),
            ]
        },
    )
    async def edit_log(self, ctx: SlashContext, id: int, note: str):
        await ctx.defer()

        # Open a connection to the database.
        db = dataset.connect(database.get_db())

        table = db["mod_logs"]

        mod_log = table.find_one(id=id)
        if not mod_log:
            await embeds.error_message(
                ctx=ctx, description="Could not find a log with that ID!"
            )
            return

        user = await self.bot.fetch_user(mod_log["user_id"])
        embed = embeds.make_embed(
            ctx=ctx,
            title=f"Edited log: {user.name}",
            description=f"Log #{id} for {user.mention} was updated by {ctx.author.mention}",
            thumbnail_url="https://i.imgur.com/A4c19BJ.png",
            color="soft_green",
        )
        embed.add_field(name="Before:", value=mod_log["reason"], inline=False)
        embed.add_field(name="After:", value=note, inline=False)
        await ctx.send(embed=embed)

        mod_log["reason"] = note
        table.update(mod_log, ["id"])

        # Commit the changes to the database and close the connection.
        db.commit()
        db.close()


def setup(bot: Bot) -> None:
    """Load the Notes cog."""
    bot.add_cog(NotesCog(bot))
    log.info("Commands loaded: notes")
