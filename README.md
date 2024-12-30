# Internship Tracker Bot

A Discord bot designed to help users track internship opportunities from repositories like [SimplifyJobs/Summer2025-Internships](https://github.com/SimplifyJobs/Summer2025-Internships). The bot allows users to search for internships posted on specific dates and aims to help users manage a personal list of internships they've applied to or are interested in.

## Features

### 1. **List Internships by Date**
- Use the command `!list MMM DD` (e.g., `!list Dec 26`) to display internships posted on a particular date.
- The bot will provide detailed information about each internship, including:
  - **Company Name**
  - **Role**
  - **Location**
  - **Application Link (if available)**

### 2. **Personal Internship List (In Development)**
- Soon, users will be able to add internships to their personal list by reacting with number emojis (e.g., `1️⃣`, `2️⃣`) to the internship list.
- Use the command `!plist` to view your saved internships.
- This feature is currently under development and will allow users to manage their internship applications effectively.

## How to Use

### Commands

1. **`!list [MMM DD]`**
   - Displays a list of internships posted on the specified date.
   - Example:
     ```
     !list Dec 26
     ```

2. **`!plist`** *(In Development)*
   - Shows a personal list of internships that the user has added.

3. **`!help`**
   - Displays a list of available commands and their descriptions.

### Adding Internships to Personal List (Coming Soon)
- React to the list message with a number emoji (e.g., `1️⃣`, `2️⃣`) to add an internship to your personal list.

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd <repository-folder>
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up your `.env` file with the following variables:
   ```
   DISCORD_TOKEN=your_discord_bot_token
   GITHUB_API_TOKEN=your_github_api_token
   CHANNEL_ID=your_discord_channel_id
   ```

4. Run the bot:
   ```bash
   python Intern.py
   ```

## Development Status

- **Implemented:**
  - Listing internships for a specific date.
  - Displaying information in a clean, embedded format.

- **In Progress:**
  - Personal internship list feature (adding internships via emoji reactions and viewing them with `!plist`).

## Contributions
Contributions are welcome! Feel free to open issues or submit pull requests for improvements or new features.

## License
This project is open-source and available under the [MIT License](LICENSE).

---

### Notes
- Make sure to invite the bot to your server with the appropriate permissions.
- Stay tuned for updates as more features are added!

