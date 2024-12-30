import discord
import requests
import os
import asyncio
from dotenv import load_dotenv
import re
from datetime import datetime

# Load environment variables from .env file
load_dotenv()

# Environment variables
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GITHUB_API_TOKEN = os.getenv("GITHUB_API_TOKEN")  # Optional for GitHub authentication
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))  # Discord channel to send updates

REPOSITORIES = [
    "SimplifyJobs/Summer2025-Internships",
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
intents.message_content = True 
client = discord.Client(intents=intents)



async def fetch_internships(date_str=None):
    """
    Fetch internships from the README.md file
    If date_str is provided, filter for internships posted on that date
    """
    headers = {}
    if GITHUB_API_TOKEN:
        headers["Authorization"] = f"token {GITHUB_API_TOKEN}"
    
    internships = []
    for repo in REPOSITORIES:
        url = f"https://api.github.com/repos/{repo}/contents/README.md"
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                file_data = response.json()
                content = requests.get(file_data['download_url']).text
                
                # Parse the table content
                lines = content.split('\n')
                for line in lines:
                    if line.startswith('|') and '|' in line[1:]:
                        # Skip header and separator lines
                        if '---' in line or 'Company' in line:
                            continue
                        
                        # Skip if position is closed (contains 🔒 emoji)
                        if '🔒' in line:
                            continue
                        
                        # Parse the line
                        parts = [part.strip() for part in line.split('|')]
                        if len(parts) >= 4:
                            # Extract company name from markdown link if present
                            company_cell = parts[1]
                            link_match = re.match(r'\[([^\]]+)\]', company_cell)
                            company = link_match.group(1) if link_match else company_cell.strip()
                            
                            role = parts[2].strip()
                            location = parts[3].strip()
                            
                            # Extract application link
                            apply_cell = parts[4] if len(parts) > 4 else ""
                            apply_link = None
                            # Look for href in the cell
                            href_match = re.search(r'href="([^"]+)"', apply_cell)
                            if href_match:
                                apply_link = href_match.group(1)
                            
                            # Find date in the parts
                            date_part = None
                            for part in parts:
                                if re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}', part):
                                    date_part = part.strip()
                                    break
                            
                            if date_str and date_part:
                                try:
                                    # Convert input date string to datetime
                                    filter_date = datetime.strptime(date_str, '%b %d')
                                    post_date = datetime.strptime(date_part, '%b %d')
                                    
                                    # Compare month and day only
                                    if post_date.month != filter_date.month or post_date.day != filter_date.day:
                                        continue
                                    
                                except ValueError:
                                    continue
                            
                            internships.append({
                                'company': company,
                                'role': role,
                                'location': location,
                                'apply_link': apply_link,
                                'date': date_part
                            })
                
        except Exception as e:
            print(f"Error fetching internships: {e}")
    
    return internships



async def check_repositories(manual_trigger=False):
    print("check_repositories triggered")  # Debug

    headers = {}
    if GITHUB_API_TOKEN:
        headers["Authorization"] = f"token {GITHUB_API_TOKEN}"

    results = []
    for repo in REPOSITORIES:
        print(f"Checking repo: {repo}")  # Debug
        url = f"https://api.github.com/repos/{repo}/contents/README.md"
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                print(f"Successfully fetched {repo}")  # Debug
                file_data = response.json()
                current_sha = file_data['sha']
                
                if manual_trigger or (previous_shas[repo] and current_sha != previous_shas[repo]):
                    file_content = requests.get(file_data['download_url']).text
                    for emoji, job_type in JOB_TYPES.items():
                        if job_type.lower() in file_content.lower():
                            results.append(f"New {job_type} update in {repo}!")
                            await notify_users(repo, job_type)
                
                previous_shas[repo] = current_sha
            else:
                print(f"Error fetching GitHub repo {repo}: {response.status_code}")  # Debug
        except Exception as e:
            print(f"Error checking repository: {e}")

    if manual_trigger:
        try:
            channel = client.get_channel(CHANNEL_ID)
            if channel is None:
                print("Error: CHANNEL_ID is incorrect or bot lacks permissions.")
                return

            if results:
                await channel.send("\n".join(results))
            else:
                await channel.send("No new updates detected.")
            print("Manual check completed")  # Debug
        except Exception as e:
            print(f"Error sending results: {e}")

async def periodic_check():
    while True:
        await check_repositories()
        await asyncio.sleep(CHECK_INTERVAL)

async def notify_users(repo, job_type):
    channel = client.get_channel(CHANNEL_ID)
    for user_id, preference in user_preferences.items():
        if preference == job_type:
            try:
                user = await client.fetch_user(user_id)
                await user.send(f"🚀 New {job_type} update in {repo}!")
            except Exception as e:
                print(f"Error notifying user {user_id}: {e}")
    await channel.send(f"🚀 New {job_type} update detected in {repo}!")

@client.event
async def on_ready():
    print(f"We have logged in as {client.user}")
    client.loop.create_task(periodic_check())

user_applied_internships = {}
last_listed_internships = {}

print("Initial user_applied_internships:", user_applied_internships)
print("Initial last_listed_internships:", last_listed_internships)

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    print(f"Message received: {message.content}")  # Debug

    if message.content.startswith("!refresh"):
        print("!refresh command detected")  # Debug
        await message.channel.send("🔄 Refreshing repositories... Please wait.")
        await check_repositories(manual_trigger=True)
        print("Refresh completed")  # Debug

    elif message.content.startswith("!list"):
        parts = message.content.split(maxsplit=1)
        if len(parts) != 2:
            embed = discord.Embed(
                title="❌ Invalid Command",
                description="Please use the format: `!list MMM DD` (e.g., `!list Dec 26`)",
                color=discord.Color.red()
            )
            await message.channel.send(embed=embed)
            return

        date_str = parts[1].strip().title()
        try:
            datetime.strptime(date_str, '%b %d')
            await message.channel.send(f"🔍 Fetching internships posted on {date_str}...")
            internships = await fetch_internships(date_str)

            if not internships:
                embed = discord.Embed(
                    title="📅 No Internships Found",
                    description=f"No internships found for {date_str}.",
                    color=discord.Color.orange()
                )
                await message.channel.send(embed=embed)
                return

            embed = discord.Embed(
                title=f"📅 Internships Posted on {date_str}",
                color=discord.Color.blue()
            )
            
            # Add number emojis for reactions
            number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
            
            for idx, internship in enumerate(internships, 1):
                if idx > len(number_emojis):
                    break
                    
                embed.add_field(
                    name=f"{number_emojis[idx-1]} {internship['company']}",
                    value=(
                        f"**Role**: {internship['role']}\n"
                        f"**Location**: {internship['location']}\n"
                        f"{'**[Apply Here]({})**'.format(internship['apply_link']) if internship['apply_link'] else ''}"
                    ),
                    inline=False
                )

            sent_message = await message.channel.send(embed=embed)
            
            # Store the internships list for this message
            last_listed_internships[sent_message.id] = internships
            
            # Add number reactions
            for idx in range(min(len(internships), len(number_emojis))):
                await sent_message.add_reaction(number_emojis[idx])
        except Exception as e:
            print(f"Error fetching Lists: {e}")
    elif message.content.startswith("!setfilter"):
        await message.channel.send(
            "React with 💻 for SWE updates or 💵 for Finance updates!"
        )
        filter_message = await message.channel.send("Choose your preference!")
        for emoji in JOB_TYPES.keys():
            await filter_message.add_reaction(emoji)

    elif message.content.startswith("!help"):
        embed = discord.Embed(
            title="🤖 Bot Commands",
            description="Here are the available commands:",
            color=discord.Color.green()
        )
        embed.add_field(
            name="🔄 `!refresh`",
            value="Refresh the repository to check for changes.",
            inline=False
        )
        embed.add_field(
            name="📅 `!list [MMM DD]`",
            value="List all activity during the specified date from the repository (e.g., `!list Dec 26`).",
            inline=False
        )
        embed.add_field(
            name="⚙️ `!setfilter`",
            value="Set your preference for SWE or Finance updates by reacting to the bot's message.",
            inline=False
        )
        embed.add_field(
            name="📅 `!plist`",
            value="Show all internships user has applied to",
            inline=False
        )
        
        await message.channel.send(embed=embed)

    elif message.content.startswith("!plist"):
        user_id = str(message.author.id)
        print(f"!plist command received for user_id: {user_id}")  # Debug
        print(f"Current user_applied_internships: {user_applied_internships}")  # Debug
        
        if user_id not in user_applied_internships or not user_applied_internships[user_id]:
            print(f"No internships found for user {user_id}")  # Debug
            await message.channel.send("🗒️ You haven't added any internships yet. Use `!list` and react to start adding!")
            return

        embed = discord.Embed(
            title="📋 Your Applied Internships",
            color=discord.Color.green()
        )
        
        print(f"User's internships: {user_applied_internships[user_id]}")  # Debug
        
        for idx, internship in enumerate(user_applied_internships[user_id], 1):
            embed.add_field(
                name=f"{idx}. {internship['company']}",
                value=(
                    f"**Role**: {internship['role']}\n"
                    f"**Location**: {internship['location']}\n"
                    f"{'**[Apply Here]({})**'.format(internship['apply_link']) if internship['apply_link'] else ''}"
                ),
                inline=False
            )
        
        await message.channel.send(embed=embed)


@client.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return

    message_id = reaction.message.id
    emoji = str(reaction.emoji)
    
    print(f"\nReaction received - Message ID: {message_id}, Emoji: {emoji}")  # Debug
    print(f"Available message IDs in last_listed_internships: {list(last_listed_internships.keys())}")  # Debug

    if message_id not in last_listed_internships:
        print(f"Message ID {message_id} not found in last_listed_internships")  # Debug
        return

    internships = last_listed_internships[message_id]
    print(f"Found internships for message: {internships}")  # Debug
    
    emoji_to_index = {
        "1️⃣": 0, "2️⃣": 1, "3️⃣": 2, "4️⃣": 3, "5️⃣": 4,
        "6️⃣": 5, "7️⃣": 6, "8️⃣": 7, "9️⃣": 8, "🔟": 9
    }

    if emoji in emoji_to_index:
        idx = emoji_to_index[emoji]
        print(f"Emoji mapped to index: {idx}")  # Debug
        
        if 0 <= idx < len(internships):
            internship = internships[idx]
            user_id = str(user.id)
            
            print(f"Processing internship {internship['company']} for user {user_id}")  # Debug
            print(f"Current user_applied_internships before adding: {user_applied_internships}")  # Debug

            # Initialize user's list if it doesn't exist
            if user_id not in user_applied_internships:
                user_applied_internships[user_id] = []
                print(f"Initialized new list for user {user_id}")  # Debug

            # Check if internship is already in the list
            existing_internship = next(
                (item for item in user_applied_internships[user_id] 
                 if item['company'] == internship['company'] and 
                    item['role'] == internship['role']),
                None
            )

            if not existing_internship:
                user_applied_internships[user_id].append(internship.copy())  # Make a copy of the internship
                print(f"Added internship to user's list. Updated data: {user_applied_internships[user_id]}")  # Debug
                await user.send(f"✅ Added **{internship['company']}** to your applied internships list!")
            else:
                print(f"Internship already exists in user's list")  # Debug
                await user.send(f"⚠️ **{internship['company']}** is already in your list!")
            
            print(f"Final user_applied_internships: {user_applied_internships}")  # Debug
@client.event
async def on_reaction_remove(reaction, user):
    if user.bot:
        return

    emoji = str(reaction.emoji)
    if emoji in JOB_TYPES and user.id in user_preferences:
        del user_preferences[user.id]
        await user.send("Preference cleared. You will no longer receive updates.")

client.run(DISCORD_TOKEN)