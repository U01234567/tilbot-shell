// The chat page (bridge/templates/bridge/chat.html).
// - Tilbot's flowchart opens the participant's results with a "Message to parent window" event whose
//   message is show_results. The results themselves come from the shell (/results), never through Tilbot.
//   The button below the chat appears once they were shown, to open and close them again on this visit.
// - When the results are shown in the chat instead, the event's message is done: the questionnaire is over.
// - Signing out, or leaving the page, before every question is answered loses the participant's place
//   in the chat (Tilbot starts again), so the page asks first.
const chat = document.querySelector(".chat");
const bot = chat.querySelector("iframe");
const results = document.getElementById("results"); // absent when the study shows no panel
const resultsButton = document.querySelector("[data-results-open]"); // the same
const signOut = document.querySelector(".sign-out");
const signOutCheck = document.getElementById("sign-out-check");
let leaving = false; // the participant chose to sign out: don't ask again
let done = bot.dataset.done === "true"; // every question answered: leaving loses nothing

async function showResults() {
  const response = await fetch(results.dataset.url);
  if (!response.ok) {
    return;
  }
  results.innerHTML = await response.text();
  results.hidden = false;
  resultsButton.hidden = false;
  chat.classList.add("with-results");
  done = true;
}

function hideResults() {
  results.hidden = true;
  chat.classList.remove("with-results");
}

addEventListener("message", (event) => {
  // Only the Tilbot frame on this page can open the results; a message from anywhere else is ignored.
  if (event.source !== bot.contentWindow || event.origin !== bot.dataset.origin) {
    return;
  }
  if (event.data?.content === "show_results" && results) {
    showResults();
  } else if (event.data?.content === "done") {
    done = true;
  }
});

signOut.addEventListener("submit", (event) => {
  if (!leaving) {
    event.preventDefault();
    signOutCheck.showModal();
  }
});

// The browser's own "Leave site?" question; browsers don't let a page choose its words.
addEventListener("beforeunload", (event) => {
  if (!leaving && !done) {
    event.preventDefault();
  }
});

document.addEventListener("click", (event) => {
  if (event.target.closest("[data-results-open]")) {
    results.hidden ? showResults() : hideResults(); // the button below the chat opens and closes the panel
  } else if (event.target.closest("[data-results-back]")) {
    hideResults();
  } else if (event.target.closest("[data-sign-out]")) {
    leaving = true;
    signOut.requestSubmit();
  } else if (event.target.closest("[data-stay]")) {
    signOutCheck.close();
  }
});
