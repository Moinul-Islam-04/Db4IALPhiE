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
        parts = message.content.split(maxsplit=1)  # Allow splitting into exactly two parts
        if len(parts) != 2:
            await message.channel.send("Please use the format: !list MMM DD (e.g., !list Dec 26)")
            return
        
        date_str = parts[1].strip().title()  # Normalize input to proper case
        try:
            # Try to parse the date in MMM DD format
            datetime.strptime(date_str, '%b %d')
            
            await message.channel.send(f"🔍 Fetching internships posted on {date_str}...")
            internships = await fetch_internships(date_str)
            
            if not internships:
                print(f"No internships found for {date_str}")  # Debugging
                await message.channel.send(f"No internships found for {date_str}")
                return
            
            # Create a formatted message with the internships
            response = f"📅 **Internships posted on {date_str}:**\n\n"
            for idx, internship in enumerate(internships, 1):
                response += f"{idx}. **{internship['company']}**\n"
                response += f"   💼 {internship['role']}\n"
                response += f"   📍 {internship['location']}\n"
                if internship['apply_link']:
                    response += f"   🔗 [Apply Here]({internship['apply_link']})\n"
                response += "\n"
            
            # Trim response if too long
            if len(response) > 1900:
                response = response[:1900] + "\n... (more results available but truncated for message limit)"
            
            await message.channel.send(response)
        
        except ValueError:
            await message.channel.send("Invalid date format. Please use MMM DD format (e.g., Dec 26)")


    elif message.content.startswith("!setfilter"):
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