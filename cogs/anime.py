from __future__ import annotations

from typing import TYPE_CHECKING, Self

import discord
from discord import app_commands
from discord.ext import commands

from utils import WAIFU_TOKEN, Embed, WaifuIm, WaifuImImage, better_string

if TYPE_CHECKING:
    from aiohttp import ClientSession

    from bot import Lagrange


class SmashOrPass(discord.ui.View):
    message: discord.Message
    current: WaifuImImage

    def __init__(self, session: ClientSession, *, for_user: int) -> None:
        super().__init__(timeout=500.0)
        self.session = session
        self.for_user = for_user

        self.smashers: set[discord.User | discord.Member] = set()
        self.passers: set[discord.User | discord.Member] = set()

    @classmethod
    async def start(cls, ctx: commands.Context[Lagrange]) -> Self:
        inst = cls(ctx.bot.session, for_user=ctx.author.id)
        data = await inst.request()

        embed = inst.embed(data)
        inst.message = await ctx.reply(embed=embed, view=inst)

        return inst

    async def request(self) -> WaifuImImage:
        raise NotImplementedError

    def embed(self, data: WaifuImImage) -> discord.Embed:
        raise NotImplementedError

    @discord.ui.button(
        emoji='<:smash:1276874474628583497>',
        style=discord.ButtonStyle.green,
    )
    async def smash(self, interaction: discord.Interaction[Lagrange], _: discord.ui.Button[Self]) -> None:
        if interaction.user in self.smashers:
            return await interaction.response.defer()

        if interaction.user in self.passers:
            self.passers.remove(interaction.user)

        self.smashers.add(interaction.user)
        await interaction.response.edit_message(embed=self.embed(self.current))
        return None

    @discord.ui.button(
        emoji='<:pass:1276874515296813118>',
        style=discord.ButtonStyle.red,
    )
    async def passbutton(self, interaction: discord.Interaction[Lagrange], _: discord.ui.Button[Self]) -> None:
        if interaction.user in self.passers:
            return await interaction.response.defer()

        if interaction.user in self.smashers:
            self.smashers.remove(interaction.user)

        self.passers.add(interaction.user)
        await interaction.response.edit_message(embed=self.embed(self.current))
        return None

    @discord.ui.button(emoji='🔁', style=discord.ButtonStyle.grey)
    async def _next(self, interaction: discord.Interaction[Lagrange], _: discord.ui.Button[Self]) -> None:
        self.smashers.clear()
        self.passers.clear()

        data = await self.request()
        await interaction.response.edit_message(embed=self.embed(data))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not self.for_user:
            return True

        if (
            interaction.user.id != self.for_user
            and interaction.data
            and interaction.data['custom_id'] == self._next.custom_id  # pyright: ignore[reportGeneralTypeIssues]
        ):
            await interaction.response.send_message(
                'Only the command initiator can cycle through waifus in this message.',
                ephemeral=True,
            )

            return False

        return True

    async def on_timeout(self) -> None:
        await self.message.edit(view=None)
        self.stop()


class WaifuView(SmashOrPass):
    async def request(self) -> WaifuImImage:
        waifu = await self.session.get(
            'https://api.waifu.im/search',
            params={
                'is_nsfw': 'false',
                'token': WAIFU_TOKEN,
            },
        )

        data: WaifuIm = await waifu.json()
        self.current = data['images'][0]

        return self.current

    def embed(self, data: WaifuImImage) -> discord.Embed:
        smasher = ', '.join(smasher.mention for smasher in self.smashers) if self.smashers else ''
        passer = ', '.join(passer.mention for passer in self.passers) if self.passers else ''

        embed = Embed(
            title='Smash or Pass',
            description=better_string(
                [
                    f'> [#{data["image_id"]}]({data["source"]})',
                    '<:smash:1276874474628583497> **Smashers:** ' + smasher,
                    '<:pass:1276874515296813118> **Passers:** ' + passer,
                ],
                seperator='\n',
            ),
            colour=discord.Colour.from_str(data['dominant_color']),
        )

        embed.set_image(url=data['url'])

        return embed


class Anime(commands.Cog):
    def __init__(self, bot: Lagrange) -> None:
        self.bot = bot

    @commands.hybrid_command(name='waifu')
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    @commands.bot_has_permissions(external_emojis=True, embed_links=True, attach_files=True)
    async def waifu(self, ctx: commands.Context[Lagrange]) -> None:
        view = WaifuView(self.bot.session, for_user=ctx.author.id)
        await view.start(ctx)


async def setup(bot: Lagrange) -> None:
    await bot.add_cog(Anime(bot))
