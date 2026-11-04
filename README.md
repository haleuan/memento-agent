# Memento

Memento turns personal documents such as certificates into structured, source-linked memories. Its conversational agent helps you inspect and organize achievements, while you decide what gets saved.

```text
Add a document to inbox → Agent parses and summarizes it → You review and confirm → Memento saves a source-linked record
```

## Quickstart

Memento requires Python 3.11+, [`uv`](https://docs.astral.sh/uv/), an OpenAI API key, and a [MinerU](https://mineru.net/) API key for document parsing.

```bash
git clone <repository-url>
cd memento-agent
uv sync
```

Create a `.env` file in the project directory:

```dotenv
OPENAI_API_KEY=your-openai-api-key
OPENAI_MODEL=your-tool-capable-model
MINERU_API_KEY=your-mineru-api-key
```

Initialize a workspace and add a document to its inbox:

```bash
uv run memento init ./memento-workspace
cp /path/to/certificate.pdf ./memento-workspace/inbox/
uv run memento chat --workspace ./memento-workspace
```

In the chat, ask Memento to process the document. Review the extracted facts and suggested description, then explicitly confirm before asking it to save. Type `exit` or press Ctrl-D to leave.

The workspace keeps imported source files under `sources/`, parse snapshots under `.memento/parses/`, and confirmed achievement records under `records/`. The source reference is attached to the saved record so you can trace it back to the document.

## How it works

The model decides which available tools to call and in what order. Deterministic code handles source import, parser integration, record validation, and persistence. Memento asks for your confirmation before saving an achievement, and does not treat a suggested description as a document fact until you accept it.

## Current limitations

- The interactive interface is a line-oriented CLI; there is no TUI.
- Conversation history exists only for the lifetime of the running process.
- The current agent workflow focuses on achievement documents and records.
- MinerU is the configured document parser; other parser integrations are not exposed through the CLI.
- There is no timeline view or persistent session recovery yet.
