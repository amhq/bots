from dataclasses import dataclass
from typing import Optional

import discord
from discord.ext import commands as util


@dataclass
class Channel:
    """Newtype that wraps a `discord.TextChannel`

    This type looks up channels by default relative to the current server.
    It also allows references to channels in another server."""

    _inner: discord.TextChannel

    def __repr__(self) -> str:
        """Return a string in the form Server@Channel."""
        return f"{self._inner.guild.name}@{self._inner.name}"

    async def send(self, msg: str) -> discord.Message:
        return await self._inner.send(msg)

    @classmethod
    async def convert(cls, ctx: util.Context, path: str) -> Optional["Channel"]:
        """Create a `Channel` from a string of the form Server@Channel.

        This class's name cannot be changed, as it is used automatically by discord.py

        Arguments:
        - ctx: The discord context. Contains the server this was called in.
        - path: Path to the channel name, either relative or absolute."""
        try:  # Fails if the channel path isn't in the current server.
            channel: discord.TextChannel = await util.TextChannelConverter().convert(
                ctx, path
            )
            return cls(channel)
        except util.BadArgument:  # Channel is in another server.
            [guild_name, channel_name] = path.split("@")[:2]
            guild = await util.GuildConverter().convert(ctx, guild_name)
            for channel in guild.text_channels:
                if channel.name == channel_name:
                    return cls(channel)
