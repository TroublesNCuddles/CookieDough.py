import json
import logging
import aiohttp
from pathlib import Path
import discord
from discord import Embed, Webhook, AsyncWebhookAdapter
from discord.ext import commands

IMAGE_SUFFIXES = {'.gif', '.jpeg', '.jpg', '.png', '.mp4', '.webm'}
IMAGE_AND_JSON_SUFFIXES = set(IMAGE_SUFFIXES)
IMAGE_AND_JSON_SUFFIXES.add('.json')


def snake_to_camel(name):
    """Converts snake_case to CamelCase"""
    return "".join(word.capitalize() for word in name.split("_"))


def snake_to_title(name):
    """Converts snake_case to Title Case"""
    return " ".join(word.capitalize() for word in name.split("_"))


class Stickers(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.category_sticker_names = dict()
        self.category_names = []
        self._walk_root()

    def _walk_root(self):
        """Registers sticker commands for each image in each category
        category can be configured with .json file of the same name
        prefix will append the string to all the stickers inside
        """
        root = Path('./stickers')
        root.mkdir(exist_ok=True)

        for category_path in root.iterdir():
            if category_path.is_dir():
                category_config = {
                    'hidden': True,
                    'name': snake_to_camel(category_path.stem),
                    'prefix': '',
                    'message': f'{snake_to_title(category_path.stem)} stickers\n```{{}}```',
                    'file': None
                }

                # Try to find path to thumbnail
                for ext in IMAGE_SUFFIXES:
                    thumb_path = root / f'{category_path.stem}{ext}'
                    if thumb_path.exists():
                        category_config['file'] = thumb_path
                        break

                try:
                    with category_path.with_suffix('.json').open() as fp:
                        category_config.update(json.load(fp))
                except IOError as e:
                    pass  # Ignore if not found

                category_name = category_config['name']
                self.category_names.append(category_name)

                # config_str = f' {category_config}' if category_config else ''
                # print(f'{category_path}{config_str}')

                sticker_names = self._walk_category(category_path, prefix=category_config['prefix'])

                self.category_sticker_names[category_name] = sticker_names

                category_config['sticker_names'] = sticker_names

                cmd = self._category_command(category_config)
                self.bot.add_command(cmd)

    def _category_command(self, config):
        """Generate a dynamic category command object"""
        hidden = config['hidden']
        name = config['name']
        file = config['file']
        message = config['message']
        sticker_names = config['sticker_names']

        formatted_message = message.format(" ".join(sticker_names)).strip()

        async def callback(cog, ctx):
            final_file = None if file is None else discord.File(file)
            await ctx.send(formatted_message, file=final_file)

        cmd = commands.Command(
            callback,
            hidden=hidden,  # Don't show category commands in the usual help
            name=name,
            help=f'Info about {name} sticker category'
        )

        cmd.cog = self

        return cmd

    def _walk_category(self, category_path: Path, prefix=""):
        """Registers commands for all the stickers inside
        sticker can be configured with .json file
        returns the name of all the commands
        """
        sticker_names = []

        sticker_dict = dict()

        # Collect image and config for each image
        for sticker_path in category_path.iterdir():
            if sticker_path.is_file() and sticker_path.suffix in IMAGE_AND_JSON_SUFFIXES:
                key = sticker_path.stem
                if key not in sticker_dict:
                    # Sticker Config Defaults
                    sticker_dict[key] = {
                        'hidden': True,
                        'name': f'{prefix}{snake_to_camel(sticker_path.stem)}',
                        'aliases': [],
                        'message': '',
                        'file': None,
                    }
                sticker_config = sticker_dict[key]

                if sticker_path.suffix in IMAGE_SUFFIXES:
                    sticker_config['file'] = sticker_path
                else:
                    try:
                        with sticker_path.with_suffix('.json').open() as fp:
                            sticker_config.update(json.load(fp))
                    except IOError as e:
                        pass  # Ignore if not found

        # Create and add a dynamic command for each config object
        for sticker_config in sticker_dict.values():
            sticker_names.append(sticker_config['name'])

            # print(f'{sticker_path} {sticker_config}')
            cmd = self._sticker_command(sticker_config)
            self.bot.add_command(cmd)

        return sticker_names

    def _sticker_command(self, config):
        """Generate a dynamic sticker command object"""
        name = config['name']
        file = config['file']
        aliases = config['aliases']
        message = config['message']
        hidden = config['hidden']

        async def callback(cog, ctx):
            log = logging.getLogger("cogs.stickers")
            final_file = None if file is None else discord.File(file)
            channel_name = ctx.channel.name
            wh_info_found = None
            for wh_info in await ctx.guild.webhooks():
                if wh_info.channel.name == channel_name and wh_info.token is not None:
                    wh_info_found = wh_info
                    break
            if wh_info_found is None:
                await ctx.send(
                    f'Missing webhook for #{channel_name}',
                    delete_after=8)
                return
            async with aiohttp.ClientSession() as session:
                webhook = Webhook.from_url(wh_info_found.url, adapter=AsyncWebhookAdapter(session))
                if webhook is None:
                    log.error(f'Unable find a webhook in #{channel_name}!')
                    await ctx.send(f'Unable find a webhook in #{channel_name}!', delete_after=8)
                    return
                await ctx.message.delete()
                await webhook.send(avatar_url=f'{ctx.author.avatar_url}', username=ctx.author.display_name, content=message, file=final_file)


        cmd = commands.Command(callback, hidden=hidden, name=name, aliases=aliases, help=f'Send {name} sticker')
        cmd.cog = self
        return cmd

    @commands.command()
    async def stickers(self, ctx):
        """Prints out a list of sticker categories"""
        categories = " ".join(self.category_names)
        await ctx.send(f'Here\'s a list of our sticker packs!\nType `{self.bot.command_prefix}[pack-name]` to see a list of the stickers inside of that pack.```{categories}``` Also, you can add stickers in the `!shop`!'.strip())


def setup(bot):
    bot.add_cog(Stickers(bot))
