# 🔬 Automatic arXiv Scientific Article Analysis System

Intelligent system for finding intersections between scientific fields and discovering interdisciplinary research on arXiv.

## 🎯 Description

The system analyzes scientific publications on arXiv and finds articles where one scientific topic is applied in the context of another field. For example, how machine learning is used in medicine, or how quantum computing is applied in cryptography.

## 🏗️ Architecture

The system is built on a microservice architecture:

### 📱 TelegramBot (User Interface)
- Provides interaction through Telegram API
- Accepts commands and sends notifications
- Works independently of AI agent state

### 🤖 AI Agent (Analytical Module)
- Performs intelligent analysis of publications
- Works autonomously in background mode
- Supports hot-reload configuration

**Advantages:** Each service can be deployed, updated, or restarted independently.

## 🔄 Workflow

### 1. Setting Analysis Topics
```
/topic "target topic" "search area"
```

**Two-level search system:**
- **Target topic** — what we want to find
- **Search area** — scientific field for search

**Examples:**
- `/topic "machine learning" "medicine"`
- `/topic "quantum computing" "cryptography"`
- `/topic "blockchain" "logistics"`

### 2. Automatic Analysis

**Stage 1: Search Area Filtering**
- Search for articles in the specified scientific field
- Analysis of metadata and abstracts
- Primary filtering by relevance

**Stage 2: Target Topic Search**
- Deep analysis for target topic content
- Multi-level intelligent analysis:
  - Contextual filtering
  - Semantic intersection analysis
  - Deep contextual analysis

### 3. Structured Reports

When a relevant article is found, the system generates a report:

```
🔬 Found topic intersection: "machine learning" in area "medicine"

📄 Title: Deep Learning for Medical Image Analysis
👥 Authors: John Smith, Jane Doe
📅 Publication date: 15.01.2024
📚 arXiv category: cs.CV
🔗 Link: https://arxiv.org/abs/2401.12345

📊 Topic intersection analysis:
• Search area relevance: 95.0%
• Target topic content: 88.0%
• Overall score: 90.6%

📋 Brief summary:
The article demonstrates the application of deep learning for medical image analysis,
showing significant improvements in diagnosis compared to traditional methods.
```

## 📋 Commands

### Basic Commands
- `/start` — Help and command list
- `/topic "topic1" "topic2"` — Set topics for analysis
- `/status` — Current monitoring status
- `/history` — Recent found intersections

### Monitoring Management
- `/pause` — Pause analysis
- `/resume` — Resume work
- `/switch_themes` — Swap topics

### Settings
- `/settings` — View filtering settings

## ⚙️ Filtering Settings

- **Relevance thresholds** for each topic separately
- **Notifications:**
  - Instant (≥80% relevance)
  - Daily digest (≥50% relevance)
  - Weekly digest (≥30% relevance)
- **Time filters** (search depth in days)

## 🚀 Installation and Setup

### Requirements
- Python 3.13+
- OpenAI API key or local LLM (Ollama)

### Installing Dependencies
```bash
# Install uv (recommended)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync
```

### Environment Variables Setup
Create a `.env` file:
```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
OPENAI_API_KEY=your_openai_api_key
DATABASE_PATH=database.db
```

### Running the System
```bash
# Run all services
python main.py

# Or run individual components
python start_bot.py     # Telegram bot only
python start_agent.py   # AI Agent only
```

## 📊 System Capabilities

- ✅ Automatic arXiv monitoring
- ✅ Two-stage relevance analysis
- ✅ Intelligent reports with scores
- ✅ Flexible filtering settings
- ✅ Multi-level notifications
- ✅ History of found intersections
- ✅ Independent microservices

## 🛠️ Technologies

- **Backend:** Python, asyncio, Peewee ORM
- **Telegram Bot:** aiogram 3.x
- **AI/LLM:** OpenAI GPT / Ollama
- **Database:** SQLite
- **arXiv API:** arxiv-py
- **PDF parsing:** PyPDF2

## 📝 Usage Examples

1. **Finding AI applications in medicine:**
   ```
   /topic "artificial intelligence" "medicine"
   ```

2. **Blockchain in finance:**
   ```
   /topic "blockchain" "finance"
   ```

3. **Quantum computing in cryptography:**
   ```
   /topic "quantum computing" "cryptography"
   ```

## 📈 Statistics and Analytics

The system tracks statistics on:
- Number of analyzed articles
- Found relevant intersections
- Trends in interdisciplinary research
- Maps of relationships between scientific fields

---

**Created for researchers who want to stay informed about interdisciplinary breakthroughs in science.**
