<div align="center">

# 🔬 Searcher Agent

<p align="center">
  <strong>AI-powered system for discovering interdisciplinary research on arXiv</strong>
</p>

<p align="center">
 
<img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white" alt="Python Version">
<img src="https://img.shields.io/badge/License-MIT-4CAF50?logo=open-source-initiative&logoColor=white" alt="License">
<img src="https://img.shields.io/badge/AI-OpenAI%20GPT-10A37F?logo=openai&logoColor=white" alt="AI Model">
<img src="https://img.shields.io/badge/Bot-Telegram-229ED9?logo=telegram&logoColor=white" alt="Telegram Bot">
<img src="https://img.shields.io/badge/Database-SQLite-07405E?logo=sqlite&logoColor=white" alt="Database">
</p>

<p align="center">
  <a href="#what-it-does">What It Does</a> •
  <a href="#quick-setup">Quick Setup</a> •
  <a href="#how-to-use">How to Use</a> •
  <a href="#example-output">Example Output</a>
</p>

</div>

---

## What It Does

**Finds scientific intersections automatically** - discovers where one research field is applied in another domain.

<table>
<tr>
<td>

**Machine Learning** → **Medicine**
</td>
<td>

**Quantum Computing** → **Cryptography**
</td>
<td>

**Blockchain** → **Logistics**
</td>
</tr>
</table>

The system continuously monitors arXiv papers and uses AI to identify meaningful cross-disciplinary research opportunities.

---

## Quick Setup

<details>
<summary><strong>Prerequisites</strong></summary>

- Python 3.10+
- Telegram Bot Token ([create one](https://t.me/BotFather))
- OpenAI API Key or local LLM setup

</details>

### 1️⃣ Install Dependencies

```bash
# Install uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install project dependencies
uv sync
```

### 2️⃣ Configure Environment

Create `.env` file from `.env.example`:

```bash
cp .env.example .env
```

or manually:

```ini
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
OPENAI_API_KEY=your-openai-api-key
OPENROUTER_API_KEY=your-openrouter-key
DATABASE_PATH=database.db
```

### 3️⃣ Configure LLM

Choose your model in [`shared/llm.py`](shared/llm.py) by changing [`AGENT_MODEL`](shared/llm.py#L39) variable. You will need to have an API key for the model you choose (except for ollama local models). You can also add your own models like this:

```python
_my_model_provider = AsyncOpenAI(
    base_url="https://api.my-model-provider.com/v1",
    api_key=os.getenv("MY_MODEL_API_KEY")
)

MyModel = OpenAIChatCompletionsModel(
    model="my-model",
    openai_client=_my_model_provider
)
```

See [`shared/llm.py`](shared/llm.py) for more examples.

### 4️⃣ Launch System

```bash
# 🚀 Start everything
python main.py

# Or run components separately:
python start_bot.py    # 🤖 Bot only
python start_agent.py  # 🧠 Agent only
```

---

## How to Use

### Set Your Research Topics

```
/topic "machine learning" "medicine"
```

### Bot Commands

<table>
<tr>
<th>Command</th>
<th>Description</th>
<th>Example</th>
</tr>
<tr>
<td><code>/start</code></td>
<td>Help & commands</td>
<td>-</td>
</tr>
<tr>
<td><code>/topic</code></td>
<td>Set analysis topics</td>
<td><code>/topic "AI" "healthcare"</code></td>
</tr>
<tr>
<td><code>/status</code></td>
<td>Current status</td>
<td>-</td>
</tr>
<tr>
<td><code>/pause</code>, <code>/resume</code></td>
<td>Control monitoring</td>
<td>-</td>
</tr>
<tr>
<td><code>/history</code></td>
<td>Recent findings</td>
<td>-</td>
</tr>
</table>

---

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
Machine learning is increasingly applied in medicine for diagnostic imaging,
predictive analytics, and treatment optimization. The approach demonstrates high
innovativeness through deep learning algorithms that can match or exceed human
performance in specific medical tasks.
```

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  <strong>🌟 Star this repo if you find it useful!</strong>
  <br>
  <br>
  <a href="#-searcher-agent" style="font-size: 1.2em; color: white;">⬆️ Back to top</a>
</p>