# Memento 0.1 Demo

This demo runs the first complete source-to-record interaction through the
line-oriented Agent adapter.

## 1. Configure providers

Create a `.env` file in the project root, or export these variables in your
shell:

```text
OPENAI_API_KEY=...
OPENAI_MODEL=...
OPENAI_BASE_URL=...
MINERU_API_KEY=...
```

`OPENAI_BASE_URL` is optional when using the default OpenAI endpoint. The CLI
loads `.env` automatically when `memento chat` starts.

## 2. Initialize a workspace

```bash
uv run memento init ./demo-workspace
```

Copy a document into the inbox:

```bash
cp /path/to/certificate.pdf ./demo-workspace/inbox/
```

## 3. Start the Agent

```bash
uv run memento chat --workspace ./demo-workspace
```

Ask the Agent to process the document:

```text
You: Process the certificate in my inbox.
```

The Agent chooses the semantic tools needed to list the inbox, import and
parse the source, and extract an achievement. `prepare_source` moves the file
from `inbox/` into content-addressed `sources/` storage.

The Agent should present the extracted facts and any description suggestion,
then ask for confirmation. Review or correct the complete entry in natural
language:

```text
You: The organization is correct. Change the title to National Mathematics
Contest and save it.
```

Only after explicit confirmation does the Agent call `save_achievement`. The
record is written to:

```text
demo-workspace/records/achievement/<record-id>.toml
```

Exit the conversation with `exit`, `quit`, EOF, or Ctrl-C.

## 4. Validate the record

```bash
uv run memento check demo-workspace/records/achievement/<record-id>.toml
```

The command validates the typed record and its source-level evidence without
starting an Agent conversation.
