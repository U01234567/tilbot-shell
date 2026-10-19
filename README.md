# tilbot-shell

A framework for research chatbots that get to know a participant, give feedback, and then answer their questions. It wraps Tilbot for the conversation and vector-similarity-intent for understanding free text, and adds what a study needs around them: participant accounts, encrypted storage, rules, a knowledge base and a dashboard. One study at a time, defined entirely in one project folder; the same framework serves patients, voters, students or any other group.

## Quick start

You need Docker, running, and Python 3.11+. Then:

```
git clone https://github.com/U01234567/tilbot-shell
cd tilbot-shell
python start_shell.py up       # first run: creates .env with fresh secrets, builds and starts everything
python start_shell.py trust    # once per computer: no certificate warnings
python start_shell.py researcher   # your name and password, for both dashboards
```

Open https://localhost. Back up `FIELD_ENCRYPTION_KEY` from `.env` right away. Then [set up your study, start to finish](docs/operations.md#your-study-start-to-finish). What you should see at each step, and what to do if you don't: [docs/operations.md](docs/operations.md).

## What every project has

The framework fixes the shape; the project folder fills it in.

| Always there | What it does | Where |
|---|---|---|
| **Tilbot** | the chatbot: the conversation is drawn as a flowchart in its editor, in the browser | built from a pinned commit with a few small patches, `tilbot/` |
| **vector-similarity-intent** | the interpreter: matches free text against the options the shell gives it | built from a pinned commit, `vector-similarity-intent/` |
| **shell** (Django) | accounts, participant data, rules, feedback, the knowledge base, the dashboard | `shell/` |
| **Participant database** | who signed up, their answers and transcripts, encrypted | Postgres |
| **Knowledge base** | question–answer pairs grouped by topic, with optional links | `project/knowledge.xlsx` |
| **Styling** | the study's name, language, texts and colours | `project/` |

And three phases, always in this order:

1. **Collect.** The bot asks the items of a questionnaire, written in Tilbot's editor. The shell stores each answer and, from thresholds in the project's settings, decides whether follow-up questions come next.
2. **Feedback.** The shell turns the answers into results beside the chat: a bar per scale, with its threshold and a sentence, scored as in the EORTC QLQ-C30 manual. The flowchart decides when they open.
3. **Questions.** The participant asks whatever they want. The shell finds the question in the knowledge base that means most nearly the same, and gives its answer word for word, with a clickable link where there is one.

Everything a study decides (its language and texts, age range, options, thresholds, results, knowledge base, theme, the Tilbot flowchart, and its ethics choices) lives in `project/`, a folder next to `start_shell.py` that is never committed (inside the containers it appears as `/project`). `project-example/` is the empty template and lists what a study has to decide.

## Read next

- [docs/architecture.md](docs/architecture.md): every folder, the contract between shell and Tilbot, how to build the questionnaire in Tilbot, the Caddyfile explained.
- [docs/decisions.md](docs/decisions.md): the big choices (Django, Postgres, Caddy, patches, …), why, and what we turned down; and the known gaps of this version.
- [docs/operations.md](docs/operations.md): setup on a new computer, your study start to finish, keys, backups, updates, and what to do when something is wrong.
- [ETHICS.md](ETHICS.md): what the software stores, where, and who can read it.

## Built with

Developed on Windows 11 with Python 3.14, Docker Desktop 29.8 (Docker Compose included) and Git.
macOS and Linux need no changes; type `python3` where this README says `python`.
Inside the containers: Python 3.12 (the shell), Node 26 (Tilbot), Postgres 17, MongoDB 8.3 and Caddy 2.10.
