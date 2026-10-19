# The project folder

Everything about one study lives here. `start_shell.py up` copies `project-example/` to `project/`
on the first start; after that `project/` is yours and is never committed. Back it up by copying the folder; the flowchart itself is exported from Tilbot's dashboard (docs/operations.md).
Participant data is never in this folder: it stays in the database.

| File | What it holds | Change it when… |
|---|---|---|
| `project.toml` | the study name, sign-up limits and options, the Tilbot project id | the research team changes a setting |
| `questionnaire.toml` | per item: the answer scale, the words on its buttons and the threshold for follow-ups | the questionnaire changes |
| `theme/tokens.css` | the study's colours and font, on the participant pages only | the look should change |
| `theme/logo.png` | optional: the study's logo, above the participant pages (not the chat) | the logo changes |
| `feedback.toml` | the results beside the chat: scales, thresholds and texts (phase 2); leave it out for no results | the results change |
| `tilbot/<name>.tilbot` | the flowchart, exported from Tilbot's dashboard as a backup; `example.tilbot` is a working example to import | the conversation changes |
| `knowledge.xlsx` | the questions participants may ask, with example phrasings, answers and optional links (phase 3); `knowledge-example.xlsx` shows the format: rename a copy to switch phase 3 on | the knowledge base changes |
| this file | the study's own decisions (below) | one of them is taken |

Restart the shell after a change: `python start_shell.py restart shell`. After adding or removing `knowledge.xlsx`: `python start_shell.py up`, which starts or leaves out the matching service.

## Decisions this study has to take

Fill these in here before real participants use the system. The ethics and data-protection
applications need them; `ETHICS.md` in the repository only describes the software.

- **Sign-up:** the age range (`project.toml`, now 1–150), and the gender options and their wording.
- **Questionnaire:** the items, their scales and thresholds, and the follow-up questions in Tilbot.
- **Results:** which scales participants see, their thresholds, and the wording, so that no result reads as a diagnosis.
- **Questions:** whether participants can ask questions, who writes and checks the answers, and whether the questions' text is kept (only with transcripts).
- **Transcripts:** whether the study needs full transcripts (`transcripts.enabled` in `project.toml`; stored encrypted by the shell), and who may read them.
- **Data category:** whether the data is special-category data under the GDPR (health, political opinions, …), which decides how strict the rest must be.
- **Retention:** how long answers, transcripts and the sign-in attempt log are kept, and how they are deleted after the study.
- **Removal requests:** whether participants can ask for their data to be removed, given that only their code identifies them.
- **Access:** who has access to the server, the encryption key, the backups and the researcher dashboard.
- **Exports:** who may export the data, with or without codes, and where the exported files are kept.
