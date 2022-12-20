"""The entry point for hilda."""

import asyncio
import logging
from typing import Optional, TypeVar

import arrow
import coloredlogs
import discord
from discord.ext import commands as util
from dotenv import dotenv_values

from channel import Channel
from sheet import Sheet

# Setup logging to log INFO to stdout.
log = logging.getLogger(__name__)
coloredlogs.install(level="INFO")

# Load the bot token and formatting sheet. Also check if we're running locally.
# Note that the formatting sheet is just a markdown file.
BOT_TOKEN: str | None = dotenv_values(".env")["BOT_TOKEN"]
RUNNING_LOCALLY: bool = bool(dotenv_values(".env")["RUNNING_LOCALLY"])
SHEET: Sheet = Sheet.from_file("sheet.md")

# The name used for the backup file.
BACKUP_NAME: str = "Backup of {guild}@{channel} at {date}"


def fmt(msg: discord.Message) -> str:
    """Convert a `discord.Message` into a neatly formatted str.

    The format styling is taken from a local file called sheet.md.

    Arguments:
    - msg: The message to format."""
    assert isinstance(msg.channel, discord.TextChannel)
    return SHEET["msg"].format(
        author=msg.author.mention,
        guild=msg.guild,
        channel=msg.channel.mention,
        date=arrow.get(msg.created_at).humanize(),
        content=msg.content,
    )


T = TypeVar("T")


def get(lst: list[T], index: int, default: T) -> T:
    try:
        return lst[index]
    except IndexError:
        return default


async def audit(ctx: util.Context) -> Optional[discord.Message]:
    """Writes `msg` to an #audit channel, if it exists."""
    assert (
        ctx.guild is not None
        and ctx.command is not None
        and isinstance(ctx.channel, discord.TextChannel)
    )
    audit_channel: Optional[discord.TextChannel] = discord.utils.get(
        ctx.guild.channels, name="audit"
    )  # type: ignore
    if audit_channel is not None:
        try:
            return await audit_channel.send(
                SHEET[ctx.command.name].format(
                    author=ctx.author.mention,
                    guild=ctx.guild,
                    channel=ctx.channel.mention,
                    amt=get(ctx.args, 1, ""),
                    new_channel=get(ctx.args, 2, ""),
                    members=get(ctx.args, 2, []),
                )
            )
        except KeyError:
            return


# Create a discord bot that activates with `!` or when mentioned.
bot = util.Bot(util.when_mentioned_or("!"), intents=discord.Intents.all())


@bot.event
async def on_ready() -> None:
    log.info("Hilda is ready for some action!")


@bot.event
async def on_command_error(ctx: util.Context, error: Exception) -> None:
    """Log all errors to stderr, and handle some of them as well."""
    log.error(f"Exception {error} was raised from {ctx.command}")
    if isinstance(error, util.NoPrivateMessage):
        await ctx.reply("Hilda only works in servers!")


@bot.before_invoke
async def before_invoke(ctx: util.Context) -> None:
    assert ctx.command is not None
    await ctx.message.delete()
    await audit(ctx)


@bot.command()
@util.guild_only()
async def bobbin(ctx: util.Context, amt: Optional[int], name: str) -> None:
    """Create a new thread and move the last `amt` messages to it.

    If amt is not passed then the whole channel's messages are moved. The
    messages are formatted according to a `sheet.md` file.

    Arguments:
    - ctx: The discord context.
    - amt: The number of messages to move.
    - name: The name of the thread to create."""
    assert isinstance(ctx.channel, discord.TextChannel)

    thread: discord.Thread = await ctx.channel.create_thread(
        name=name, type=discord.ChannelType.public_thread
    )

    msgs: list[discord.Message] = await ctx.channel.purge(limit=amt)
    msgs.sort(key=lambda msg: msg.created_at)
    for msg in msgs:
        await thread.send(fmt(msg))


@bot.command()
@util.guild_only()
async def pin(ctx: util.Context, amt: Optional[int]) -> None:
    """Pins the last `amt` messages to a channel.

    Arguments:
    - ctx: The discord context.
    - amt: The number of messages to pin."""
    assert isinstance(ctx.channel, discord.TextChannel)

    async for msg in ctx.channel.history(limit=amt):
        await msg.pin(reason="Pinned automatically by hilda.")


@bot.command()
@util.guild_only()
async def cp(ctx: util.Context, amt: Optional[int], channel: Channel) -> None:
    """Copies the last `amt` messages to a channel.

    This channel can be in a different server, as long as hilda is also present
    in that server. If `amt` is not given, it will copy the whole channel.

    Arguments:
    - ctx: The discord context.
    - amt: The number of messages to copy.
    - channel: The server and channel to copy to, in the form `Server@Channel`."""
    assert isinstance(ctx.channel, discord.TextChannel)

    async for msg in ctx.channel.history(limit=amt):
        await channel.send(fmt(msg))


@bot.command()
@util.guild_only()
async def mv(ctx: util.Context, amt: Optional[int], channel: Channel) -> None:
    """Moves the last `amt` messages to a channel.

    This channel can be in a different server, as long as hilda is also present
    in that server. If `amt` is not given, it will move the whole channel.

    Arguments:
    - ctx: The discord context.
    - amt: The number of messages to move.
    - channel: The server and channel to move to, in the form `Server@Channel`."""
    assert isinstance(ctx.channel, discord.TextChannel)

    msgs: list[discord.Message] = await ctx.channel.purge(limit=amt)
    msgs.sort(key=lambda m: m.created_at)
    for msg in msgs:
        await channel.send(fmt(msg))


@bot.command()
@util.guild_only()
async def save(ctx: util.Context, amt: Optional[int]) -> None:
    """Saves the last `amt` messages to a file.

    This command only works if a RUNNING_LOCALLY environment variable
    is set.

    Arguments:
    - ctx: The discord context.
    - amt: The number of messages to move."""

    assert isinstance(ctx.channel, discord.TextChannel) and ctx.guild is not None

    with open(
        BACKUP_NAME.format(
            guild=ctx.guild.name,
            channel=ctx.channel.name,
            date=arrow.utcnow().format("YYYY-MM-DD HH:mm:ss"),
        ),
        "w",
    ) as f:
        f.writelines([fmt(msg) async for msg in ctx.channel.history(limit=amt)])


@bot.command()
@util.guild_only()
async def rm(
    ctx: util.Context,
    amt: Optional[int],
    members: util.Greedy[discord.Member],
):
    """Deletes the last `amt` messages sent by `members` in a channel.

    If `amt` is not passed then the whole channel will be deleted.

    Arguments:
    - ctx: The discord context.
    - amt: The number of messages to delete.
    - members: The list of members whose messages will be deleted."""
    assert isinstance(ctx.channel, discord.TextChannel)

    # Confirm deletion by adding a reaction.
    msg: discord.Message = await ctx.send("React to this message to proceed.")
    try:
        await bot.wait_for("reaction_add", timeout=10.0)
    except asyncio.TimeoutError:
        await msg.edit(content="Timed out. Please try again.")
        return

    await msg.delete()

    def check(msg: discord.Message) -> bool:
        """Returns True if the message was written by someone in `members`."""
        if members != []:
            return msg.author.name in map(lambda member: member.name, members)
        return True

    await ctx.channel.purge(limit=amt, check=check)


if BOT_TOKEN is not None:
    bot.run(BOT_TOKEN)
