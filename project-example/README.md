# The project folder

Everything about one study lives here. `start_shell.py up` copies `project-example/` to `project/`
on the first start; after that `project/` is yours and is never committed. Back it up by copying the folder; the flowchart itself is exported from Tilbot's dashboard (docs/operations.md).
Participant data is never in this folder: it stays in the database.

| File | What it holds | Change it when… |
|---|---|---|
| `project.toml` | the study name, sign-up limits and options, the Tilbot project id | the research team changes a setting |
| `questionnaire.toml` | per item: the answer scale and the threshold for follow-ups | the questionnaire changes |
| `theme/tokens.css` | the study's colours | the look should change |
| `tilbot/<name>.tilbot` | the flowchart, exported from Tilbot's dashboard as a backup (make the folder when you need it) | the conversation changes |
| `knowledge.xlsx` | question–answer pairs with topics, example phrasings and optional links (phase 3, not built yet) | the knowledge base changes |
| `feedback/` | feedback templates per score band (phase 2, not built yet) | the feedback changes |
| this file | the study's own decisions (below) | one of them is taken |

Restart the shell after a change: `python start_shell.py restart shell`.

## Decisions this study has to take

Fill these in here before real participants use the system. The ethics and data-protection
applications need them; `ETHICS.md` in the repository only describes the software.

- **Sign-up:** the age range (`project.toml`, now 1–150), and the gender options and their wording.
- **Questionnaire:** the items, their scales and thresholds, and the follow-up questions in Tilbot.
- **Transcripts:** whether the study needs full transcripts (`transcripts.enabled` in `project.toml`; stored encrypted by the shell), and who may read them.
- **Data category:** whether the data is special-category data under the GDPR (health, political opinions, …), which decides how strict the rest must be.
- **Retention:** how long answers, transcripts and the sign-in attempt log are kept, and how they are deleted after the study.
- **Removal requests:** whether participants can ask for their data to be removed, given that only their code identifies them.
- **Access:** who has access to the server, the encryption key and the backups.
