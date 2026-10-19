// The chat page (bridge/templates/bridge/chat.html). Tilbot's flowchart opens the participant's results
// with a "Message to parent window" event whose message is show_results. The results themselves come
// from the shell (/results), never through Tilbot.
const chat = document.querySelector(".chat");
const bot = chat.querySelector("iframe");
const results = document.getElementById("results");

async function showResults() {
  const response = await fetch(results.dataset.url);
  if (!response.ok) {
    return;
  }
  results.innerHTML = await response.text();
  results.hidden = false;
  chat.classList.add("with-results");
}

function hideResults() {
  results.hidden = true;
  chat.classList.remove("with-results");
}

addEventListener("message", (event) => {
  // Only the Tilbot frame on this page can open the results; a message from anywhere else is ignored.
  const fromBot = event.source === bot.contentWindow && event.origin === bot.dataset.origin;
  if (fromBot && event.data?.content === "show_results") {
    showResults();
  }
});

document.addEventListener("click", (event) => {
  if (event.target.closest("[data-results-open]")) {
    showResults();
  } else if (event.target.closest("[data-results-back]")) {
    hideResults();
  } else if (event.target.closest("[data-results-print]")) {
    print();
  }
});
