# tilbot-shell

A framework for research chatbots that get to know a participant, give feedback, and then answer their questions. It wraps Tilbot for the conversation and vector-similarity-intent for understanding free text, and adds what a study needs around them: participant accounts, encrypted storage, rules, a knowledge base and a dashboard. One study at a time, defined entirely in one project folder; the same framework serves patients, voters, students or any other group.

## What every project has

The framework fixes the shape; the project folder fills it in.

| Always there | What it does | Where |
|---|---|---|
| **Tilbot** | the chatbot: the conversation is drawn as a flowchart in its studio | built from a pinned commit with two small patches, `tilbot/` |
| **vector-similarity-intent** | the interpreter: matches free text against the options the shell gives it | built from a pinned commit, `vector-similarity-intent/` |
| **shell** (Django) | accounts, participant data, rules, feedback, the knowledge base, the dashboard | `shell/` |
| **Participant database** | who signed up, their answers and transcripts, encrypted | Postgres |
| **Knowledge base** | question–answer pairs grouped by topic, with optional links | `/project/knowledge.xlsx` |
| **Styling** | the study's name, language, texts and colours | `/project/` |

And three phases, always in this order:

1. **Collect.** The bot asks the items of a questionnaire, written in Tilbot's studio. The shell stores each answer and, from thresholds in the project's settings, decides whether follow-up questions come next.
2. **Feedback.** The shell turns the answers into feedback: sentences, a narrative with placeholders, charts.
3. **Questions.** The participant asks whatever they want. The shell matches the question to the knowledge base (topic first, then question) and answers, using the participant's own data where the answer calls for it.

Everything a study decides (its language and texts, age range, options, thresholds, feedback templates, knowledge base, theme, the Tilbot flowchart, and its ethics choices) lives in `/project/`, which is never committed. `project-example/` is the empty template and lists what a study has to decide.

## Start

You need Docker and Python 3.11+. The full first-time setup is in [docs/operations.md](docs/operations.md); in short:

```
cp .env.example .env              # then: python start_shell.py secrets, paste the values
python start_shell.py lock        # once: pins the Python packages
python start_shell.py up          # builds and starts everything; creates /project/ from project-example/
python start_shell.py exec shell pytest
```

Then open https://localhost.

## Read next

- [docs/architecture.md](docs/architecture.md): every folder, the contract between shell and Tilbot, how to build the questionnaire in Tilbot, the Caddyfile explained.
- [docs/decisions.md](docs/decisions.md): the big choices (Django, Postgres, Caddy, patches, …), why, and what we turned down; and the known gaps of this version.
- [docs/operations.md](docs/operations.md): setup, putting a Tilbot project online, keys, backups, updates.
- [ETHICS.md](ETHICS.md): what the software stores, where, and who can read it.

## Built with

Developed on Windows 11 with Python 3.14, Docker Desktop 29.8 (Docker Compose included) and Git.
macOS and Linux need no changes; type `python3` where this README says `python`.
Inside the containers: Python 3.12 (the shell), Node 26 (Tilbot), Postgres 17, MongoDB 8.3 and Caddy 2.10.
