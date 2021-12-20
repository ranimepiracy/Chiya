import asyncio
import logging

import discord
import requests
from discord.commands import (
    Option,
    SlashCommandGroup,
    context,
    permissions
)
from discord.ext import commands
from utils import embeds
from utils.config import config

log = logging.getLogger(__name__)

server = SlashCommandGroup(
    name="server", description="Server management commands", default_permission=False, guild_ids=[config['guild_id']]
)


class ServerCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @server.command(
        name="pop",
        description="Gets the current server population",
        default_permission=False,
        guild_ids=config["guild_ids"],
    )
    @permissions.has_role(config["roles"]["staff"])
    async def pop(ctx: context.ApplicationContext):
        """
        Slash command for getting the current population of the server.

        Args:
            ctx (): The context of the slash command.
        """
        await ctx.defer()
        await ctx.respond(ctx.guild.member_count)

    @server.command(
        name="banner",
        description="Sets the banner to the image provided",
        default_permission=False,
        guild_ids=config["guild_ids"],
    )
    @permissions.has_role(config["roles"]["staff"])
    async def banner(
        ctx: context.ApplicationContext,
        link: Option(str, description="The link to the image to be set", required=True),
    ):
        """
        Slash command for updating the server banner.

        Args:
            ctx (): The context of the slash command.
            link (): A direct link to the image to use for the update.
        """
        await ctx.defer()

        r = requests.get(url=link)

        if r.status_code != 200:
            return await embeds.error_message(
                ctx=ctx, description="The link you entered was not accessible."
            )

        try:
            await ctx.guild.edit(banner=r.content)
        except discord.errors.InvalidArgument:
            return await embeds.error_message(
                ctx=ctx, description="Unable to set banner, verify the link is correct."
            )

        await ctx.respond(
            embed=embeds.make_embed(
                ctx=ctx,
                title="Banner updated",
                description=f"Banner [image]({link}) updated by {ctx.author.mention}",
                color="soft_green",
            )
        )

    @server.command(
        name="pingable",
        description="Makes a role pingable for 10 seconds",
        default_permission=False,
        guild_ids=config["guild_ids"],
    )
    @permissions.has_role(config["roles"]["staff"])
    async def pingable(
        ctx: context.ApplicationContext,
        role: Option(discord.Role, description="The role to make pingable", required=True)
    ):
        """
        Slash command for making server roles temporarily pingable.

        Args:
            ctx (): The context of the slash command.
            role (): The role to be made temporarily pingable.
        """
        await ctx.defer()

        if role.mentionable:
            return await embeds.success_message(
                ctx, description="That role is already mentionable."
            )

        await role.edit(mentionable=True)
        await embeds.success_message(
            ctx, description="You have 10 seconds to ping the role."
        )
        await asyncio.sleep(10)
        await role.edit(mentionable=False)

    @server.command(guild_ids=config["guild_ids"], default_permission=False, description="List all the server boosters")
    @permissions.has_role(config["roles"]["staff"])
    async def boosters(self, ctx: context.ApplicationContext):
        """
        Slash command for getting the current list of server boosters.

        Args:
            ctx (Context): The context of the slash command.
        """
        await ctx.defer()

        embed = embeds.make_embed(
            ctx=ctx,
            title=f"Total boosts: {ctx.guild.premium_subscription_count}",
            thumbnail_url="https://i.imgur.com/22ZZG7h.png",
            color="nitro_pink",
            author=False
        )
        embed.description = "\n".join(user.mention for user in ctx.guild.premium_subscribers)
        embed.set_footer(text=f"Total boosters: {len(ctx.guild.premium_subscribers)}")
        await ctx.respond(embed=embed)


def setup(bot: commands.Bot) -> None:
    bot.add_cog(ServerCommands(bot))
    bot.add_application_command(server)
    log.info("Commands loaded: server")
