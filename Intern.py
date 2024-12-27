import discord
import requests
import os
from time import sleep
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Environment variables
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GITHUB_API_TOKEN = os.getenv("GITHUB_API_TOKEN")  # Optional for GitHub authentication
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))  # Discord channel to send updates

REPOSITORIES = [
    "SimplifyJobs/Summer2025-Internships",
    "another/repo-name"
]
CHECK_INTERVAL = 60  # Check every 60 seconds

JOB_TYPES = {
    "💻": "SWE",
    "💵": "Finance"
}

user_preferences = {}
previous_shas = {repo: None for repo in REPOSITORIES}

intents = discord.Intents.default()
intents.reactions = True
intents.messages = True
client = discord.Client(intents=intents)

async def check_repositories():
    headers = {}
    if GITHUB_API_TOKEN:
        headers["Authorization"] = f"token {GITHUB_API_TOKEN}"
    
    while True:
        for repo in REPOSITORIES:
            url = f"https://api.github.com/repos/{repo}/contents/README.md"
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                file_data = response.json()
                current_sha = file_data['sha']
                if previous_shas[repo] and current_sha != previous_shas[repo]:
                    file_content = requests.get(file_data['download_url']).text
                    for emoji, job_type in JOB_TYPES.items():
                        if job_type.lower() in file_content.lower():
                            await notify_users(repo, job_type)
                previous_shas[repo] = current_sha
            else:
                print(f"Error fetching GitHub repo {repo}: {response.status_code}")
        sleep(CHECK_INTERVAL)

async def notify_users(repo, job_type):
    channel = client.get_channel(CHANNEL_ID)
    for user_id, preference in user_preferences.items():
        if preference == job_type:
            user = await client.fetch_user(user_id)
            await user.send(f"🚀 New {job_type} update in {repo}!")
    await channel.send(f"🚀 New {job_type} update detected in {repo}!")

@client.event
async def on_ready():
    print(f"We have logged in as {client.user}")
    client.loop.create_task(check_repositories())

@client.event
async def on_message(message):
    if message.content.startswith("!setfilter"):
        await message.channel.send(
            "React with 💻 for SWE updates or 💵 for Finance updates!"
        )
        filter_message = await message.channel.send("Choose your preference!")
        for emoji in JOB_TYPES.keys():
            await filter_message.add_reaction(emoji)

@client.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return

    emoji = str(reaction.emoji)
    if emoji in JOB_TYPES:
        job_type = JOB_TYPES[emoji]
        user_preferences[user.id] = job_type
        await user.send(f"Preference set to {job_type} updates!")

@client.event
async def on_reaction_remove(reaction, user):
    if user.bot:
        return

    emoji = str(reaction.emoji)
    if emoji in JOB_TYPES and user.id in user_preferences:
        del user_preferences[user.id]
        await user.send("Preference cleared. You will no longer receive updates.")

client.run(DISCORD_TOKEN)
