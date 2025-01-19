import discord
import requests
import os
import asyncio
from dotenv import load_dotenv
import re
from datetime import datetime

# Load environment variables from .env file
load_dotenv()

tracker_messages = {}

# Environment variables
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GITHUB_API_TOKEN = os.getenv("GITHUB_API_TOKEN")  # Optional for GitHub authentication
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))  # Discord channel to send updates

APPLICATION_STATUSES = {
    "📝": "Applied",
    "📞": "Phone Screen",
    "💻": "Technical Interview",
    "👥": "On-site/Final Round",
    "✅": "Offer Received",
    "❌": "Rejected",
    "⏳": "Waiting"
}

REPOSITORIES = [
    "SimplifyJobs/Summer2025-Internships",
]

CHECK_INTERVAL = 60

JOB_TYPES = {
    "💻": "SWE",
    "💵": "Finance"
}

user_preferences = {}
previous_shas = {repo: None for repo in REPOSITORIES}
user_applied_internships = {}
last_listed_internships = {}
user_tracked_internships = {}  # New dictionary to store tracked internships with status

intents = discord.Intents.default()
intents.reactions = True
intents.messages = True
intents.message_content = True 
client = discord.Client(intents=intents)

# Add new function to validate GitHub URL
def validate_github_url(url):
    pattern = r"https?://github\.com/[\w-]+/[\w-]+"
    return bool(re.match(pattern, url))

# Add new function to extract repo path from URL
def extract_repo_path(url):
    match = re.search(r"github\.com/([\w-]+/[\w-]+)", url)
    return match.group(1) if match else None

# Add new function to update tracking status
async def update_tracking_status(user_id, internship_index, new_status):
    if user_id not in user_tracked_internships:
        return False
    
    if 0 <= internship_index < len(user_tracked_internships[user_id]):
        user_tracked_internships[user_id][internship_index]['status'] = new_status
        return True
    return False



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
            last_listed_internships[sent_message.id] = internships
            
            for idx in range(min(len(internships), len(number_emojis))):
                await sent_message.add_reaction(number_emojis[idx])
        except Exception as e:
            print(f"Error fetching Lists: {e}")
            await message.channel.send("❌ An error occurred while fetching the internships.")

    elif message.content.startswith("!switch"):
        parts = message.content.split(maxsplit=1)
        if len(parts) != 2:
            await message.channel.send("❌ Please provide a GitHub repository URL: `!switch [GitHub URL]`")
            return
        
        repo_url = parts[1].strip()
        if not validate_github_url(repo_url):
            await message.channel.send("❌ Invalid GitHub URL format. Please provide a valid GitHub repository URL.")
            return
        
        repo_path = extract_repo_path(repo_url)
        if repo_path in REPOSITORIES:
            await message.channel.send(f"⚠️ Repository {repo_path} is already being tracked!")
            return
        
        REPOSITORIES.append(repo_path)
        previous_shas[repo_path] = None
        await message.channel.send(f"✅ Successfully added repository: {repo_path}")

    elif message.content.startswith("!tracker"):
        user_id = str(message.author.id)
    
        if user_id not in user_applied_internships or not user_applied_internships[user_id]:
            await message.channel.send("🗒️ You haven't added any internships to track yet. Use `!list` to find internships!")
            return

        # Initialize tracking if not exists
        if user_id not in user_tracked_internships:
            user_tracked_internships[user_id] = [
                {**internship, 'status': 'Applied'} 
                for internship in user_applied_internships[user_id]
            ]

        embed = discord.Embed(
            title="📊 Your Internship Application Tracker",
            description="React with emojis to update status:\n" + \
                "\n".join([f"{emoji} - {status}" for emoji, status in APPLICATION_STATUSES.items()]),
            color=discord.Color.blue()
        )

        for idx, internship in enumerate(user_tracked_internships[user_id]):
            status_emoji = next(
                (emoji for emoji, status in APPLICATION_STATUSES.items() 
                if status == internship['status']),
                "📝"
            )
            embed.add_field(
                name=f"{idx + 1}. {internship['company']} {status_emoji}",
                value=(
                    f"**Role**: {internship['role']}\n"
                    f"**Status**: {internship['status']}\n"
                    f"**Location**: {internship['location']}"
                ),
                inline=False
            )

        tracker_message = await message.channel.send(embed=embed)
        
        # Store the tracker message ID and associated user ID
        tracker_messages[tracker_message.id] = {
            'user_id': user_id,
            'internships': user_tracked_internships[user_id]
        }
        
        # Add status reactions
        for emoji in APPLICATION_STATUSES.keys():
            await tracker_message.add_reaction(emoji)

    elif message.content.startswith("!stats"):
        user_id = str(message.author.id)
        if user_id not in user_tracked_internships or not user_tracked_internships[user_id]:
            await message.channel.send("No tracking data available yet!")
            return

        # Calculate statistics
        status_counts = {}
        for internship in user_tracked_internships[user_id]:
            status = internship['status']
            status_counts[status] = status_counts.get(status, 0) + 1

        embed = discord.Embed(
            title="📊 Your Application Statistics",
            color=discord.Color.green()
        )

        total_apps = len(user_tracked_internships[user_id])
        embed.add_field(
            name="Total Applications",
            value=str(total_apps),
            inline=False
        )

        for status, count in status_counts.items():
            percentage = (count / total_apps) * 100
            embed.add_field(
                name=status,
                value=f"{count} ({percentage:.1f}%)",
                inline=True
            )

        await message.channel.send(embed=embed)

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
            name="📋 `!plist`",
            value="Show all internships you have applied to.",
            inline=False
        )
        embed.add_field(
            name="📊 `!tracker`",
            value="Track the status of your internship applications.",
            inline=False
        )
        embed.add_field(
            name="🔄 `!switch [GitHub URL]`",
            value="Add a new GitHub repository to track.",
            inline=False
        )
        embed.add_field(
            name="📈 `!stats`",
            value="View statistics about your internship applications.",
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
            # Get status from tracked internships if available
            status = "Applied"  # Default status
            if user_id in user_tracked_internships:
                tracked_internship = next(
                    (item for item in user_tracked_internships[user_id] 
                    if item['company'] == internship['company'] and 
                        item['role'] == internship['role']),
                    None
                )
                if tracked_internship:
                    status = tracked_internship['status']
            
            # Get status emoji
            status_emoji = next(
                (emoji for emoji, stat in APPLICATION_STATUSES.items() 
                if stat == status),
                "📝"
            )
            
            embed.add_field(
                name=f"{idx}. {internship['company']} {status_emoji}",
                value=(
                    f"**Role**: {internship['role']}\n"
                    f"**Status**: {status}\n"
                    f"**Location**: {internship['location']}\n"
                    f"{'**[Apply Here]({})**'.format(internship['apply_link']) if internship.get('apply_link') else ''}"
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
    
    # Handle tracker reactions
    if message_id in tracker_messages:
        if emoji in APPLICATION_STATUSES:
            tracker_data = tracker_messages[message_id]
            user_id = tracker_data['user_id']
            
            # Only allow the user who created the tracker to update it
            if str(user.id) != user_id:
                return
                
            embed = reaction.message.embeds[0]
            
            try:
                # Find the internship that was reacted to
                for field in embed.fields:
                    field_number = field.name.split('.')[0]
                    if field_number.isdigit():
                        idx = int(field_number) - 1
                        internship = user_tracked_internships[user_id][idx]
                        new_status = APPLICATION_STATUSES[emoji]
                        
                        # Update status in tracked internships
                        user_tracked_internships[user_id][idx]['status'] = new_status
                        
                        # Update status in applied internships
                        if user_id in user_applied_internships:
                            matching_internship = next(
                                (item for item in user_applied_internships[user_id]
                                 if item['company'] == internship['company'] and
                                    item['role'] == internship['role']),
                                None
                            )
                            if matching_internship:
                                matching_internship['status'] = new_status
                        
                        # Update the embed field
                        embed.set_field_at(
                            idx,
                            name=f"{field_number}. {internship['company']} {emoji}",
                            value=(
                                f"**Role**: {internship['role']}\n"
                                f"**Status**: {new_status}\n"
                                f"**Location**: {internship['location']}"
                            ),
                            inline=False
                        )
                
                await reaction.message.edit(embed=embed)
                await user.send(f"✅ Updated status for {internship['company']} to {new_status}")
                
            except Exception as e:
                print(f"Error updating tracker: {e}")
                await user.send("❌ An error occurred while updating the tracker.")
        return

    # Handle existing reactions (keep the rest of the reaction handling code)
    if message_id in last_listed_internships:
        internships = last_listed_internships[message_id]
        emoji_to_index = {
            "1️⃣": 0, "2️⃣": 1, "3️⃣": 2, "4️⃣": 3, "5️⃣": 4,
            "6️⃣": 5, "7️⃣": 6, "8️⃣": 7, "9️⃣": 8, "🔟": 9
        }
        
        if emoji in emoji_to_index:
            idx = emoji_to_index[emoji]
            if 0 <= idx < len(internships):
                internship = internships[idx]
                user_id = str(user.id)
                
                if user_id not in user_applied_internships:
                    user_applied_internships[user_id] = []
                
                existing_internship = next(
                    (item for item in user_applied_internships[user_id] 
                     if item['company'] == internship['company'] and 
                        item['role'] == internship['role']),
                    None
                )
                
                if not existing_internship:
                    internship_copy = internship.copy()
                    internship_copy['status'] = 'Applied'  # Add initial status
                    user_applied_internships[user_id].append(internship_copy)
                    await user.send(f"✅ Added **{internship['company']}** to your applied internships list!")
                else:
                    await user.send(f"⚠️ **{internship['company']}** is already in your list!")@client.event
async def on_reaction_remove(reaction, user):
    if user.bot:
        return

    emoji = str(reaction.emoji)
    if emoji in JOB_TYPES and user.id in user_preferences:
        del user_preferences[user.id]
        await user.send("Preference cleared. You will no longer receive updates.")

client.run(DISCORD_TOKEN)
