# Searcher Agent

AI-powered system for finding interdisciplinary research on arXiv - discovers where one scientific topic is applied in another field.

## What It Does

Automatically analyzes arXiv papers to find intersections between scientific fields. For example:
- Machine learning applications in medicine
- Quantum computing in cryptography  
- Blockchain technology in logistics

## Quick Setup

### 1. Install Dependencies

```bash
# Install uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install project dependencies
uv sync
```

### 2. Configure Environment

Create `.env` file:

```ini
TELEGRAM_BOT_TOKEN=telegram-token-here
# if you have an API key for OpenAI:
# OPENAI_API_KEY=your-openai-key-here
# if you use other providers:
# OPENAI_API_KEY=
OPENAI_API_KEY=your-openai-key-here
OPENROUTER_API_KEY=openrouter-key-here
DATABASE_PATH=database.db
```

### 3. Run the System
```bash
# Start both bot and agent
python main.py

# Or run separately:
python start_bot.py    # Telegram bot only
python start_agent.py  # AI agent only
```

## How to Use

### Set Search Topics

```
/topic "machine learning" "medicine"
```

### Basic Commands

- `/start` - Help and command list
- `/topic "topic1" "topic2"` - Set analysis topics
- `/status` - Current monitoring status
- `/pause` / `/resume` - Control monitoring
- `/history` - View recent findings

## Architecture

- **`bot/`** - Telegram bot interface
- **`agent/`** - AI analysis engine  
- **`shared/`** - Common modules (database, LLM, arXiv)

## Example Output

```
🔬 Found topic intersection: "machine learning" in area "medicine"

📄 Title: AI and Medicine
👥 Authors: Mihai Nadin
📅 Publication date: 2019-12-05 21:58:18+00:00
📚 arXiv category: q-bio.OT

🔗 Link: http://arxiv.org/abs/2001.00641v1

📊 Topic intersection analysis:
• Target topic relevance: 95.0%

📋 Brief summary:
Machine learning is increasingly applied in medicine for diagnostic imaging, predictive analytics, and treatment optimization. The approach demonstrates high innovativeness through deep learning algorithms that can match or exceed human performance in specific medical tasks. Practical significance:
```

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.