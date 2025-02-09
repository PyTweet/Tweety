import discord
import random
import pytweet

from twitter import Account
from discord import ButtonStyle
from discord.ext import commands
from discord.ui import View, Button, Select
from pytweet import Tweet
from typing import Optional, List, Union, Callable
from twitter import TwitterUser

MAXIMUM_INTERACTION_ATTEMPTS = 10

def to_dict(raw_data, **keys):
    data = {}
    if not raw_data:
        return None
    for k, v in zip(list(keys.keys()), raw_data):
        data[k] = v
    return data

def to_keycap(c):
    return "\N{KEYCAP TEN}" if c == 10 else str(c) + "\u20e3"


def format_mentioned(text):
    if not len(text) > 0:
        return "*User doesnt provide a bio*"

    original_split = text.split(" ")
    bio = (
        text.replace("@", "[@")
        .replace("#", "[#")
        .replace("PyTweet", "[PyTweet")
        .replace("pytweet", "[pytweet")
    )
    split_bio = bio.split(" ")
    complete = ""
    for num, word in enumerate(split_bio):
        before_word = ""
        if "." in word and not "t.co" in word:
            before_word += "."
            word = word.replace(".", "")

        if "[" in word:
            if "#" in word:
                values = original_split[num].replace("#", "").split("\n")
                for value in values:
                    if value and value.startswith("[#"):
                        value = value
                        
                complete += f" {word}](https://twitter.com/hashtag/{value}?src=hashtag_click){before_word}"
            elif "@" in word:
                values = original_split[num].replace("@", "").split("\n")
                for value in values:
                    if value and value.startswith("[@"):
                        value = value
                        
                complete += f" {word}](https://twitter.com/{value}){before_word}"
            elif "pytweet" in word.lower():  # ;)
                complete += f" {word}](https://github.com/PyTweet/PyTweet){before_word}"

        else:
            complete += " " + word

    return complete if len(complete) <= 4096 else text #4096 Is the maximum characters in embed description.


def get_badges(ctx, user) -> str:
    text = ""
    badges = ["✅ ", "🔒 ", "⚒️ "]
    if user.verified:
        text += badges[0]
    if user.protected:
        text += badges[1]
    if user.id in ctx.bot.twitter_dev_ids:
        text += badges[2]
    return text


class DisplayModels:
    def __init__(self, bot):
        self.bot = bot

    async def check_interaction_attempts(self, inter: discord.Interaction, attempts: int, timeout: Callable):
        if attempts == MAXIMUM_INTERACTION_ATTEMPTS:
            await inter.response.send_message("Maximum interaction attempts between you and the tweet(s) has exceeded!")
            await timeout()
            return 0
        return 1

    async def display_user(
        self,
        ctx: commands.Context,
        user: Union[discord.User, discord.Member, TwitterUser],
        author: Union[discord.User, discord.Member, TwitterUser]
    ):
        tweet_options = []
        dm_message_options = []
        keycaps = [to_keycap(x) for x in range(1, 8)]
        view = View(timeout=200.0)
        interaction_attempts = 0
        buttons = [
            Button(
                label=f"{user.follower_count} Followers",
                emoji="🤗",
                style=ButtonStyle.blurple,
            ),
            Button(
                label=f"{user.following_count} Following",
                emoji="🤗",
                style=ButtonStyle.blurple,
            ),
            Button(
                label=f"{user.tweet_count} Tweets",
                emoji="<:retweet:914877560142299167>",
                style=ButtonStyle.blurple,
            ),
            Button(
                label=f"Send Message",
                emoji="💬",
                row=3,
                style=ButtonStyle.blurple,
            )
        ]

        async def follow(inter):
            nonlocal interaction_attempts
                
            if inter.user.id != ctx.author.id:
                await inter.response.send_message("This is not for you", ephemeral=True)
                return

            user_id = await (await self.bot.db_cursor.execute("SELECT user_id FROM main WHERE discord_user_id = ?", (ctx.author.id,))).fetchone()

            if user.id == user_id:
                buttons[0].disabled = True
                if isinstance(message, discord.Interaction):
                    try:
                        await message.edit_original_message(view=view)
                    except Exception as e:
                        raise e
                else:
                    try:
                        await message.edit(view=view)
                    except Exception as e:
                        raise e
                await ctx.send("You cannot follow yourself!")
                return

            user.follow()
            num, label = buttons[0].label.split(" ")
            buttons[0].label = str(int(num) + 1) + " " + label
            buttons[0].disabled = True
            if isinstance(message, discord.Interaction):
                try:
                    await message.edit_original_message(view=view)
                except Exception as e:
                    raise e
            else:
                try:
                    await message.edit(view=view)
                except Exception as e:
                    raise e
            await inter.response.send_message(
                f"Followed {user.username}!", ephemeral=True
            )
            result = await self.check_interaction_attempts(inter, interaction_attempts, timeout)
            if not result:
                return

        async def message(inter):
            nonlocal interaction_attempts
                
            if inter.user.id != ctx.author.id:
                await inter.response.send_message("This is not for you", ephemeral=True)
                return

            await inter.response.send_message("Send a message, you have 2 minutes to do this!")
            message = await self.bot.wait_for("message", check=lambda msg: msg.author.id == inter.user.id and msg.channel.id == inter.channel_id, timeout=120)
            dm_message = user.send(message.content)
            await ctx.send(f"Sent message to {user.mention}!")
            await ctx.author.send(f"[{dm_message.created_at:%d/%m/%Y}] You({author.username}): {dm_message.text}")
            interaction_attempts += 1
            result = await self.check_interaction_attempts(inter, interaction_attempts, timeout)
            if not result:
                return

        async def display_tweet(inter):
            nonlocal interaction_attempts
                
            if inter.user.id != ctx.author.id:
                await inter.response.send_message("This is not for you", ephemeral=True)
                return

            index = inter.data["values"][0]
            await self.display_tweet(
                ctx,
                tweets[int(index) - 1] if index.isdigit() else index,
                inter,
                replace_user_with=user,
            )
            interaction_attempts += 1
            result = await self.check_interaction_attempts(inter, interaction_attempts, timeout)
            if not result:
                return

        async def display_direct_message(inter):
            nonlocal interaction_attempts
            
            if inter.user.id != ctx.author.id:
                await inter.response.send_message("This is not for you", ephemeral=True)
                return

            index = inter.data["values"][0]
            
            await self.display_direct_message(
                ctx,
                dm_messages[int(index) - 1] if index.isdigit() else index,
                inter,
            )
            interaction_attempts += 1
            result = await self.check_interaction_attempts(inter, interaction_attempts, timeout)
            if not result:
                return

        async def timeout():
            for child in view.children:
                child.disabled = True
                
            if isinstance(message, discord.Interaction):
                try:
                    await message.edit_original_message(view=view)
                except Exception as e:
                    raise e
            else:
                try:
                    await message.edit(view=view)
                except Exception as e:
                    raise e
        
        dm_messages = None
        tweets = None
        try:
            tweets = user.fetch_timelines(exclude="replies,retweets")
            if isinstance(user, Account):
                dm_messages = user.client.fetch_message_history()
            elif isinstance(author, Account):
                dm_messages = author.client.fetch_message_history()

            if dm_messages:
                dm_messages = dm_messages.content[0:7]
            if tweets:
                tweets = tweets.content[0:7]
            
        except (pytweet.PyTweetException):
            pass
        else:
            if tweets:
                for num, keycap, tweet in zip(range(1, 8), keycaps, tweets):
                    if user.protected and not tweets:
                        break
        
                    else:
                        tweet_options.append(
                            discord.SelectOption(
                                label=f"({tweet.created_at:%d/%m/%Y}) {tweet.text[:25]}{'...' if len(tweet.text) > 25 else ''}",
                                value=str(num),
                                description="(click to see full result)"
                                if len(tweet.text) > 25
                                else "",
                                emoji=keycap,
                                default=False,
                            )
                        )

            if dm_messages:
                dm_messages = list(filter(lambda msg: msg.author.id == user.id and msg.recipient.id == author.id, dm_messages))
                for num, keycap, dm_message in zip(range(1, 8), keycaps, dm_messages):
                    if user.protected and not dm_messages:
                        break
        
                    else:
                        dm_message_options.append(
                            discord.SelectOption(
                                label=f"({dm_message.created_at:%d/%m/%Y}) {dm_message.text[:25]}{'...' if len(dm_message.text) > 25 else ''}",
                                value=str(num),
                                description="(click to see full result)"
                                if len(dm_message.text) > 25
                                else "",
                                emoji=keycap,
                                default=False,
                            )
                        )
            
        buttons[0].callback = follow
        buttons[3].callback = message

        unknown_tweet = True if not tweets and not user.protected else False
        unknown_message_history = True if not dm_messages and not user.protected else False
        tweet_placeholder = "(Recent User Timelines)"
        dm_message_placeholder = "(Message History With You)"
        if user.protected:
            tweet_placeholder = "(User Is Protected)"
            dm_message_placeholder = "(User Is Protected)"
        elif not user.protected and unknown_tweet:
            tweet_placeholder = "(Unknown Timelines)"
        elif user.protected and tweets:
            tweet_placeholder = "(Granted Access For Protected User Timelines)"

        
        if not user.protected and unknown_message_history:
            dm_message_placeholder = "(Unknown Message History)"
        elif user.protected and unknown_message_history:
            dm_message_placeholder = "(Granted Access For Protected User Message History)"
            
    
        if tweet_options:
            pass
            
        elif user.protected:
            tweet_options = [
                discord.SelectOption(
                    label="???",
                    value="protected",
                    description="Cannot fetch user timelines...\n User is protected!",
                    default=False,
                )
            ]
        else:
            tweet_options = [
                discord.SelectOption(
                    label="???",
                    value="unknown",
                    description="User has empty timelines!",
                    default=False,
                )
            ]

        if not dm_messages:
            dm_message_options = [
                discord.SelectOption(
                    label="???",
                    value="unknown",
                    description="Unknown Message History!",
                    default=False,
                )
            ]

        selects = [
            Select(placeholder=tweet_placeholder, options=tweet_options),
            Select(placeholder=dm_message_placeholder, options=dm_message_options)
        ]

        for button in buttons:
            view.add_item(button)
        for select in selects:
            if "Timelines" in select.placeholder:
                select.callback = display_tweet
            elif "Message" in select.placeholder:
                select.callback = display_direct_message
            view.add_item(select)
            
        bio = format_mentioned(user.bio)
        badges = get_badges(ctx, user)
        em = (
            discord.Embed(
                title=user.name + " " + badges,
                url=user.profile_url,
                description=f"{bio}\n\n:link: {user.url if len(user.url) > 0 else '*This user doesnt provide a link*'} • <:compas:879722735377469461> {user.location if len(user.location or '') > 0 else '*This user doesnt provide a location*'}",
                color=discord.Color.blue(),
            )
            .set_author(
                name=user.username + f"({user.id})",
                icon_url=user.profile_image_url,
                url=user.profile_url,
            )
            .set_footer(
                text=f"Created Time: {user.created_at:%d/%m/%Y}",
                icon_url=user.profile_image_url,
            )
        )

        view.on_timeout = timeout
        message = await ctx.send(embed=em, view=view)

    async def display_tweet(
        self,
        ctx: Optional[commands.Context] = None,
        tweet: Optional[Tweet] = None,
        method: Optional[Union[commands.Context, discord.Interaction]] = None,
        *,
        client=None,
        replace_user_with=None,
    ):
        interaction_attempts = 0
        user = tweet.author if isinstance(tweet, Tweet) else None
        medias = tweet.medias
        buttons = [
            Button(
                label=f"{tweet.like_count} Likes",
                emoji="👍",
                style=discord.ButtonStyle.blurple,
            ),
            Button(
                label=f"{tweet.retweet_count} Retweets",
                emoji="<:retweet:914877560142299167>",
                style=discord.ButtonStyle.blurple,
            ),
            Button(
                label=f"{tweet.reply_count} Replies",
                emoji="🗨️",
                style=discord.ButtonStyle.blurple,
            ),
            Button(
                label=f"{tweet.quote_count} Quotes",
                emoji="💬",
                style=discord.ButtonStyle.blurple,
                row=2,
            ),
            Button(
                label=f"{len(medias)} Media(s)" if medias else "No Media Available",
                emoji="<:images:879722735817850890>",
                style=discord.ButtonStyle.green,
                row=2,
            )
        ]
        
        if not client:
            client = await self.bot.get_twitter_user(ctx.author.id, ctx)
        if not user:
            user = replace_user_with
        if not method:
            method = ctx
        if not isinstance(tweet, Tweet):
            if isinstance(method, discord.Interaction):
                await method.response.send_message(
                    f"Unknown tweet! {'Cannot fetch timelines, user is protected!' if tweet == 'protected' else 'User has no tweets timelines!'}",
                    ephemeral=True,
                )

            elif isinstance(method, commands.Context):
                await method.send(
                    f"Unknown tweet! {'Cannot fetch timelines, user is protected!' if tweet == 'protected' else 'User has no tweets timelines!'}"
                )
            return

        async def like(inter):
            nonlocal interaction_attempts
                
            if inter.user.id != ctx.author.id:
                await inter.response.send_message("This is not for you", ephemeral=True)
                return

            tweet.like()
            await inter.response.send_message(
                f"{client.twitter_account.username} Liked the tweet!", ephemeral=True
            )
            num, label = buttons[0].label.split(" ")
            buttons[0].label = str(int(num) + 1) + " " + label
            buttons[0].disabled = True
            if isinstance(message, discord.Interaction):
                try:
                    await message.edit_original_message(view=view)
                except Exception as e:
                    raise e
            else:
                try:
                    await message.edit(view=view)
                except Exception as e:
                    raise e
            interaction_attempts += 1
            result = await self.check_interaction_attempts(inter, interaction_attempts, timeout)
            if not result:
                return

        async def retweet(inter):
            nonlocal interaction_attempts
                
            if inter.user.id != ctx.author.id:
                await inter.response.send_message("This is not for you", ephemeral=True)
                return

            tweet.retweet()
            await inter.response.send_message(
                f"{client.twitter_account.username} retweeted the tweet!",
                ephemeral=True,
            )
            num, label = buttons[1].label.split(" ")
            buttons[1].label = str(int(num) + 1) + " " + label
            buttons[1].disabled = True
            if isinstance(message, discord.Interaction):
                try:
                    await message.edit_original_message(view=view)
                except Exception as e:
                    raise e
            else:
                try:
                    await message.edit(view=view)
                except Exception as e:
                    raise e
            interaction_attempts += 1
            result = await self.check_interaction_attempts(inter, interaction_attempts, timeout)
            if not result:
                return

        async def quote(inter):
            nonlocal interaction_attempts

            await inter.response.send_message("Send your quote message, you have a minute to do this!")
            quote_message = await self.bot.wait_for("message", check=lambda msg: msg.author.id == inter.user.id and msg.channel.id == inter.channel_id, timeout=60)
            quoted_tweet = client.twitter_account.client.tweet(quote_message.content, quote_tweet=tweet)
            await ctx.send(f"Quoted the tweet! {quoted_tweet.url}")

            num, label = buttons[3].label.split(" ")
            buttons[3].label = str(int(num) + 1) + " " + label
            buttons[3].disabled = True
            if isinstance(message, discord.Interaction):
                try:
                    await message.edit_original_message(view=view)
                except Exception as e:
                    raise e
            else:
                try:
                    await message.edit(view=view)
                except Exception as e:
                    raise e
            interaction_attempts += 1
            result = await self.check_interaction_attempts(inter, interaction_attempts, timeout)
            if not result:
                return

        async def reply(inter):
            nonlocal interaction_attempts
                
            if inter.user.id != ctx.author.id:
                await inter.response.send_message("This is not for you", ephemeral=True)
                return

            await inter.response.send_message("Send your reply message, you have a minute to do this!")
            reply_message = await self.bot.wait_for("message", check=lambda msg: msg.author.id == inter.user.id and msg.channel.id == inter.channel_id, timeout=60)
            reply_tweet = tweet.reply(reply_message.content)
            await ctx.send(f"Replied to the tweet! {reply_tweet.url}")
            
            number, label = buttons[2].label.split(" ")
            buttons[2].label = str(int(number) + 1) + " " + label
            if isinstance(message, discord.Interaction):
                try:
                    await message.edit_original_message(view=view)
                except Exception as e:
                    raise e
            else:
                try:
                    await message.edit(view=view)
                except Exception as e:
                    raise e
            interaction_attempts += 1
            result = await self.check_interaction_attempts(inter, interaction_attempts, timeout)
            if not result:
                return

        async def images(inter):
            nonlocal interaction_attempts
                
            if inter.user.id != ctx.author.id:
                await inter.response.send_message("This is not for you", ephemeral=True)
                return

            if not medias:
                await inter.response.send_message("No media available for this tweet!")
                return

            if len(medias) > 1:
                embed = em.copy()
                img = random.choice(medias)
                embed.set_image(
                    url=img.url
                    if img.type == pytweet.MediaType.photo
                    else img.preview_image_url
                )
                if isinstance(message, discord.Interaction):
                    try:
                        await message.edit_original_message(embed=embed)
                    except Exception as e:
                        raise e
                else:
                    try:
                        await message.edit(embed=embed)
                    except Exception as e:
                        raise e

            else:
                await inter.response.send_message(
                    "No more images available!", ephemeral=True
                )

            interaction_attempts += 1
            result = await self.check_interaction_attempts(inter, interaction_attempts, timeout)
            if not result:  
                return

        async def timeout():
            for child in view.children:
                child.disabled = True

            await message.edit(view=view)

        callbacks = [like, retweet, reply, quote, images] 

        if isinstance(ctx.channel, discord.TextChannel) and not ctx.channel.is_nsfw() and tweet.sensitive:
            if isinstance(method, discord.Interaction):
                await method.response.send_message(
                "This tweet has a sensitive content and might ends up as nsfw, gore, and disturbing content. Use this command in nsfw channel!",
                ephemeral=True,
            )
            elif isinstance(method, commands.Context):
                await method.send(
                "This tweet has a sensitive content and might end up as nsfw, gore, and other disturbing contents. Use this command in nsfw channel!"
            )
                
            return

        try:
            link = tweet.link
        except (TypeError, AttributeError):
            link = f"https://twitter.com/{user.username.replace('@', '', 1)}/status/{str(tweet.id)}"

        text = format_mentioned(tweet.text)
        em = (
            discord.Embed(
                title=user.name + " " + get_badges(ctx, user),
                url=link,
                description=text,
                color=discord.Color.blue()
                if not tweet.sensitive
                else discord.Color.red(),
            )
            .set_author(
                name=user.username + f"({user.id})",
                icon_url=user.profile_image_url,
                url=user.profile_url,
            )
            .set_footer(
                text=f"Conversation ID: {tweet.conversation_id}",
                icon_url=user.profile_image_url,
            )
            .add_field(name="Created At:", value=tweet.created_at.strftime("%d/%m/%Y"))
            .add_field(name="Reply Setting", value=tweet.raw_reply_setting)
            .add_field(
                name="Source",
                value=f"[{tweet.source}](https://help.twitter.com/en/using-twitter/how-to-tweet#source-labels)",
            )
        )

        if medias:
            img = random.choice(medias)
            em.set_image(
                url=img.url
                if img.type is pytweet.MediaType.photo
                else img.preview_image_url
            )

        view = View(timeout=200.0)
        view.on_timeout = timeout

        for num, callback in enumerate(callbacks):
            buttons[num].callback = callback
            view.add_item(buttons[num])

        if isinstance(method, discord.Interaction):
            message = await method.response.send_message(
                content="You know you can do: `e!tweet <tweet_id>` to see other tweet's info!\nlooks like this tweet has a poll, mind checking that out with `e!poll <tweet_id>`?"
                if tweet.id == 1465231032760684548 and tweet.poll
                else "You know you can do: `e!tweet <tweet_id>` to see other tweet's info!"
                if tweet.id == 1465231032760684548
                else "looks like this tweet has a poll, mind checking that out with `e!poll <tweet_id>`?"
                if tweet.poll
                else "",
                embed=em,
                view=view,
                ephemeral=True,
            )

        else:
            if tweet.id == 1465231032760684548:
                await method.send(
                    "You can use: `e!tweet <tweet_id>` to see other tweet's info!"
                )

            if tweet.poll:
                await method.send(
                    "looks like this tweet has a poll, mind checking that out with `e!poll <tweet_id>`?"
                )

            message = await method.send(embed=em, view=view)

    async def display_direct_message(
        self,
        ctx: Optional[commands.Context],
        direct_message: Optional[pytweet.DirectMessage],
        method: Optional[Union[discord.Interaction, commands.Context]]
    ):
        if not isinstance(direct_message, pytweet.DirectMessage):
            if isinstance(method, discord.Interaction):
                await method.response.send_message(
                    f"Unknown direct message! {'Cannot fetch message history, user is protected!' if direct_message == 'protected' else 'User has no message history with you!'}",
                    ephemeral=True,
                )

            elif isinstance(method, commands.Context):
                await method.send(
                    f"Unknown direct message! {'Cannot fetch message history, user is protected!' if direct_message == 'protected' else 'User has no message history with you!'}"
                )
            return
            
        recipient = direct_message.recipient
        author = direct_message.author
        badges = get_badges(ctx, author)
        em = discord.Embed(
            title=f"Viewing {recipient.username}'s Message For You!",
            description=f"**[<t:{int(direct_message.created_at.timestamp())}:R> {author.username + ' ' + badges}]: __{format_mentioned(direct_message.text)}__**\n",
            color=discord.Color.blue(),
            url=f"https://twitter.com/messages/{recipient.id}-{author.id}"
        ).set_author(
            name=recipient.username,
            url=f"https://twitter.com/messages/{recipient.id}-{author.id}",
            icon_url=recipient.profile_image_url
        )

        if isinstance(method, commands.Context):
            try:
                await method.send(embed=em)
            except Exception as e:
                raise e
        elif isinstance(method, discord.Interaction):
            try:
                await method.response.send_message(embed=em, ephemeral=True)
            except Exception as e:
                raise e

    async def display_direct_messages(
        self,
        ctx,
        method: commands.Context,
        direct_messages: List[pytweet.DirectMessage],
    ):
        
        em = discord.Embed(
            title="Viewing Message History!",
            description="",
            color=discord.Color.blue()
        ).set_author(
            direct_messages[0].author.username + "+" + direct_messages[0].recipient.username, 
            f"https://twitter.com/messages/{direct_messages[0].author.id}-{direct_messages[0].recipient.id}",
        )

        for direct_message in direct_messages:
            badges = get_badges(ctx, direct_message.author)
            em.description += f"<t:{direct_message.created_at.timestamp()}:F>**[{direct_message.author.username + badges}]:** {direct_message.text}\n"
        
        if isinstance(method, commands.Context):
            try:
                await method.send(embed=em)
            except Exception as e:
                raise e
        elif isinstance(method, discord.Interaction):
            try:
                await method.response.send_message(embed=em)
            except Exception as e:
                raise e
                