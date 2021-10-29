import os
import discord
import pytweet
from helpcommand import CustomHelpCommand
from discord.ext import commands

# pip install git+https://github.com/Pycord-Development/pycord
# pip install git+https://github.com/TheFarGG/PyTweet


bot = commands.Bot(
    command_prefix=commands.when_mentioned_or("e!"),
    help_command=CustomHelpCommand(),
    intents=discord.Intents.all(),
    owner_id=685082846993317953,
    status=discord.Status.idle,
    activity=discord.Activity(type=discord.ActivityType.competing, name="A Battle"),
)

bot.twitter = pytweet.Client(
    os.environ["bearer_token"],
    consumer_key=os.environ["api_key"],
    consumer_key_secret=os.environ["api_key_secret"],
    access_token=os.environ["access_token"],
    access_token_secret=os.environ["access_token_secret"],
)

@bot.event
async def on_ready():
    print(f"In online as {bot.twitter.user.username} - {bot.twitter.user.id}")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandInvokeError):
        err=error.original
        if isinstance(err, pytweet.errors.TooManyRequests):
            await ctx.send("Runtime Error. Return code: 429. Rate limit exceeded!")

        else:
            raise error

    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"Im on cooldown! Please wait {error.retry_after:.2f} seconds")

    elif isinstance(error, commands.NotOwner):
        await ctx.send(f"Only owner can do that command sus")
        ctx.command.reset_cooldown(ctx)

    else:
        raise error

@bot.command(description="Get the bot's ping")
async def ping(ctx):
    await ctx.send(f"PONG! `{round(bot.latency * 1000)}MS`")

@bot.command(description="Get a user info through the user's id or username")
@commands.cooldown(1, 10, commands.BucketType.user)
async def user(ctx, username: str):
    try:
        user = bot.twitter.get_user_by_username(username)
        await ctx.send(
            embed=discord.Embed(
                title=user.name,
                url=user.profile_link,
                description=user.bio
                if len(user.bio) > 0
                else "*User doesnt provide a bio*",
                color=discord.Color.blue(),
            )
            .set_author(
                name=user.username + f"({user.id})",
                icon_url=user.avatar_url,
                url=user.profile_link,
            )
            .set_footer(
                text=f"Created Time: {user.created_at.strftime('%Y/%m/%d')}",
                icon_url=user.avatar_url,
            )
        )

    except pytweet.errors.NotFoundError:
        await ctx.send(f"Could not find user with username(or id): [{username}].")


@bot.command(description="Get a tweet info through the tweet's id")
@commands.cooldown(1, 10, commands.BucketType.user)
async def tweet(ctx, tweet_id: int):
    try:
        tweet = bot.twitter.get_tweet(tweet_id)
        user = tweet.author
        await ctx.send(
            embed=discord.Embed(
                title=f"Posted by {user.name}",
                url=tweet.link,
                description=tweet.text,
                color=discord.Color.blue(),
            )
            .set_author(
                name=user.username + f"({user.id})",
                icon_url=user.avatar_url,
                url=user.profile_link
            )
            .set_footer(
                text=f"Created Time: {tweet.created_at.strftime('%Y/%m/%d')} | Was tweeted with: {tweet.source}",
                icon_url=user.avatar_url,
            )
            .add_field(name="Likes Count 👍", value=tweet.like_count)
            .add_field(name="Quotes Count 📰", value=tweet.quote_count)
            .add_field(name="Replies Count 🗨️", value=tweet.reply_count)
            .add_field(name="Retweetes Count 🗨️", value=tweet.retweet_count)
        )

    except pytweet.errors.NotFoundError:
        await ctx.send(f"Could not find user with username(or id): [{tweet_id}].")


@bot.command(
    description="Follow a user, only an owner of the server can do this command"
)
@commands.is_owner()
@commands.cooldown(1, 10, commands.BucketType.user)
async def follow(ctx, username: str):
    try:
        user = None
        if username.isdigit():
            user = bot.twitter.get_user(int(username))

        else:
            user = bot.twitter.get_user_by_username(username)

        user.follow()
        await ctx.send(f"{bot.twitter.user.username} Has followed {user.username}!")

    except Exception as error:
        if isinstance(error, pytweet.errors.NotFoundError):
            await ctx.send(f"Could not find user with username(or id): [{username}].")
        else:
            raise error

@bot.command(
    description="UnFollow a user, only an owner of the server can do this command"
)
@commands.is_owner()
@commands.cooldown(1, 10, commands.BucketType.user)
async def unfollow(ctx, username: str):
    try:
        user = None
        if username.isdigit():
            user = bot.twitter.get_user(int(username))

        else:
            user = bot.twitter.get_user_by_username(username)

        user.unfollow()
        await ctx.send(f"{bot.twitter.user.username} Has unfollowed {user.username}!")

    except Exception as error:
        if isinstance(error, pytweet.errors.NotFoundError):
            await ctx.send(f"Could not find user with username(or id): [{username}].")
            
        else:
            raise error

@bot.command(
    description="Return users that i followed"
)
@commands.is_owner()
@commands.cooldown(1, 10, commands.BucketType.user)
async def following(ctx):
    users=bot.twitter.user.following
    txt=""
    for num, user in enumerate(users):
        txt += f"{num + 1}. {user.username}({user.id})\n"
    
    await ctx.send(f"Here are **{len(users)}** cool people i followed!\n{txt}")

token = os.environ["token"]
bot.run(token)
